"""
This module provides an adapter for Azure Text-to-Speech services.

It implements the TextToSpeechService interface and handles the complexities of
interacting with both Azure's edge-tts (via the `edge_tts` library for "v1" voices)
and Azure Cognitive Services Speech SDK (for "v2" voices).
Configuration is sourced from `app.config.config.azure`.
"""
import asyncio
import re
from typing import Any, List, Union, Tuple
from xml.sax.saxutils import unescape # Used by helper, may not be needed if create_subtitle is moved
from datetime import datetime # Used by helper

import edge_tts # For "v1" Azure voices (via Edge online TTS)
from edge_tts import SubMaker as EdgeSubMaker # Renamed to avoid conflict if a local SubMaker exists
# from edge_tts.submaker import mktimestamp # If create_subtitle functionality were here
import azure.cognitiveservices.speech as speechsdk # For "v2" Azure voices (Speech SDK)

from app.config import config as app_config # Standardized import alias
from app.services.tts_interface import TextToSpeechService
# Assuming app.services.subtitle.SubMaker is the standard SubMaker if it exists,
# otherwise, EdgeSubMaker is used for consistency with original behavior.
# For this adapter, the subtitle data returned is an EdgeSubMaker instance.
# from app.services.subtitle import SubMaker
from app.utils import utils # Currently not used here, but kept from original structure

from loguru import logger


# Helper functions specific to Azure TTS, adapted from voice.py

def _parse_azure_voice_name(name: str) -> str:
    """
    Parses a full Azure voice name string (which may include gender) to extract
    the base voice ID used by the APIs.
    Example: "zh-CN-XiaoyiNeural-Female" -> "zh-CN-XiaoyiNeural"
    Example: "zh-CN-XiaoxiaoMultilingualNeural-V2-Female" -> "zh-CN-XiaoxiaoMultilingualNeural-V2"
    """
    name = name.replace("-Female", "").replace("-Male", "").strip()
    return name

def _is_azure_v2_voice(voice_id_with_gender: str) -> str:
    """
    Checks if the given voice name corresponds to an Azure Speech SDK (V2) voice.
    V2 voices typically have "-V2" in their name and are often multilingual.

    Args:
        voice_id_with_gender: The full voice name string (e.g., "en-US-AndrewMultilingualNeural-V2-Male").

    Returns:
        The base voice name (e.g., "en-US-AndrewMultilingualNeural-V2") if it's a V2 voice,
        otherwise an empty string.
    """
    parsed_name = _parse_azure_voice_name(voice_id_with_gender)
    if parsed_name.endswith("-V2"):
        # The Azure SDK uses the full name including "-V2" for v2 voices.
        return parsed_name
    return ""

def _convert_rate_to_percent_str(rate: float) -> str:
    """
    Converts a rate float (e.g., 1.0 for normal, 1.5 for 50% faster)
    to Azure's string format for speech rate (e.g., "+0%", "+50%").
    Used for edge-tts (v1 voices).
    """
    if not (0.5 <= rate <= 2.0): # Typical supported range for edge-tts rate
        logger.warning(f"Azure edge-tts rate {rate} is outside typical [0.5, 2.0] range. May not work as expected.")
    if rate == 1.0:
        return "+0%"
    percent = round((rate - 1.0) * 100)
    return f"+{percent}%" if percent > 0 else f"{percent}%"

def _format_duration_to_offset_100ns(duration: Union[str, int]) -> int:
    """
    Converts duration (either from Azure SDK string "H:M:S.f" or int ticks)
    to 100-nanosecond units, which is used by edge_tts.SubMaker.
    """
    if isinstance(duration, str): # Format "0:0:1.2340000" (H:M:S.fraction_of_second)
        parts = duration.split(':')
        h = int(parts[0])
        m = int(parts[1])
        s_parts = parts[2].split('.')
        s = int(s_parts[0])
        
        # Azure SDK evt.duration gives 7 decimal places for seconds (100ns precision)
        hundred_ns_part = 0
        if len(s_parts) > 1 and len(s_parts[1]) > 0:
            hundred_ns_part = int(s_parts[1].ljust(7, '0')[:7]) # Ensure 7 digits for 100ns

        total_100ns = (h * 3600 + m * 60 + s) * 10_000_000 + hundred_ns_part
        return total_100ns
        
    if isinstance(duration, int): # Azure SDK audio_offset is already in 100ns ticks
        return duration
    logger.warning(f"Unexpected duration type for Azure TTS: {type(duration)}. Returning 0.")
    return 0


