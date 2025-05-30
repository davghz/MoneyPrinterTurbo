"""
This module provides core Text-to-Speech (TTS) functionalities.

It features a main `tts` function that acts as a dispatcher to various
TTS adapters (Azure, Google Cloud, SiliconFlow) based on the provided
voice name. The selection logic relies on prefixes in the voice name
(e.g., "google:", "siliconflow:") or defaults to Azure if no prefix matches.

The module also retains utility functions for subtitle creation (`create_subtitle`),
text formatting (`_format_text`), and calculating audio duration from subtitle data
(`get_audio_duration`). These utilities are primarily designed to work with
`SubMaker`-like objects (as produced by Azure and SiliconFlow adapters).
"""
import asyncio # Keep for potential future async operations if tts becomes async
import os
import re
# from datetime import datetime # Not directly used in remaining code after cleanup
from typing import Union, Any # Union might be replaced by Any if SubMaker types vary
from xml.sax.saxutils import unescape # Keep if create_subtitle is kept and uses it

# Removed direct imports of edge_tts, requests as they are now handled by adapters.
# Kept SubMaker from edge_tts as it's a common return type for subtitle data from some adapters.
from edge_tts import SubMaker # Potentially used as a common subtitle format
from loguru import logger
from moviepy.video.tools import subtitles # Keep if create_subtitle is kept

from app.config import config
from app.utils import utils

# Import new adapters and interface
from app.services.tts_interface import TextToSpeechService
from app.services.google_cloud_tts import GoogleCloudTTS
from app.services.azure_tts_adapter import AzureTTSAdapter
from app.services.siliconflow_tts_adapter import SiliconflowTTSAdapter


# Old TTS functions and their direct helpers (get_siliconflow_voices, get_all_azure_voices,
# parse_voice_name, is_azure_v2_voice, convert_rate_to_percent, azure_tts_v1,
# siliconflow_tts, azure_tts_v2) have been removed as of previous refactoring steps.
# The _is_siliconflow_voice helper specific to the old `tts` dispatcher was also removed;
# new local helpers _is_google_voice and _is_siliconflow_voice are defined below.


# Local helper functions for provider detection in the main tts dispatcher
def _is_google_voice(voice_name: str) -> bool:
    """Checks if the voice name indicates a Google Cloud TTS voice via 'google:' prefix."""
    return voice_name.startswith("google:")

def _is_siliconflow_voice(voice_name: str) -> bool:
    """Checks if the voice name indicates a SiliconFlow voice via 'siliconflow:' prefix."""
    return voice_name.startswith("siliconflow:")


