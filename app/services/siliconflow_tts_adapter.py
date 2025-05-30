"""
This module provides an adapter for the SiliconFlow Text-to-Speech service.

It implements the `TextToSpeechService` interface and handles communication
with the SiliconFlow API. Configuration, such as the API key, is expected
to be provided via `app.config.config.siliconflow`.
Subtitle generation is rudimentary, based on splitting text by punctuation
and distributing timestamps proportionally to audio duration.
"""
import requests
from typing import Any, List, Tuple, Union

from app.config import config as app_config # Standardized import alias
from app.services.tts_interface import TextToSpeechService
# Assuming app.services.subtitle.SubMaker is compatible with edge_tts.SubMaker structure
from app.services.subtitle import SubMaker
from app.utils import utils # For split_string_by_punctuations

from loguru import logger

# Helper function specific to SiliconFlow, can be kept in this module
def _is_siliconflow_voice(voice_name: str) -> bool:
    """
    Checks if the provided voice name string indicates it's a SiliconFlow voice
    by looking for the "siliconflow:" prefix.
    """
    return voice_name.startswith("siliconflow:")

class SiliconflowTTSAdapter(TextToSpeechService):
    """
    Adapter for SiliconFlow Text-to-Speech service.

    This class connects to the SiliconFlow API to synthesize speech.
    It requires an API key to be configured in `app.config.config.siliconflow`.
    The list of available voices is currently hardcoded as per the original
    implementation but should ideally be fetched from an API if SiliconFlow provides one.
    Subtitle data is returned as a `SubMaker` object, with timestamps generated
    proportionally based on text length and audio duration.
    """
    def __init__(self, api_key: str = None):
        """
        Initializes the SiliconflowTTSAdapter.

        Args:
            api_key (str, optional): SiliconFlow API key.
                                     Defaults to the value from `app.config.config.siliconflow`.
        """
        self.api_key = api_key or app_config.siliconflow.get("api_key")
        if not self.api_key:
            logger.warning(
                "SiliconFlow API key is not configured. "
                "SiliconflowTTSAdapter will not be able to synthesize speech."
            )

    def get_available_voices(self, **kwargs) -> List[str]:
        """
        Gets a list of available SiliconFlow voices.

        Note: This list is currently hardcoded based on the initial implementation.
        It does not make an API call to SiliconFlow to fetch voices dynamically.
        The `kwargs` are ignored in this implementation.

        Returns:
            A list of strings, where each string is a SiliconFlow voice identifier
            (e.g., "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male").
        """
        # From app/services/voice.py, hardcoded list:
        voices_with_gender = [
            ("FunAudioLLM/CosyVoice2-0.5B", "alex", "Male"),
            ("FunAudioLLM/CosyVoice2-0.5B", "anna", "Female"),
            ("FunAudioLLM/CosyVoice2-0.5B", "bella", "Female"),
            ("FunAudioLLM/CosyVoice2-0.5B", "benjamin", "Male"),
            ("FunAudioLLM/CosyVoice2-0.5B", "charles", "Male"),
            ("FunAudioLLM/CosyVoice2-0.5B", "claire", "Female"),
            ("FunAudioLLM/CosyVoice2-0.5B", "david", "Male"),
            ("FunAudioLLM/CosyVoice2-0.5B", "diana", "Female"),
        ]
        return [
            f"siliconflow:{model}:{voice}-{gender}"
            for model, voice, gender in voices_with_gender
        ]

    def synthesize_speech(
        self, text: str, voice_id: str, output_filename: str, **kwargs
    ) -> Tuple[str, Any]:
        """
        Synthesizes speech using the SiliconFlow TTS API.

        Args:
            text: The text to be synthesized.
            voice_id: The SiliconFlow voice identifier, expected to be prefixed with "siliconflow:",
                      e.g., "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male".
            output_filename: Path to save the generated audio file.
            **kwargs:
                voice_rate (float, optional): Speech rate. Defaults to 1.0. SiliconFlow range [0.25, 4.0].
                voice_volume (float, optional): Speech volume. Defaults to 1.0. Mapped to SiliconFlow's
                                      `gain` parameter (range -10 to 10, where 1.0 volume = 0 gain).
                sample_rate (int, optional): Audio sample rate. Defaults to 32000.

        Returns:
            A tuple: (path_to_audio_file, subtitle_data).
            The `subtitle_data` is a `SubMaker` object with rudimentary timestamps,
            or None if synthesis fails.

        Raises:
            ValueError: If `voice_id` is not a valid SiliconFlow identifier or if API key is missing.
        """
        if not _is_siliconflow_voice(voice_id): # Use the module-level helper
            raise ValueError(f"Invalid voice_id format for SiliconFlow: {voice_id}")

        if not self.api_key:
            logger.error("SiliconFlow API key is not configured. Cannot synthesize speech.")
            raise ValueError("SiliconFlow API key is not configured.")

        text = text.strip()
        
        try:
            parts = voice_id.split(":")
            model_name = parts[1]
            voice_with_gender = parts[2]
            voice_actual = voice_with_gender.split("-")[0] 
            api_voice_param = f"{model_name}:{voice_actual}" # Format for API: "model_name:voice_name"
        except IndexError:
            logger.error(f"Could not parse SiliconFlow voice_id: {voice_id}")
            raise ValueError(f"Invalid SiliconFlow voice_id format: {voice_id}")

        voice_rate = float(kwargs.get("voice_rate", 1.0))
        voice_volume = float(kwargs.get("voice_volume", 1.0)) # User-friendly volume (e.g. 1.0 = normal)
        
        # Clamp voice_rate to SiliconFlow's typical supported range [0.25, 4.0]
        if not (0.25 <= voice_rate <= 4.0):
            logger.warning(f"SiliconFlow voice_rate {voice_rate} out of range [0.25, 4.0]. Clamping.")
            voice_rate = max(0.25, min(4.0, voice_rate))

        # Convert user-friendly voice_volume to SiliconFlow 'gain'
        # User volume 1.0 = 0 gain (normal). User volume 0.0 could map to -10 gain (very quiet).
        # User volume 2.0 could map to +X gain (louder). Here, a simple mapping:
        gain = (voice_volume - 1.0) * 5.0 # Example: volume 2.0 -> gain 5.0; volume 0.5 -> gain -2.5
        gain = max(-10.0, min(10.0, gain)) # Clamp to SiliconFlow's gain range [-10, 10]
        logger.debug(f"SiliconFlow: user volume {voice_volume} mapped to gain {gain}")


        url = "https://api.siliconflow.cn/v1/audio/speech"
        payload = {
            "model": model_name, 
            "input": text,
            "voice": api_voice_param, 
            "response_format": kwargs.get("response_format", "mp3"),
            "sample_rate": int(kwargs.get("sample_rate", 32000)),
            "stream": False,
            "speed": voice_rate,
            "gain": gain,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        sub_maker_result: SubMaker = None 

        for attempt in range(3): # Retry loop
            try:
                logger.info(
                    f"Starting SiliconFlow TTS request (attempt {attempt+1}) for voice '{voice_id}', output: '{output_filename}'"
                )
                response = requests.post(url, json=payload, headers=headers, timeout=kwargs.get("timeout", 60))

                if response.status_code == 200:
                    with open(output_filename, "wb") as f:
                        f.write(response.content)
                    logger.success(f"SiliconFlow TTS succeeded, audio saved to '{output_filename}'")

                    sub_maker_result = SubMaker()
                    try:
                        # moviepy is an optional dependency, attempt import here
                        from moviepy.editor import AudioFileClip 

                        audio_clip = AudioFileClip(output_filename)
                        audio_duration_sec = audio_clip.duration
                        audio_clip.close()
                        # SubMaker expects timestamps in 100ns units
                        audio_duration_100ns = int(audio_duration_sec * 10_000_000)

                        sentences = utils.split_string_by_punctuations(text)
                        if sentences:
                            total_chars = sum(len(s) for s in sentences)
                            char_duration_100ns_per_char = (
                                audio_duration_100ns / total_chars if total_chars > 0 else 0
                            )
                            current_offset_100ns = 0
                            for sentence_text in sentences:
                                if not sentence_text.strip():
                                    continue
                                sentence_chars = len(sentence_text)
                                sentence_duration_100ns = int(sentence_chars * char_duration_100ns_per_char)
                                
                                sub_maker_result.subs.append(sentence_text)
                                sub_maker_result.offset.append(
                                     (current_offset_100ns, current_offset_100ns + sentence_duration_100ns)
                                )
                                current_offset_100ns += sentence_duration_100ns
                        else: # Fallback for non-splittable text
                            sub_maker_result.subs = [text]
                            sub_maker_result.offset = [(0, audio_duration_100ns)]
                    except ImportError:
                        logger.warning("moviepy library not found. Cannot generate precise subtitles for SiliconFlow.")
                        sub_maker_result.subs = [text] # Provide full text as one subtitle
                        sub_maker_result.offset = [(0, 10_000_000)] # Placeholder 1-second duration
                    except Exception as e:
                        logger.warning(f"Failed to create subtitles for SiliconFlow TTS due to: {e}. Subtitles may be inaccurate.")
                        sub_maker_result.subs = [text]
                        sub_maker_result.offset = [(0, 10_000_000)]

                    return output_filename, sub_maker_result
                else:
                    logger.error(
                        f"SiliconFlow TTS failed (attempt {attempt+1}) with status {response.status_code}: {response.text}"
                    )
            except requests.exceptions.RequestException as e:
                logger.error(f"SiliconFlow TTS request (attempt {attempt+1}) failed: {e}")
            except Exception as e:
                logger.error(f"An unexpected error in SiliconFlow TTS (attempt {attempt+1}): {e}", exc_info=True)
            
            if attempt == 2: # Last attempt failed
                logger.error(f"SiliconFlow TTS failed permanently after 3 attempts for '{voice_id}'.")
                raise RuntimeError(f"SiliconFlow TTS failed after 3 attempts for '{voice_id}'.")
        
        # Fallback, though should be caught by exception above
        return output_filename, None

# Notes regarding original code structure:
# - The `_is_siliconflow_voice` helper is now part of this module, making it self-contained.
# - Assumes `app.services.subtitle.SubMaker` is the standard and compatible with `edge_tts.SubMaker`'s list-based .subs and .offset.
# - `utils.split_string_by_punctuations` is used for basic subtitle segmentation.
# - `moviepy` is treated as an optional dependency for subtitle timing; if not present, basic subtitles are generated.
