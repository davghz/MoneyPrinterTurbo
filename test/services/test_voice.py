import asyncio
import unittest
import os
import sys
from pathlib import Path
from loguru import logger

# add project root to python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import utils
from app.services import voice as vs # This now contains the main tts dispatcher
from app.services.tts_interface import TextToSpeechService
from app.services.google_cloud_tts import GoogleCloudTTS
from app.services.azure_tts_adapter import AzureTTSAdapter
from app.services.siliconflow_tts_adapter import SiliconflowTTSAdapter
from app.config import config as app_config # To check API keys for skipping tests

temp_dir = utils.storage_dir("temp")
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir, exist_ok=True)

text_en = """
What is the meaning of life? 
This question has puzzled philosophers, scientists, and thinkers of all kinds for centuries. 
Throughout history, various cultures and individuals have come up with their interpretations and beliefs around the purpose of life. 
Some say it's to seek happiness and self-fulfillment, while others believe it's about contributing to the welfare of others and making a positive impact in the world. 
Despite the myriad of perspectives, one thing remains clear: the meaning of life is a deeply personal concept that varies from one person to another. 
It's an existential inquiry that encourages us to reflect on our values, desires, and the essence of our existence.
"""

text_zh = """
预计未来3天深圳冷空气活动频繁，未来两天持续阴天有小雨，出门带好雨具；
10-11日持续阴天有小雨，日温差小，气温在13-17℃之间，体感阴凉；
12日天气短暂好转，早晚清凉；
"""

# Default voice parameters for tests - can be overridden in specific tests
voice_rate_default = 1.0
voice_volume_default = 1.0
                    
class TestVoiceServiceAdapters(unittest.TestCase):
    def setUp(self):
        # self.loop = asyncio.new_event_loop() # Not strictly needed if all adapter calls are sync
        # asyncio.set_event_loop(self.loop)
        # Ensure temp_dir exists for test outputs
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
    
    def tearDown(self):
        # self.loop.close()
        # Clean up files created during tests
        for item in os.listdir(temp_dir):
            if item.startswith("test_tts_") or item.startswith("tts-"): # prefix for test files
                try:
                    os.remove(os.path.join(temp_dir, item))
                except Exception as e:
                    logger.error(f"Error removing test file {item}: {e}")


    @unittest.skipIf(not app_config.siliconflow.get("api_key"), "SiliconFlow API key not configured")
    def test_siliconflow_adapter(self):
        adapter = SiliconflowTTSAdapter()
        voice_id = "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male" # Full prefixed name
        
        audio_file_path = os.path.join(temp_dir, f"test_tts_siliconflow_adapter_alex.mp3")
        subtitle_file_path = audio_file_path + ".srt"

        _, subtitle_data = adapter.synthesize_speech(
            text=text_en, 
            voice_id=voice_id, 
            output_filename=audio_file_path,
            voice_rate=voice_rate_default,
            voice_volume=voice_volume_default
        )
        
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data)
        if subtitle_data:
            vs.create_subtitle(sub_maker=subtitle_data, text=text_en, subtitle_file=subtitle_file_path)
            self.assertTrue(os.path.exists(subtitle_file_path))
            audio_duration = vs.get_audio_duration(subtitle_data)
            logger.info(f"Siliconflow Adapter - Voice: {voice_id}, Audio duration: {audio_duration}s")

    @unittest.skipIf(not (app_config.azure.get("speech_key") and app_config.azure.get("speech_region")), "Azure Speech key or region not configured")
    def test_azure_adapter_v1_voice(self):
        adapter = AzureTTSAdapter()
        voice_id = "en-US-JennyNeural-Female" # A V1 style voice
        
        audio_file_path = os.path.join(temp_dir, f"test_tts_azure_adapter_v1.mp3")
        subtitle_file_path = audio_file_path + ".srt"

        _, subtitle_data = adapter.synthesize_speech(
            text=text_en,
            voice_id=voice_id,
            output_filename=audio_file_path,
            voice_rate=voice_rate_default
        )
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data)
        if subtitle_data:
            vs.create_subtitle(sub_maker=subtitle_data, text=text_en, subtitle_file=subtitle_file_path)
            self.assertTrue(os.path.exists(subtitle_file_path))
            audio_duration = vs.get_audio_duration(subtitle_data)
            logger.info(f"Azure Adapter (V1 voice) - Voice: {voice_id}, Audio duration: {audio_duration}s")

    @unittest.skipIf(not (app_config.azure.get("speech_key") and app_config.azure.get("speech_region")), "Azure Speech key or region not configured")
    def test_azure_adapter_v2_voice(self):
        adapter = AzureTTSAdapter()
        voice_id = "en-US-AndrewMultilingualNeural-V2-Male" # A V2 style voice
        
        audio_file_path = os.path.join(temp_dir, f"test_tts_azure_adapter_v2.mp3")
        subtitle_file_path = audio_file_path + ".srt"
        
        _, subtitle_data = adapter.synthesize_speech(
            text=text_en,
            voice_id=voice_id,
            output_filename=audio_file_path
            # voice_rate for V2 is typically handled via SSML, not directly passed here for basic test
        )
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data)
        if subtitle_data:
            vs.create_subtitle(sub_maker=subtitle_data, text=text_en, subtitle_file=subtitle_file_path)
            self.assertTrue(os.path.exists(subtitle_file_path))
            audio_duration = vs.get_audio_duration(subtitle_data)
            logger.info(f"Azure Adapter (V2 voice) - Voice: {voice_id}, Audio duration: {audio_duration}s")

    @unittest.skipIf(not (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or app_config.google_tts.get("service_account_key_path")), "Google Cloud credentials not configured")
    def test_google_cloud_tts_adapter(self):
        try:
            adapter = GoogleCloudTTS()
        except Exception as e:
            self.skipTest(f"Skipping GoogleCloudTTS test: Failed to initialize adapter - {e}")
            return

        voice_id = app_config.google_tts.get("default_voice_name", "en-US-Wavenet-D") # Use configured default
        
        audio_file_path = os.path.join(temp_dir, f"test_tts_google_adapter.mp3")
        # Subtitle file not created by default by Google adapter's synthesize_speech in the same way
        
        _, subtitle_data = adapter.synthesize_speech(
            text=text_en,
            voice_id=voice_id, # Adapter will use its default if this is None
            output_filename=audio_file_path,
            speaking_rate=voice_rate_default,
            pitch=(voice_volume_default - 1.0) * 10.0 # Example pitch mapping
        )
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data) # Google returns list of timepoints
        self.assertIsInstance(subtitle_data, list)
        if len(text_en.strip()) > 0: # if text is not empty, expect some timepoints
             # If SSML marks were used, timepoints would be populated. Plain text might not always yield timepoints.
             # For this test, we are more interested in audio generation.
            logger.info(f"GoogleCloudTTS subtitle data (timepoints): {subtitle_data}")

        # Test get_available_voices
        available_voices = adapter.get_available_voices(language_code="en-US") # Filter for a language
        self.assertIsInstance(available_voices, list)
        self.assertTrue(len(available_voices) > 0)
        self.assertIn(voice_id, available_voices if voice_id else []) # Check if default voice is in the list if used
        logger.info(f"GoogleCloudTTS found {len(available_voices)} voices for en-US.")