class AzureTTSAdapter(TextToSpeechService):
    """
    Adapter for Azure Text-to-Speech services.

    This class implements the `TextToSpeechService` interface. It determines whether to
    use Azure's older TTS mechanism (via `edge-tts` library, referred to as "v1")
    or the newer Azure Cognitive Services Speech SDK (referred to as "v2") based on
    the provided `voice_id`.

    Configuration for Azure credentials (speech key and region) is loaded from
    `app.config.config.azure`.
    """
    def __init__(self, speech_key: str = None, speech_region: str = None):
        """
        Initializes the AzureTTSAdapter.

        Args:
            speech_key (str, optional): Azure Speech API key. Defaults to value from config.
            speech_region (str, optional): Azure Speech service region. Defaults to value from config.
        """
        self.speech_key = speech_key or app_config.azure.get("speech_key")
        self.speech_region = speech_region or app_config.azure.get("speech_region")

        if not self.speech_key or not self.speech_region:
            logger.warning(
                "Azure Speech Key or Region is not configured. "
                "AzureTTSAdapter may not function correctly, especially for V2 voices."
            )


    async def _synthesize_v1_edge_tts(
        self, text: str, voice_id: str, output_filename: str, rate_str: str
    ) -> EdgeSubMaker:
        """
        Synthesizes speech using the edge-tts library (for "v1" voices).

        Args:
            text: The text to synthesize.
            voice_id: The base voice ID (e.g., "zh-CN-XiaoyiNeural").
            output_filename: Path to save the audio file.
            rate_str: Speech rate in Azure's string format (e.g., "+0%").

        Returns:
            An `edge_tts.SubMaker` object containing subtitle information.
        """
        communicate = edge_tts.Communicate(text, voice_id, rate=rate_str)
        sub_maker = EdgeSubMaker()
        with open(output_filename, "wb") as file:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    sub_maker.create_sub(
                        (chunk["offset"], chunk["duration"]), chunk["text"]
                    )
        return sub_maker

    def _synthesize_v2_sdk(
        self, text: str, voice_id_v2_full: str, output_filename: str, **kwargs
    ) -> EdgeSubMaker:
        """
        Synthesizes speech using the Azure Cognitive Services Speech SDK (for "v2" voices).

        Args:
            text: The text to synthesize.
            voice_id_v2_full: The full V2 voice name (e.g., "en-US-AndrewMultilingualNeural-V2").
            output_filename: Path to save the audio file.
            **kwargs: Additional keyword arguments, e.g., `output_format`.

        Returns:
            An `edge_tts.SubMaker` object populated with word boundary information.

        Raises:
            RuntimeError: If Azure SDK synthesis fails.
            ValueError: If speech key or region is missing.
        """
        if not self.speech_key or not self.speech_region:
            raise ValueError("Azure Speech Key and Region must be configured for V2 voices.")

        sub_maker = EdgeSubMaker()

        def speech_synthesizer_word_boundary_cb(evt: speechsdk.SessionEventArgs):
            """Callback for Azure SDK word boundary events to populate SubMaker."""
            # evt.audio_offset is in ticks (100 nanoseconds)
            # evt.duration is a timedelta object, convert to 100ns ticks
            duration_100ns = int(evt.duration.total_seconds() * 10_000_000)
            offset_100ns = evt.audio_offset
            
            sub_maker.subs.append(evt.text)
            sub_maker.offset.append((offset_100ns, offset_100ns + duration_100ns))

        speech_config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        speech_config.speech_synthesis_voice_name = voice_id_v2_full
        speech_config.set_property(
            property_id=speechsdk.PropertyId.SpeechServiceResponse_RequestWordBoundary,
            value="true",
        )
        
        output_format_enum = kwargs.get("output_format", speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3)
        speech_config.set_speech_synthesis_output_format(output_format_enum)

        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        
        # Connect the event to the callback
        speech_synthesizer.synthesis_word_boundary.connect(speech_synthesizer_word_boundary_cb)

        result = speech_synthesizer.speak_text_async(text).get()
        speech_synthesizer.synthesis_word_boundary.disconnect_all() # Clean up connection

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.info(f"Azure SDK TTS completed for '{output_filename}'")
            return sub_maker
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            logger.error(f"Azure SDK TTS canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                logger.error(f"Azure SDK TTS error details: {cancellation_details.error_details}")
            raise RuntimeError(f"Azure SDK TTS synthesis failed: {cancellation_details.reason} - {cancellation_details.error_details}")
        
        # Should not be reached if logic is correct and an exception is raised on failure
        return sub_maker


    def synthesize_speech(
        self, text: str, voice_id: str, output_filename: str, **kwargs
    ) -> Tuple[str, Any]:
        """
        Synthesizes speech using either edge-tts (v1) or Azure Speech SDK (v2).

        The method determines the appropriate backend based on the `voice_id` format.
        It attempts synthesis up to 3 times in case of transient errors.

        Args:
            text: The text content to synthesize.
            voice_id: The full voice name, including gender and potentially "-V2" suffix
                      (e.g., "en-US-JennyNeural-Female", "en-US-AndrewMultilingualNeural-V2-Male").
            output_filename: The path where the generated audio file will be saved.
            **kwargs:
                voice_rate (float, optional): For v1 (edge_tts) voices, specifies the speech rate.
                                     Default is 1.0. Not directly used for v2 voices via this arg.
                output_format (speechsdk.SpeechSynthesisOutputFormat, optional): For v2 voices,
                                     specifies the audio output format. Defaults to Audio48Khz192KBitRateMonoMp3.

        Returns:
            A tuple containing the path to the audio file and an `edge_tts.SubMaker`
            object with subtitle information, or None if synthesis fails.

        Raises:
            RuntimeError: If synthesis fails after multiple retries.
            ValueError: If V2 voice is selected but key/region are missing.
        """
        text = text.strip()
        
        # Check if it's a V2 voice (e.g., "en-US-AndrewMultilingualNeural-V2-Male" -> "en-US-AndrewMultilingualNeural-V2")
        azure_v2_voice_full_name = _is_azure_v2_voice(voice_id)

        sub_maker_result: EdgeSubMaker = None # Type hint for clarity
        
        for attempt in range(3): # Retry loop
            try:
                if azure_v2_voice_full_name:
                    logger.info(f"Using Azure SDK (v2) for voice: {azure_v2_voice_full_name}, attempt: {attempt+1}")
                    sub_maker_result = self._synthesize_v2_sdk(text, azure_v2_voice_full_name, output_filename, **kwargs)
                else:
                    # Use edge_tts (v1)
                    parsed_v1_voice_id = _parse_azure_voice_name(voice_id) # e.g., "zh-CN-XiaoyiNeural"
                    logger.info(f"Using edge_tts (v1) for voice: {parsed_v1_voice_id}, attempt: {attempt+1}")
                    voice_rate = float(kwargs.get("voice_rate", 1.0))
                    rate_str = _convert_rate_to_percent_str(voice_rate)
                    
                    # asyncio.run can be problematic if an event loop is already running.
                    # Consider using a helper that gets or creates a loop if this adapter
                    # might be called from an async context in the future.
                    # For now, assuming it's called from a sync context as per TextToSpeechService interface.
                    sub_maker_result = asyncio.run(
                        self._synthesize_v1_edge_tts(text, parsed_v1_voice_id, output_filename, rate_str)
                    )
                
                if sub_maker_result and hasattr(sub_maker_result, 'subs') and sub_maker_result.subs:
                    logger.info(f"Azure TTS synthesis successful: '{output_filename}'")
                    return output_filename, sub_maker_result
                else:
                    logger.warning(f"Azure TTS attempt {attempt+1}: No subtitles generated or SubMaker empty.")

            except Exception as e:
                logger.error(f"Azure TTS synthesis attempt {attempt+1} failed for voice '{voice_id}': {e}")
                if attempt == 2: # Last attempt
                    raise RuntimeError(f"Azure TTS failed after 3 attempts for voice '{voice_id}': {e}") from e
        
        logger.error(f"Azure TTS synthesis ultimately failed for '{voice_id}' after retries without producing subs.")
        return output_filename, None # Should ideally not be reached if exceptions are raised


    def get_available_voices(self, **kwargs) -> List[str]:
        """
        Gets a list of available Azure voices.

        Currently, this list is hardcoded based on data available at the time of
        implementation. It does not query the Azure API for a live list.
        The `filter_locals` kwarg can be used to filter by locale prefixes.

        Args:
            **kwargs:
                filter_locals (List[str], optional): A list of locale prefixes
                                     (e.g., ["en-US", "zh-CN"]) to filter the voices.
                                     If None, all voices are returned.
        Returns:
            A sorted list of voice name strings (e.g., "en-US-JennyNeural-Female").
        """
        filter_locals = kwargs.get("filter_locals")
        # This extensive list is from the original app/services/voice.py
        azure_voices_str = """
Name: af-ZA-AdriNeural
Gender: Female
Name: af-ZA-WillemNeural
Gender: Male
Name: am-ET-AmehaNeural
Gender: Male
Name: am-ET-MekdesNeural
Gender: Female
Name: ar-AE-FatimaNeural
Gender: Female
Name: ar-AE-HamdanNeural
Gender: Male
Name: ar-BH-AliNeural
Gender: Male
Name: ar-BH-LailaNeural
Gender: Female
Name: ar-DZ-AminaNeural
Gender: Female
Name: ar-DZ-IsmaelNeural
Gender: Male
Name: ar-EG-SalmaNeural
Gender: Female
Name: ar-EG-ShakirNeural
Gender: Male
Name: ar-IQ-BasselNeural
Gender: Male
Name: ar-IQ-RanaNeural
Gender: Female
Name: ar-JO-SanaNeural
Gender: Female
Name: ar-JO-TaimNeural
Gender: Male
Name: ar-KW-FahedNeural
Gender: Male
Name: ar-KW-NouraNeural
Gender: Female
Name: ar-LB-LaylaNeural
Gender: Female
Name: ar-LB-RamiNeural
Gender: Male
Name: ar-LY-ImanNeural
Gender: Female
Name: ar-LY-OmarNeural
Gender: Male
Name: ar-MA-JamalNeural
Gender: Male
Name: ar-MA-MounaNeural
Gender: Female
Name: ar-OM-AbdullahNeural
Gender: Male
Name: ar-OM-AyshaNeural
Gender: Female
Name: ar-QA-AmalNeural
Gender: Female
Name: ar-QA-MoazNeural
Gender: Male
Name: ar-SA-HamedNeural
Gender: Male
Name: ar-SA-ZariyahNeural
Gender: Female
Name: ar-SY-AmanyNeural
Gender: Female
Name: ar-SY-LaithNeural
Gender: Male
Name: ar-TN-HediNeural
Gender: Male
Name: ar-TN-ReemNeural
Gender: Female
Name: ar-YE-MaryamNeural
Gender: Female
Name: ar-YE-SalehNeural
Gender: Male
Name: az-AZ-BabekNeural
Gender: Male
Name: az-AZ-BanuNeural
Gender: Female
Name: bg-BG-BorislavNeural
Gender: Male
Name: bg-BG-KalinaNeural
Gender: Female
Name: bn-BD-NabanitaNeural
Gender: Female
Name: bn-BD-PradeepNeural
Gender: Male
Name: bn-IN-BashkarNeural
Gender: Male
Name: bn-IN-TanishaaNeural
Gender: Female
Name: bs-BA-GoranNeural
Gender: Male
Name: bs-BA-VesnaNeural
Gender: Female
Name: ca-ES-EnricNeural
Gender: Male
Name: ca-ES-JoanaNeural
Gender: Female
Name: cs-CZ-AntoninNeural
Gender: Male
Name: cs-CZ-VlastaNeural
Gender: Female
Name: cy-GB-AledNeural
Gender: Male
Name: cy-GB-NiaNeural
Gender: Female
Name: da-DK-ChristelNeural
Gender: Female
Name: da-DK-JeppeNeural
Gender: Male
Name: de-AT-IngridNeural
Gender: Female
Name: de-AT-JonasNeural
Gender: Male
Name: de-CH-JanNeural
Gender: Male
Name: de-CH-LeniNeural
Gender: Female
Name: de-DE-AmalaNeural
Gender: Female
Name: de-DE-ConradNeural
Gender: Male
Name: de-DE-FlorianMultilingualNeural
Gender: Male
Name: de-DE-KatjaNeural
Gender: Female
Name: de-DE-KillianNeural
Gender: Male
Name: de-DE-SeraphinaMultilingualNeural
Gender: Female
Name: el-GR-AthinaNeural
Gender: Female
Name: el-GR-NestorasNeural
Gender: Male
Name: en-AU-NatashaNeural
Gender: Female
Name: en-AU-WilliamNeural
Gender: Male
Name: en-CA-ClaraNeural
Gender: Female
Name: en-CA-LiamNeural
Gender: Male
Name: en-GB-LibbyNeural
Gender: Female
Name: en-GB-MaisieNeural
Gender: Female
Name: en-GB-RyanNeural
Gender: Male
Name: en-GB-SoniaNeural
Gender: Female
Name: en-GB-ThomasNeural
Gender: Male
Name: en-HK-SamNeural
Gender: Male
Name: en-HK-YanNeural
Gender: Female
Name: en-IE-ConnorNeural
Gender: Male
Name: en-IE-EmilyNeural
Gender: Female
Name: en-IN-NeerjaExpressiveNeural
Gender: Female
Name: en-IN-NeerjaNeural
Gender: Female
Name: en-IN-PrabhatNeural
Gender: Male
Name: en-KE-AsiliaNeural
Gender: Female
Name: en-KE-ChilembaNeural
Gender: Male
Name: en-NG-AbeoNeural
Gender: Male
Name: en-NG-EzinneNeural
Gender: Female
Name: en-NZ-MitchellNeural
Gender: Male
Name: en-NZ-MollyNeural
Gender: Female
Name: en-PH-JamesNeural
Gender: Male
Name: en-PH-RosaNeural
Gender: Female
Name: en-SG-LunaNeural
Gender: Female
Name: en-SG-WayneNeural
Gender: Male
Name: en-TZ-ElimuNeural
Gender: Male
Name: en-TZ-ImaniNeural
Gender: Female
Name: en-US-AnaNeural
Gender: Female
Name: en-US-AndrewMultilingualNeural
Gender: Male
Name: en-US-AndrewNeural
Gender: Male
Name: en-US-AriaNeural
Gender: Female
Name: en-US-AvaMultilingualNeural
Gender: Female
Name: en-US-AvaNeural
Gender: Female
Name: en-US-BrianMultilingualNeural
Gender: Male
Name: en-US-BrianNeural
Gender: Male
Name: en-US-ChristopherNeural
Gender: Male
Name: en-US-EmmaMultilingualNeural
Gender: Female
Name: en-US-EmmaNeural
Gender: Female
Name: en-US-EricNeural
Gender: Male
Name: en-US-GuyNeural
Gender: Male
Name: en-US-JennyNeural
Gender: Female
Name: en-US-MichelleNeural
Gender: Female
Name: en-US-RogerNeural
Gender: Male
Name: en-US-SteffanNeural
Gender: Male
Name: en-ZA-LeahNeural
Gender: Female
Name: en-ZA-LukeNeural
Gender: Male
Name: es-AR-ElenaNeural
Gender: Female
Name: es-AR-TomasNeural
Gender: Male
Name: es-BO-MarceloNeural
Gender: Male
Name: es-BO-SofiaNeural
Gender: Female
Name: es-CL-CatalinaNeural
Gender: Female
Name: es-CL-LorenzoNeural
Gender: Male
Name: es-CO-GonzaloNeural
Gender: Male
Name: es-CO-SalomeNeural
Gender: Female
Name: es-CR-JuanNeural
Gender: Male
Name: es-CR-MariaNeural
Gender: Female
Name: es-CU-BelkysNeural
Gender: Female
Name: es-CU-ManuelNeural
Gender: Male
Name: es-DO-EmilioNeural
Gender: Male
Name: es-DO-RamonaNeural
Gender: Female
Name: es-EC-AndreaNeural
Gender: Female
Name: es-EC-LuisNeural
Gender: Male
Name: es-ES-AlvaroNeural
Gender: Male
Name: es-ES-ElviraNeural
Gender: Female
Name: es-ES-XimenaNeural
Gender: Female
Name: es-GQ-JavierNeural
Gender: Male
Name: es-GQ-TeresaNeural
Gender: Female
Name: es-GT-AndresNeural
Gender: Male
Name: es-GT-MartaNeural
Gender: Female
Name: es-HN-CarlosNeural
Gender: Male
Name: es-HN-KarlaNeural
Gender: Female
Name: es-MX-DaliaNeural
Gender: Female
Name: es-MX-JorgeNeural
Gender: Male
Name: es-NI-FedericoNeural
Gender: Male
Name: es-NI-YolandaNeural
Gender: Female
Name: es-PA-MargaritaNeural
Gender: Female
Name: es-PA-RobertoNeural
Gender: Male
Name: es-PE-AlexNeural
Gender: Male
Name: es-PE-CamilaNeural
Gender: Female
Name: es-PR-KarinaNeural
Gender: Female
Name: es-PR-VictorNeural
Gender: Male
Name: es-PY-MarioNeural
Gender: Male
Name: es-PY-TaniaNeural
Gender: Female
Name: es-SV-LorenaNeural
Gender: Female
Name: es-SV-RodrigoNeural
Gender: Male
Name: es-US-AlonsoNeural
Gender: Male
Name: es-US-PalomaNeural
Gender: Female
Name: es-UY-MateoNeural
Gender: Male
Name: es-UY-ValentinaNeural
Gender: Female
Name: es-VE-PaolaNeural
Gender: Female
Name: es-VE-SebastianNeural
Gender: Male
Name: et-EE-AnuNeural
Gender: Female
Name: et-EE-KertNeural
Gender: Male
Name: fa-IR-DilaraNeural
Gender: Female
Name: fa-IR-FaridNeural
Gender: Male
Name: fi-FI-HarriNeural
Gender: Male
Name: fi-FI-NooraNeural
Gender: Female
Name: fil-PH-AngeloNeural
Gender: Male
Name: fil-PH-BlessicaNeural
Gender: Female
Name: fr-BE-CharlineNeural
Gender: Female
Name: fr-BE-GerardNeural
Gender: Male
Name: fr-CA-AntoineNeural
Gender: Male
Name: fr-CA-JeanNeural
Gender: Male
Name: fr-CA-SylvieNeural
Gender: Female
Name: fr-CA-ThierryNeural
Gender: Male
Name: fr-CH-ArianeNeural
Gender: Female
Name: fr-CH-FabriceNeural
Gender: Male
Name: fr-FR-DeniseNeural
Gender: Female
Name: fr-FR-EloiseNeural
Gender: Female
Name: fr-FR-HenriNeural
Gender: Male
Name: fr-FR-RemyMultilingualNeural
Gender: Male
Name: fr-FR-VivienneMultilingualNeural
Gender: Female
Name: ga-IE-ColmNeural
Gender: Male
Name: ga-IE-OrlaNeural
Gender: Female
Name: gl-ES-RoiNeural
Gender: Male
Name: gl-ES-SabelaNeural
Gender: Female
Name: gu-IN-DhwaniNeural
Gender: Female
Name: gu-IN-NiranjanNeural
Gender: Male
Name: he-IL-AvriNeural
Gender: Male
Name: he-IL-HilaNeural
Gender: Female
Name: hi-IN-MadhurNeural
Gender: Male
Name: hi-IN-SwaraNeural
Gender: Female
Name: hr-HR-GabrijelaNeural
Gender: Female
Name: hr-HR-SreckoNeural
Gender: Male
Name: hu-HU-NoemiNeural
Gender: Female
Name: hu-HU-TamasNeural
Gender: Male
Name: id-ID-ArdiNeural
Gender: Male
Name: id-ID-GadisNeural
Gender: Female
Name: is-IS-GudrunNeural
Gender: Female
Name: is-IS-GunnarNeural
Gender: Male
Name: it-IT-DiegoNeural
Gender: Male
Name: it-IT-ElsaNeural
Gender: Female
Name: it-IT-GiuseppeMultilingualNeural
Gender: Male
Name: it-IT-IsabellaNeural
Gender: Female
Name: iu-Cans-CA-SiqiniqNeural
Gender: Female
Name: iu-Cans-CA-TaqqiqNeural
Gender: Male
Name: iu-Latn-CA-SiqiniqNeural
Gender: Female
Name: iu-Latn-CA-TaqqiqNeural
Gender: Male
Name: ja-JP-KeitaNeural
Gender: Male
Name: ja-JP-NanamiNeural
Gender: Female
Name: jv-ID-DimasNeural
Gender: Male
Name: jv-ID-SitiNeural
Gender: Female
Name: ka-GE-EkaNeural
Gender: Female
Name: ka-GE-GiorgiNeural
Gender: Male
Name: kk-KZ-AigulNeural
Gender: Female
Name: kk-KZ-DauletNeural
Gender: Male
Name: km-KH-PisethNeural
Gender: Male
Name: km-KH-SreymomNeural
Gender: Female
Name: kn-IN-GaganNeural
Gender: Male
Name: kn-IN-SapnaNeural
Gender: Female
Name: ko-KR-HyunsuMultilingualNeural
Gender: Male
Name: ko-KR-InJoonNeural
Gender: Male
Name: ko-KR-SunHiNeural
Gender: Female
Name: lo-LA-ChanthavongNeural
Gender: Male
Name: lo-LA-KeomanyNeural
Gender: Female
Name: lt-LT-LeonasNeural
Gender: Male
Name: lt-LT-OnaNeural
Gender: Female
Name: lv-LV-EveritaNeural
Gender: Female
Name: lv-LV-NilsNeural
Gender: Male
Name: mk-MK-AleksandarNeural
Gender: Male
Name: mk-MK-MarijaNeural
Gender: Female
Name: ml-IN-MidhunNeural
Gender: Male
Name: ml-IN-SobhanaNeural
Gender: Female
Name: mn-MN-BataaNeural
Gender: Male
Name: mn-MN-YesuiNeural
Gender: Female
Name: mr-IN-AarohiNeural
Gender: Female
Name: mr-IN-ManoharNeural
Gender: Male
Name: ms-MY-OsmanNeural
Gender: Male
Name: ms-MY-YasminNeural
Gender: Female
Name: mt-MT-GraceNeural
Gender: Female
Name: mt-MT-JosephNeural
Gender: Male
Name: my-MM-NilarNeural
Gender: Female
Name: my-MM-ThihaNeural
Gender: Male
Name: nb-NO-FinnNeural
Gender: Male
Name: nb-NO-PernilleNeural
Gender: Female
Name: ne-NP-HemkalaNeural
Gender: Female
Name: ne-NP-SagarNeural
Gender: Male
Name: nl-BE-ArnaudNeural
Gender: Male
Name: nl-BE-DenaNeural
Gender: Female
Name: nl-NL-ColetteNeural
Gender: Female
Name: nl-NL-FennaNeural
Gender: Female
Name: nl-NL-MaartenNeural
Gender: Male
Name: pl-PL-MarekNeural
Gender: Male
Name: pl-PL-ZofiaNeural
Gender: Female
Name: ps-AF-GulNawazNeural
Gender: Male
Name: ps-AF-LatifaNeural
Gender: Female
Name: pt-BR-AntonioNeural
Gender: Male
Name: pt-BR-FranciscaNeural
Gender: Female
Name: pt-BR-ThalitaMultilingualNeural
Gender: Female
Name: pt-PT-DuarteNeural
Gender: Male
Name: pt-PT-RaquelNeural
Gender: Female
Name: ro-RO-AlinaNeural
Gender: Female
Name: ro-RO-EmilNeural
Gender: Male
Name: ru-RU-DmitryNeural
Gender: Male
Name: ru-RU-SvetlanaNeural
Gender: Female
Name: si-LK-SameeraNeural
Gender: Male
Name: si-LK-ThiliniNeural
Gender: Female
Name: sk-SK-LukasNeural
Gender: Male
Name: sk-SK-ViktoriaNeural
Gender: Female
Name: sl-SI-PetraNeural
Gender: Female
Name: sl-SI-RokNeural
Gender: Male
Name: so-SO-MuuseNeural
Gender: Male
Name: so-SO-UbaxNeural
Gender: Female
Name: sq-AL-AnilaNeural
Gender: Female
Name: sq-AL-IlirNeural
Gender: Male
Name: sr-RS-NicholasNeural
Gender: Male
Name: sr-RS-SophieNeural
Gender: Female
Name: su-ID-JajangNeural
Gender: Male
Name: su-ID-TutiNeural
Gender: Female
Name: sv-SE-MattiasNeural
Gender: Male
Name: sv-SE-SofieNeural
Gender: Female
Name: sw-KE-RafikiNeural
Gender: Male
Name: sw-KE-ZuriNeural
Gender: Female
Name: sw-TZ-DaudiNeural
Gender: Male
Name: sw-TZ-RehemaNeural
Gender: Female
Name: ta-IN-PallaviNeural
Gender: Female
Name: ta-IN-ValluvarNeural
Gender: Male
Name: ta-LK-KumarNeural
Gender: Male
Name: ta-LK-SaranyaNeural
Gender: Female
Name: ta-MY-KaniNeural
Gender: Female
Name: ta-MY-SuryaNeural
Gender: Male
Name: ta-SG-AnbuNeural
Gender: Male
Name: ta-SG-VenbaNeural
Gender: Female
Name: te-IN-MohanNeural
Gender: Male
Name: te-IN-ShrutiNeural
Gender: Female
Name: th-TH-NiwatNeural
Gender: Male
Name: th-TH-PremwadeeNeural
Gender: Female
Name: tr-TR-AhmetNeural
Gender: Male
Name: tr-TR-EmelNeural
Gender: Female
Name: uk-UA-OstapNeural
Gender: Male
Name: uk-UA-PolinaNeural
Gender: Female
Name: ur-IN-GulNeural
Gender: Female
Name: ur-IN-SalmanNeural
Gender: Male
Name: ur-PK-AsadNeural
Gender: Male
Name: ur-PK-UzmaNeural
Gender: Female
Name: uz-UZ-MadinaNeural
Gender: Female
Name: uz-UZ-SardorNeural
Gender: Male
Name: vi-VN-HoaiMyNeural
Gender: Female
Name: vi-VN-NamMinhNeural
Gender: Male
Name: zh-CN-XiaoxiaoNeural
Gender: Female
Name: zh-CN-XiaoyiNeural
Gender: Female
Name: zh-CN-YunjianNeural
Gender: Male
Name: zh-CN-YunxiNeural
Gender: Male
Name: zh-CN-YunxiaNeural
Gender: Male
Name: zh-CN-YunyangNeural
Gender: Male
Name: zh-CN-liaoning-XiaobeiNeural
Gender: Female
Name: zh-CN-shaanxi-XiaoniNeural
Gender: Female
Name: zh-HK-HiuGaaiNeural
Gender: Female
Name: zh-HK-HiuMaanNeural
Gender: Female
Name: zh-HK-WanLungNeural
Gender: Male
Name: zh-TW-HsiaoChenNeural
Gender: Female
Name: zh-TW-HsiaoYuNeural
Gender: Female
Name: zh-TW-YunJheNeural
Gender: Male
Name: zu-ZA-ThandoNeural
Gender: Female
Name: zu-ZA-ThembaNeural
Gender: Male

Name: en-US-AvaMultilingualNeural-V2
Gender: Female
Name: en-US-AndrewMultilingualNeural-V2
Gender: Male
Name: en-US-EmmaMultilingualNeural-V2
Gender: Female
Name: en-US-BrianMultilingualNeural-V2
Gender: Male
Name: de-DE-FlorianMultilingualNeural-V2
Gender: Male
Name: de-DE-SeraphinaMultilingualNeural-V2
Gender: Female
Name: fr-FR-RemyMultilingualNeural-V2
Gender: Male
Name: fr-FR-VivienneMultilingualNeural-V2
Gender: Female
Name: zh-CN-XiaoxiaoMultilingualNeural-V2
Gender: Female
        """.strip()
        
        voices = []
        pattern = re.compile(r"Name:\s*(.+?)\s*Gender:\s*(.+?)\s*\n", re.MULTILINE)
        matches = pattern.findall(azure_voices_str + "\n") # Add newline to match last entry

        for name, gender in matches:
            full_voice_name = f"{name.strip()}-{gender.strip()}"
            if filter_locals:
                # Check if the voice name starts with any of the filter_locals
                # e.g., filter_local "en-US" should match "en-US-JennyNeural-Female"
                if any(name.strip().startswith(fl) for fl in filter_locals):
                    voices.append(full_voice_name)
            else:
                voices.append(full_voice_name)
        
        voices.sort()
        return voices

# Note: The SubMaker class might need to be reconciled.
# If app.services.subtitle.SubMaker is different from edge_tts.SubMaker,
# an adapter or common format for subtitle data will be needed.
# For now, this code assumes that the SubMaker returned by Azure methods
# is compatible with what the TextToSpeechService interface expects.
# The original `create_subtitle` and `get_audio_duration` functions from `voice.py`
# were not moved here as they seem to be utility functions for post-processing
# subtitles, rather than part of the core TTS synthesis. They might be needed elsewhere.

# Example of how to get the asyncio loop if needed (e.g., if not running in an async context already)
# async def some_async_function():
#     # ... your async code ...
#
# try:
#     loop = asyncio.get_running_loop()
# except RuntimeError:  # 'RuntimeError: There is no current event loop...'
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
# result = loop.run_until_complete(some_async_function())

# For synthesize_speech, if called from a synchronous context, ensure async parts are run correctly.
# The current implementation uses asyncio.run() for the edge_tts part.
# The Azure SDK v2 part is synchronous in its .get() call.
# If the main application is async, asyncio.run() should not be used directly within library code.
# Instead, the adapter methods themselves should be `async` and `await` the calls.
# For now, `synthesize_speech` is synchronous as per the interface,
# and `asyncio.run` is used internally for the async edge_tts call.
# This is a common pattern but has implications if the broader application is async.
# The interface `synthesize_speech` is not async, so this should be fine for now.