def tts(
    text: str,
    voice_name: str,
    voice_rate: float,
    voice_file: str,
    voice_volume: float = 1.0,
) -> Any:
    """
    Main Text-to-Speech dispatch function.

    Selects and uses the appropriate TTS adapter (Google Cloud, Azure, SiliconFlow)
    based on the `voice_name` format.
    - "google:...": Uses GoogleCloudTTS. The part after "google:" is the actual voice ID for Google.
    - "siliconflow:...": Uses SiliconflowTTSAdapter. The full name is passed to the adapter.
    - Otherwise (no recognized prefix): Defaults to AzureTTSAdapter. The full name is passed.

    Args:
        text: The text to synthesize into speech.
        voice_name: The voice identifier. Specific prefixes determine the TTS provider.
                    Examples:
                    - "google:en-US-Wavenet-A" (for Google Cloud)
                    - "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male" (for SiliconFlow)
                    - "en-US-JennyNeural-Female" (for Azure, no prefix needed)
        voice_rate: The desired speaking rate. Interpretation may vary slightly by provider.
                    - For Google Cloud: Maps to `speaking_rate` (0.25 to 4.0).
                    - For Azure (edge-tts based v1 voices): Converted to a percentage change (e.g., 1.5 -> "+50%").
                    - For SiliconFlow: Passed as a speed factor (e.g., 1.0 is normal).
        voice_file: The path where the generated audio file will be saved.
        voice_volume: Desired volume or perceived loudness. Interpretation varies by provider:
                      - For Google Cloud: Mapped to `pitch` adjustment. A value of 1.0 means normal pitch (0.0).
                        Values > 1.0 increase pitch, < 1.0 decrease pitch. E.g., 1.5 maps to +5.0 pitch.
                      - For Azure (edge-tts v1): This parameter is not directly used for volume by edge-tts;
                        volume is more related to system settings or SSML for finer control.
                      - For SiliconFlow: Mapped to `gain` (dB). 1.0 means 0dB gain.
                                         Range typically -10dB to +10dB.

    Returns:
        Subtitle-related data, the format of which depends on the TTS provider:
        - GoogleCloudTTS: A list of (mark_name, time_seconds) tuples if SSML marks were used
                          and timepoints enabled; otherwise, may be an empty list.
        - AzureTTSAdapter & SiliconflowTTSAdapter: An `edge_tts.SubMaker` object (or a
                          compatible structure) containing word or sentence timings.
        Returns None if TTS synthesis fails for any reason.
    """
    logger.info(f"TTS request for voice: '{voice_name}', rate: {voice_rate}, volume: {voice_volume}")

    adapter: TextToSpeechService
    actual_voice_id = voice_name # This might be modified if there's a prefix
    subtitle_data = None

    kwargs_for_adapter = {}

    try:
        if _is_google_voice(voice_name):
            logger.info("Using GoogleCloudTTS adapter.")
            adapter = GoogleCloudTTS()
            actual_voice_id = voice_name.split("google:", 1)[1]
            # Map generic voice_rate and voice_volume to Google-specific parameters
            # Google's speaking_rate range: [0.25, 4.0]
            # Google's pitch range: [-20.0, 20.0].
            # Mapping volume to pitch: (volume - 1.0) * 10.0 (e.g., vol 1.0 -> pitch 0.0)
            kwargs_for_adapter = {
                "speaking_rate": voice_rate,
                "pitch": (voice_volume - 1.0) * 10.0
            }

        elif _is_siliconflow_voice(voice_name):
            logger.info("Using SiliconflowTTSAdapter.")
            adapter = SiliconflowTTSAdapter()
            # SiliconflowTTSAdapter expects `voice_rate` and `voice_volume` in kwargs.
            kwargs_for_adapter = {"voice_rate": voice_rate, "voice_volume": voice_volume}

        else: # Default to Azure
            logger.info("Using AzureTTSAdapter.")
            adapter = AzureTTSAdapter()
            # AzureTTSAdapter's synthesize_speech expects `voice_rate` for edge-tts (v1).
            kwargs_for_adapter = {"voice_rate": voice_rate}

        # Synthesize speech using the chosen adapter
        _, subtitle_data = adapter.synthesize_speech(
            text=text,
            voice_id=actual_voice_id,
            output_filename=voice_file,
            **kwargs_for_adapter
        )

        logger.info(f"TTS synthesis completed. Output: '{voice_file}', Subtitle data type: {type(subtitle_data)}")

    except Exception as e:
        logger.error(f"TTS synthesis failed for voice '{voice_name}': {e}", exc_info=True)
        # Clean up potentially empty/failed output file
        if os.path.exists(voice_file):
            try:
                if os.path.getsize(voice_file) == 0: # Check if file is empty
                    os.remove(voice_file)
                    logger.info(f"Removed empty/failed output file: '{voice_file}'")
            except OSError as rm_err:
                logger.error(f"Error removing failed output file '{voice_file}': {rm_err}")
        return None

    return subtitle_data


def _format_text(text: str) -> str:
    """
    Basic text formatting: replaces certain special characters with spaces and strips whitespace.
    """
    # text = text.replace("\n", " ") # Original was commented out, keeping it that way
    text = text.replace("[", " ")
    text = text.replace("]", " ")
    text = text.replace("(", " ")
    text = text.replace(")", " ")
    text = text.replace("{", " ")
    text = text.replace("}", " ")
    text = text.strip()
    return text