class TestMainTTSDispatcher(unittest.TestCase):
    def setUp(self):
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)

    def tearDown(self):
        for item in os.listdir(temp_dir):
            if item.startswith("test_tts_dispatcher_"):
                try:
                    os.remove(os.path.join(temp_dir, item))
                except Exception as e:
                    logger.error(f"Error removing dispatcher test file {item}: {e}")
    
    @unittest.skipIf(not (app_config.azure.get("speech_key") and app_config.azure.get("speech_region")), "Azure Speech key or region not configured")
    def test_tts_dispatcher_azure(self):
        voice_id = "en-US-JennyNeural-Female" # Azure voice
        audio_file_path = os.path.join(temp_dir, "test_tts_dispatcher_azure.mp3")
        subtitle_file_path = audio_file_path + ".srt"

        subtitle_data = vs.tts(
            text=text_en,
            voice_name=voice_id,
            voice_rate=voice_rate_default,
            voice_file=audio_file_path,
            voice_volume=voice_volume_default
        )
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data)
        if subtitle_data and hasattr(subtitle_data, 'subs'): # Check if it's SubMaker-like
            vs.create_subtitle(sub_maker=subtitle_data, text=text_en, subtitle_file=subtitle_file_path)
            self.assertTrue(os.path.exists(subtitle_file_path))

    @unittest.skipIf(not app_config.siliconflow.get("api_key"), "SiliconFlow API key not configured")
    def test_tts_dispatcher_siliconflow(self):
        voice_id = "siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male"
        audio_file_path = os.path.join(temp_dir, "test_tts_dispatcher_siliconflow.mp3")
        subtitle_file_path = audio_file_path + ".srt"

        subtitle_data = vs.tts(
            text=text_en,
            voice_name=voice_id,
            voice_rate=voice_rate_default,
            voice_file=audio_file_path,
            voice_volume=voice_volume_default
        )
        self.assertTrue(os.path.exists(audio_file_path))
        self.assertIsNotNone(subtitle_data)
        if subtitle_data and hasattr(subtitle_data, 'subs'):
            vs.create_subtitle(sub_maker=subtitle_data, text=text_en, subtitle_file=subtitle_file_path)
            self.assertTrue(os.path.exists(subtitle_file_path))

    @unittest.skipIf(not (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or app_config.google_tts.get("service_account_key_path")), "Google Cloud credentials not configured")
    def test_tts_dispatcher_google(self):
        # Use a voice name known to be available or from config
        gcp_voice_name = app_config.google_tts.get("default_voice_name", "en-US-Wavenet-D")
        voice_id = f"google:{gcp_voice_name}" 
        audio_file_path = os.path.join(temp_dir, "test_tts_dispatcher_google.mp3")
        
        subtitle_data = vs.tts(
            text=text_en,
            voice_name=voice_id,
            voice_rate=voice_rate_default,
            voice_file=audio_file_path,
            voice_volume=voice_volume_default # Mapped to pitch in tts() for Google
        )
        self.assertTrue(os.path.exists(audio_file_path))
        # Google returns a list of timepoints, not a SubMaker object directly from adapter
        self.assertIsNotNone(subtitle_data) 
        self.assertIsInstance(subtitle_data, list) 
        logger.info(f"Google dispatcher test subtitle data: {subtitle_data}")


if __name__ == "__main__":
    unittest.main()