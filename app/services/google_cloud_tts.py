"""
This module implements the TextToSpeechService interface for Google Cloud Text-to-Speech.

It handles authentication, making API calls to Google Cloud TTS, and processing
the responses to generate audio files and subtitle-related data.
Configuration for this service is expected in `app.config.config.google_tts`.
"""
import os
from typing import Any, List, Tuple

from google.cloud import texttospeech, texttospeech_v1
from google.api_core import exceptions as google_exceptions

from app.services.tts_interface import TextToSpeechService
from app.config import config as app_config # Import global config
from loguru import logger

class GoogleCloudTTS(TextToSpeechService):
    """
    Implements the TextToSpeechService for Google Cloud Text-to-Speech.

    This class manages the connection to Google Cloud TTS, including authentication,
    and provides methods to synthesize speech and list available voices.
    It relies on configurations set in `app.config.config.google_tts` for
    defaults such as voice name, language code, and audio encoding, as well as
    for the optional service account key path.

    Authentication methods, in order of precedence:
    1.  Service account key JSON file path provided in `config.google_tts.service_account_key_path`.
    2.  `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to a service account key file.
    3.  Application Default Credentials (ADC) when running in a Google Cloud environment.
    """

    def __init__(self):
        """
        Initializes the GoogleCloudTTS service.

        Sets up the Google Cloud TextToSpeechClient, using credentials specified
        in the application configuration or through standard Google Cloud environment variables.
        It also loads default voice, language, and encoding settings from the config.
        """
        # Config value for service_account_key_path takes precedence.
        # If not set, Google library automatically checks GOOGLE_APPLICATION_CREDENTIALS.
        key_path = app_config.google_tts.get("service_account_key_path")
        
        if key_path:
            logger.info(f"Initializing GoogleCloudTTS with service account key from config: {key_path}")
            try:
                self.client = texttospeech.TextToSpeechClient.from_service_account_file(key_path)
            except Exception as e:
                logger.error(f"Failed to initialize GoogleCloudTTS client with key {key_path}: {e}. Falling back to ADC or GOOGLE_APPLICATION_CREDENTIALS env var.")
                self.client = texttospeech.TextToSpeechClient()
        else:
            # If key_path is not in config, GOOGLE_APPLICATION_CREDENTIALS will be used automatically by the client if set.
            # Otherwise, ADC is used.
            logger.info("Initializing GoogleCloudTTS with Application Default Credentials or GOOGLE_APPLICATION_CREDENTIALS env var if set.")
            self.client = texttospeech.TextToSpeechClient()
        
        self.default_voice_id: str = app_config.google_tts.get("default_voice_name", "en-US-Wavenet-D")
        self.default_language_code: str = app_config.google_tts.get("default_language_code", "en-US")
        self.default_audio_encoding_str: str = app_config.google_tts.get("default_audio_encoding", "MP3").upper()


    def _get_audio_encoding_enum(self, encoding_str: str) -> texttospeech_v1.types.AudioEncoding:
        """
        Converts an audio encoding string (e.g., "MP3", "LINEAR16") to the
        corresponding `texttospeech.AudioEncoding` enum value.

        Args:
            encoding_str: The audio encoding string.

        Returns:
            The `texttospeech.AudioEncoding` enum value. Defaults to MP3 if
            the provided string is invalid.
        """
        try:
            return texttospeech.AudioEncoding[encoding_str]
        except KeyError:
            valid_encodings = [e.name for e in texttospeech.AudioEncoding if e.name != 'AUDIO_ENCODING_UNSPECIFIED']
            logger.warning(
                f"Invalid audio encoding string '{encoding_str}'. "
                f"Defaulting to MP3. Available: {valid_encodings}"
            )
            return texttospeech.AudioEncoding.MP3

    def synthesize_speech(
        self, text: str, voice_id: str = None, output_filename: str = "output.mp3", **kwargs
    ) -> Tuple[str, Any]:
        """
        Synthesizes speech from text using Google Cloud TTS and saves it as an audio file.

        The method uses voice ID, language code, and audio encoding from provided arguments
        or falls back to defaults specified in the application configuration.
        `voice_volume` from the main `tts` function is mapped to `pitch` for Google TTS.
        Other parameters like `speaking_rate` and `effects_profile_id` can be passed via `kwargs`.

        Args:
            text: The text to be synthesized.
            voice_id: The specific voice model name (e.g., "en-US-Wavenet-D").
                      If None, the default from config is used.
            output_filename: The path where the generated audio file will be saved.
            **kwargs:
                language_code (str, optional): BCP-47 language tag (e.g., "en-US").
                                               If None, inferred from `voice_id` or default config used.
                audio_encoding (str, optional): The desired audio encoding (e.g., "MP3", "LINEAR16").
                                                Defaults to value from config.
                speaking_rate (float, optional): Speaking rate/speed, range: 0.25 to 4.0.
                pitch (float, optional): Speaking pitch, range: -20.0 to 20.0.
                effects_profile_id (str or List[str], optional): Identifier(s) for audio effects profiles.

        Returns:
            A tuple: (path_to_audio_file, subtitle_data).
            The subtitle_data is a list of (mark_name, time_seconds) tuples if SSML marks
            were used and timepoints are enabled. Otherwise, it may be an empty list.

        Raises:
            google_exceptions.GoogleAPIError: If the Google Cloud TTS API call fails.
            ValueError: For invalid parameter values not directly handled by the API.
        """
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)

            current_voice_id = voice_id or self.default_voice_id
            current_language_code = kwargs.get("language_code")

            if not current_language_code:
                # Try to infer from voice_id. Expects format like "en-US-Wavenet-A"
                if current_voice_id and len(current_voice_id.split('-')) >= 2:
                    current_language_code = f"{current_voice_id.split('-')[0]}-{current_voice_id.split('-')[1]}"
                else:
                    current_language_code = self.default_language_code
            
            logger.debug(f"Using voice: {current_voice_id}, language: {current_language_code}")

            voice_params = texttospeech.VoiceSelectionParams(
                language_code=current_language_code, name=current_voice_id
            )

            audio_encoding_str_kwarg = kwargs.get("audio_encoding")
            final_audio_encoding_str = audio_encoding_str_kwarg.upper() if audio_encoding_str_kwarg else self.default_audio_encoding_str
            audio_encoding_enum = self._get_audio_encoding_enum(final_audio_encoding_str)
            
            audio_config_params = {"audio_encoding": audio_encoding_enum}

            if "speaking_rate" in kwargs and kwargs["speaking_rate"] is not None:
                rate = float(kwargs["speaking_rate"])
                # Google Cloud TTS speaking_rate is between 0.25 and 4.0
                if not (0.25 <= rate <= 4.0):
                    logger.warning(f"Requested speaking_rate {rate} is out of range [0.25, 4.0]. Clamping.")
                    rate = max(0.25, min(4.0, rate))
                audio_config_params["speaking_rate"] = rate
            if "pitch" in kwargs and kwargs["pitch"] is not None:
                pitch = float(kwargs["pitch"])
                # Google Cloud TTS pitch is between -20.0 and 20.0
                if not (-20.0 <= pitch <= 20.0):
                    logger.warning(f"Requested pitch {pitch} is out of range [-20.0, 20.0]. Clamping.")
                    pitch = max(-20.0, min(20.0, pitch))
                audio_config_params["pitch"] = pitch
            
            if "effects_profile_id" in kwargs and kwargs["effects_profile_id"]:
                profile_ids = kwargs["effects_profile_id"]
                if isinstance(profile_ids, str):
                    audio_config_params["effects_profile_id"] = [profile_ids]
                elif isinstance(profile_ids, list):
                    audio_config_params["effects_profile_id"] = profile_ids
                else:
                    logger.warning(f"Invalid type for effects_profile_id: {type(profile_ids)}. Should be str or list[str]. Ignoring.")


            audio_config = texttospeech.AudioConfig(**audio_config_params)

            request = texttospeech.SynthesizeSpeechRequest(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
                enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK]
            )

            response = self.client.synthesize_speech(request=request)

            # Save the audio content
            with open(output_filename, "wb") as out:
                out.write(response.audio_content)
                logger.info(f"Audio content written to file '{output_filename}'")

            # Process timepoints data.
            # Google Cloud TTS returns timepoints for <mark> tags in SSML.
            # If plain text is used, or no <mark> tags are present, this list might be empty.
            subtitles_data = []
            if response.timepoints:
                for point in response.timepoints:
                    subtitles_data.append((point.mark_name, point.time_seconds))
            logger.debug(f"Subtitle data (timepoints): {subtitles_data}")

            return output_filename, subtitles_data

        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google Cloud TTS API error: {e}")
            raise
        except ValueError as e: # Catch local ValueErrors, e.g. from param validation
            logger.error(f"Google Cloud TTS configuration or parameter error: {e}")
            raise
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error in GoogleCloudTTS.synthesize_speech: {e}", exc_info=True)
            raise


    def get_available_voices(self, **kwargs) -> List[str]:
        """
        Gets a list of available voices from Google Cloud TTS.
        
        Can be filtered by language code by providing a `language_code`_ kwarg.

        Args:
            **kwargs:
                language_code (str, optional): BCP-47 language tag (e.g., "en-US")
                                               to filter the voices. If None, lists voices
                                               for all languages.
        Returns:
            A list of voice names (e.g., "en-US-Wavenet-A").

        Raises:
            google_exceptions.GoogleAPIError: If an error occurs during the API call.
        """
        try:
            # Allow filtering by language_code if provided in kwargs
            language_code_filter = kwargs.get("language_code")
            response = self.client.list_voices(language_code=language_code_filter)
            voice_names = [voice.name for voice in response.voices]
            return voice_names
        except google_exceptions.GoogleAPIError as e:
            logger.error(f"Google Cloud TTS API error while listing voices: {e}")
            raise
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error listing Google voices: {e}", exc_info=True)
            raise