def create_subtitle(sub_maker: Any, text: str, subtitle_file: str):
    """
    Generates an SRT subtitle file from subtitle data (typically a SubMaker object).

    This function processes subtitle data, which is expected to have `offset` and `subs`
    attributes (like `edge_tts.SubMaker`), aligns it with punctuated segments of the
    original text, and writes it to an SRT file.

    Args:
        sub_maker: The subtitle data object. Expected to have `offset` (list of
                   (start_100ns, end_100ns) tuples) and `subs` (list of text segments).
                   If not compatible, a warning is logged and the function exits.
        text: The original full text used for TTS, used for matching subtitle segments.
        subtitle_file: The path to save the generated SRT subtitle file.
    """
    if not hasattr(sub_maker, 'offset') or not hasattr(sub_maker, 'subs'):
        logger.warning(f"create_subtitle received subtitle data of type {type(sub_maker)} which is not SubMaker-like. Skipping subtitle creation.")
        return

    formatted_text = _format_text(text)

    # This requires mktimestamp from edge_tts.submaker
    # This import is fine here as this function is specifically for SubMaker-like objects.
    from edge_tts.submaker import mktimestamp

    def srt_formatter(idx: int, start_time_sec: float, end_time_sec: float, sub_text: str) -> str:
        """Formats a single subtitle entry in SRT format."""
        start_t = mktimestamp(start_time_sec).replace(".", ",")
        end_t = mktimestamp(end_time_sec).replace(".", ",")
        return f"{idx}\n{start_t} --> {end_t}\n{sub_text}\n"

    current_sub_start_time_100ns = -1.0
    srt_items = []
    srt_idx = 0
    script_lines = utils.split_string_by_punctuations(formatted_text)
    current_raw_sub_line = ""

    try:
        if not sub_maker.offset or not sub_maker.subs:
            logger.warning("SubMaker object has no offset or subs. Cannot create subtitle file.")
            return

        for _, (offset_100ns, sub_text_segment) in enumerate(zip(sub_maker.offset, sub_maker.subs)):
            start_100ns, end_100ns = offset_100ns
            if current_sub_start_time_100ns < 0:
                current_sub_start_time_100ns = start_100ns

            unscaped_sub_text = unescape(sub_text_segment)
            current_raw_sub_line += unscaped_sub_text

            matched_script_line_text = ""
            if srt_idx < len(script_lines):
                target_script_line = script_lines[srt_idx]
                if target_script_line in current_raw_sub_line:
                    matched_script_line_text = target_script_line
                elif any(p in unscaped_sub_text for p in ".!?。！？"):
                     matched_script_line_text = current_raw_sub_line

            if matched_script_line_text:
                srt_idx += 1
                line = srt_formatter(
                    idx=srt_idx,
                    start_time_sec=current_sub_start_time_100ns / 10_000_000.0,
                    end_time_sec=end_100ns / 10_000_000.0,
                    sub_text=matched_script_line_text.strip(),
                )
                srt_items.append(line)
                current_sub_start_time_100ns = -1.0
                current_raw_sub_line = ""

        if current_raw_sub_line and srt_idx < len(script_lines) and current_sub_start_time_100ns >=0:
            srt_idx += 1
            last_end_time_100ns = sub_maker.offset[-1][1] if sub_maker.offset else current_sub_start_time_100ns + 10_000_000
            line = srt_formatter(
                idx=srt_idx,
                start_time_sec=current_sub_start_time_100ns / 10_000_000.0,
                end_time_sec=last_end_time_100ns / 10_000_000.0,
                sub_text=script_lines[srt_idx-1].strip()
            )
            srt_items.append(line)

        if srt_items:
            with open(subtitle_file, "w", encoding="utf-8") as file:
                file.write("\n".join(srt_items) + "\n")
            try:
                subtitles.file_to_subtitles(subtitle_file, encoding="utf-8")
                logger.info(f"Subtitle file created and validated: '{subtitle_file}'")
            except Exception as e:
                logger.error(f"Failed to validate generated subtitle file '{subtitle_file}': {str(e)}")
                if os.path.exists(subtitle_file):
                    os.remove(subtitle_file)
        else:
            logger.warning(
                f"No subtitle items generated for '{subtitle_file}'. Alignment with script lines might have failed."
            )

    except Exception as e:
        logger.error(f"Failed to create subtitle file '{subtitle_file}': {e}", exc_info=True)


def get_audio_duration(sub_maker: Any) -> float:
    """
    Calculates the total audio duration from a SubMaker-like object.

    Args:
        sub_maker: A subtitle data object, expected to have an `offset` attribute
                   which is a list of (start_time_100ns, end_time_100ns) tuples.

    Returns:
        The total duration in seconds. Returns 0.0 if duration cannot be determined.
    """
    if not hasattr(sub_maker, 'offset') or not sub_maker.offset:
        logger.warning(f"get_audio_duration received data of type {type(sub_maker)} or empty offset. Cannot determine duration.")
        return 0.0
    try:
        # Duration is the end time of the last subtitle segment
        last_segment_end_time_100ns = sub_maker.offset[-1][1]
        return last_segment_end_time_100ns / 10_000_000.0 # Convert 100ns to seconds
    except (IndexError, TypeError, AttributeError) as e:
        logger.warning(f"Could not determine audio duration from SubMaker object: {e}")
        return 0.0


if __name__ == "__main__":
    # Example of using the new tts function (for testing)
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set for GoogleCloudTTS if used.
    # Ensure Azure/SiliconFlow keys/regions are in app.config.config if those are tested.

    logger.info("Starting TTS test in __main__")
    temp_dir = utils.storage_dir("temp")
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    test_text = "Hello, this is a test of the new TTS system. One, two, three."
    test_text_chinese = "你好，这是一个新的TTS系统测试。一，二，三。"

    # Define some test voices with known or expected prefixes/formats
    # Replace with actual available voice names for each provider for thorough testing
    test_scenarios = [
        # {
        #     "voice_name": "google:en-US-Standard-A", # Example, replace with actual if testing Google
        #     "text": test_text,
        #     "rate": 1.0,
        #     "volume": 1.0, # For Google, this will be mapped to pitch
        #     "file": os.path.join(temp_dir, "test_google.mp3")
        # },
        {
            "voice_name": "en-US-JennyNeural-Female", # Azure voice
            "text": test_text,
            "rate": 1.0,
            "volume": 1.0,
            "file": os.path.join(temp_dir, "test_azure_jenny.mp3")
        },
        # {
        #     "voice_name": "zh-CN-XiaoxiaoNeural-Female", # Azure voice (example)
        #     "text": test_text_chinese,
        #     "rate": 1.0,
        #     "volume": 1.0,
        #     "file": os.path.join(temp_dir, "test_azure_xiaoxiao.mp3")
        # },
        # {
        #     "voice_name": "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male", # SiliconFlow
        #     "text": test_text,
        #     "rate": 1.0,
        #     "volume": 1.0, # For SiliconFlow, this maps to gain
        #     "file": os.path.join(temp_dir, "test_siliconflow_alex.mp3")
        # },
    ]

    for scenario in test_scenarios:
        logger.info(f"Testing scenario: {scenario['voice_name']}")
        subtitle_data = None
        try:
            subtitle_data = tts(
                text=scenario["text"],
                voice_name=scenario["voice_name"],
                voice_rate=scenario["rate"],
                voice_file=scenario["file"],
                voice_volume=scenario["volume"],
            )

            if os.path.exists(scenario["file"]) and os.path.getsize(scenario["file"]) > 0:
                logger.success(f"Successfully created audio file: {scenario['file']}")
            else:
                logger.error(f"Failed to create audio file or file is empty: {scenario['file']}")

            if subtitle_data:
                logger.info(f"Subtitle data received: {type(subtitle_data)}")
                # If it's a SubMaker-like object, try to create subtitles
                if hasattr(subtitle_data, 'offset') and hasattr(subtitle_data, 'subs'):
                    subtitle_file_path = scenario["file"] + ".srt"
                    create_subtitle(sub_maker=subtitle_data, text=scenario["text"], subtitle_file=subtitle_file_path)
                    if os.path.exists(subtitle_file_path):
                        logger.success(f"Successfully created subtitle file: {subtitle_file_path}")
                    else:
                        logger.warning(f"Subtitle file not created: {subtitle_file_path}")

                    audio_dur = get_audio_duration(subtitle_data)
                    logger.info(f"Estimated audio duration from subs: {audio_dur}s")
                else: # Google timepoints or other format
                     logger.info(f"Raw subtitle data: {subtitle_data}")
            else:
                logger.warning("No subtitle data returned.")

        except Exception as e:
            logger.error(f"Error during TTS test for {scenario['voice_name']}: {e}", exc_info=True)
        logger.info("-" * 30)

    logger.info("TTS test in __main__ finished.")
