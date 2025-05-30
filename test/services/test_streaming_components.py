import unittest
from unittest.mock import patch, MagicMock, PropertyMock, call
import subprocess
import os
import sys
from pathlib import Path
import time

# Add project root to Python path to allow imports from app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from loguru import logger

# Assuming these are the correct paths after project structuring
from app.services.streaming_interface import StreamConfig
from app.services.ffmpeg_manager import FFmpegManager
from app.services.youtube_manager import YouTubeManager, GOOGLE_API_LIBS_AVAILABLE
from app.services.streaming_orchestrator import StreamingOrchestrator

# Disable logger for tests to keep output clean, or configure to a test log file
logger.remove()
logger.add(sys.stderr, level="ERROR") # Or "CRITICAL" to suppress almost all logs


class TestFFmpegManager(unittest.TestCase):
    def setUp(self):
        self.test_output_dir = "test_temp_output"
        os.makedirs(self.test_output_dir, exist_ok=True)

        self.base_config = StreamConfig(
            stream_key="test_key",
            rtmp_url="rtmp://fake.server/live",
            resolution="1280x720",
            fps=30,
            video_bitrate="2000k",
            audio_bitrate="128k",
            ffmpeg_input_source=f"lavfi:testsrc=size=1280x720:rate=30:duration=1" # Short duration for tests
        )
        # Mock app.config.config.streaming for FFmpegManager's ffmpeg_path
        self.mock_app_config = patch('app.services.ffmpeg_manager.app_global_config').start()
        self.mock_app_config.streaming.get.return_value = "ffmpeg" # Default path for tests

    def tearDown(self):
        patch.stopall()
        if os.path.exists(self.test_output_dir):
            for f in os.listdir(self.test_output_dir):
                os.remove(os.path.join(self.test_output_dir, f))
            os.rmdir(self.test_output_dir)

    def test_build_ffmpeg_command_basic(self):
        manager = FFmpegManager(config=self.base_config)
        command = manager.build_ffmpeg_command()

        self.assertIn("ffmpeg", command)
        self.assertIn(self.base_config.ffmpeg_input_source, command)
        self.assertIn(f"{self.base_config.rtmp_url}/{self.base_config.stream_key}", command)
        self.assertIn("libx264", command)
        self.assertIn("aac", command)
        self.assertIn(self.base_config.resolution, command)
        self.assertIn(str(self.base_config.fps), command)

    def test_build_ffmpeg_command_file_input(self):
        config = self.base_config._replace(ffmpeg_input_source="test_input.mp4")
        manager = FFmpegManager(config=config)
        # Mock os.path.exists for this specific case
        with patch('os.path.exists', return_value=True):
            command = manager.build_ffmpeg_command()
        self.assertIn("-re", command)
        self.assertIn("-i", command)
        self.assertIn("test_input.mp4", command)

    @patch('subprocess.Popen')
    def test_start_process_success(self, mock_popen):
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.poll.return_value = None # Simulate running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager = FFmpegManager(config=self.base_config)
        self.assertTrue(manager.start())
        mock_popen.assert_called_once()
        self.assertTrue(manager.is_running())
        self.assertEqual(manager.ffmpeg_process, mock_process)

    @patch('subprocess.Popen')
    @patch('time.sleep') # Mock time.sleep to speed up test
    def test_start_process_immediate_failure(self, mock_sleep, mock_popen):
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.poll.return_value = 1 # Simulate immediate termination
        mock_process.communicate.return_value = (b"stdout error", b"stderr error")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process

        manager = FFmpegManager(config=self.base_config)
        self.assertFalse(manager.start())
        mock_popen.assert_called_once()
        self.assertFalse(manager.is_running())
        self.assertIsNone(manager.ffmpeg_process)

    @patch('subprocess.Popen')
    def test_stop_process(self, mock_popen):
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.poll.return_value = None # Simulate running
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager = FFmpegManager(config=self.base_config)
        manager.start() # Starts the mocked process
        self.assertTrue(manager.is_running())

        manager.stop()
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=5)
        # mock_process.kill would be called if wait timed out, not testing that path here for simplicity
        self.assertFalse(manager.is_running())
        self.assertIsNone(manager.ffmpeg_process)

    def test_is_running(self):
        manager = FFmpegManager(config=self.base_config)
        self.assertFalse(manager.is_running()) # No process yet

        # Simulate process running
        manager.ffmpeg_process = MagicMock(spec=subprocess.Popen)
        manager.ffmpeg_process.poll.return_value = None
        self.assertTrue(manager.is_running())

        # Simulate process stopped
        manager.ffmpeg_process.poll.return_value = 0
        self.assertFalse(manager.is_running())


@unittest.skipIf(not GOOGLE_API_LIBS_AVAILABLE, "Google API client libraries not installed, skipping YouTubeManager tests")
class TestYouTubeManager(unittest.TestCase):
    def setUp(self):
        self.mock_build_service = patch('app.services.youtube_manager.build_google_api_service').start()
        self.mock_youtube_service_instance = MagicMock()
        self.mock_build_service.return_value = self.mock_youtube_service_instance

        # Mock os.environ.get for GOOGLE_APPLICATION_CREDENTIALS to be initially None
        self.mock_os_environ = patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": ""}, clear=True).start()

    def tearDown(self):
        patch.stopall()

    @patch('google.oauth2.service_account.Credentials.from_service_account_file')
    def test_authentication_service_account_env_var(self, mock_from_sa_file):
        mock_credentials = MagicMock()
        mock_from_sa_file.return_value = mock_credentials

        # Simulate GOOGLE_APPLICATION_CREDENTIALS being set
        with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": "dummy_sa_path.json"}):
            yt_manager = YouTubeManager()

        mock_from_sa_file.assert_called_once_with("dummy_sa_path.json", scopes=YOUTUBE_FULL_SCOPE)
        self.mock_build_service.assert_called_once_with("youtube", "v3", credentials=mock_credentials)
        self.assertEqual(yt_manager.youtube_service, self.mock_youtube_service_instance)

    def test_authentication_api_key(self):
        yt_manager = YouTubeManager(api_key="test_api_key")
        self.mock_build_service.assert_called_once_with("youtube", "v3", developerKey="test_api_key")
        self.assertEqual(yt_manager.youtube_service, self.mock_youtube_service_instance)

    def test_get_live_stream_status_success(self):
        mock_list_request = MagicMock()
        mock_list_response = {
            "items": [{
                "id": "test_stream_id",
                "snippet": {"title": "Test Stream"},
                "status": {"streamStatus": "active", "healthStatus": {"status": "good"}},
                "cdn": {"ingestionInfo": {"ingestionAddress": "rtmp://...", "streamName": "key"}, "frameRate": "30fps", "resolution": "1080p"}
            }]
        }
        mock_list_request.execute.return_value = mock_list_response
        self.mock_youtube_service_instance.liveStreams().list.return_value = mock_list_request

        yt_manager = YouTubeManager(api_key="fake_key") # Assume auth is successful
        status = yt_manager.get_live_stream_status("test_stream_id")

        self.assertTrue(status["is_live"])
        self.assertEqual(status["raw_status"], "active")
        self.assertEqual(status["health"], "good")

    def test_get_live_stream_status_not_found(self):
        mock_list_request = MagicMock()
        mock_list_request.execute.return_value = {"items": []} # No stream found
        self.mock_youtube_service_instance.liveStreams().list.return_value = mock_list_request

        yt_manager = YouTubeManager(api_key="fake_key")
        status = yt_manager.get_live_stream_status("non_existent_id")

        self.assertFalse(status["is_live"])
        self.assertEqual(status["raw_status"], "not_found")


class TestStreamingOrchestrator(unittest.TestCase):
    def setUp(self):
        self.stream_config = StreamConfig(
            stream_key="test_key",
            rtmp_url="rtmp://fake.server/live",
            resolution="1280x720",
            fps=30,
            video_bitrate="2M",
            audio_bitrate="128k",
            ffmpeg_input_source="lavfi:testsrc",
            youtube_live_stream_id="yt_stream_id_123"
        )

        # Mock the managers that StreamingOrchestrator will instantiate
        self.ffmpeg_manager_patch = patch('app.services.streaming_orchestrator.FFmpegManager')
        self.mock_ffmpeg_manager_class = self.ffmpeg_manager_patch.start()
        self.mock_ffmpeg_instance = MagicMock(spec=FFmpegManager)
        self.mock_ffmpeg_manager_class.return_value = self.mock_ffmpeg_instance

        self.youtube_manager_patch = patch('app.services.streaming_orchestrator.YouTubeManager')
        self.mock_youtube_manager_class = self.youtube_manager_patch.start()
        self.mock_youtube_instance = MagicMock(spec=YouTubeManager)
        self.mock_youtube_manager_class.return_value = self.mock_youtube_instance

        # Mock app_config for orchestrator's YouTubeManager instantiation
        self.mock_app_config_orchestrator = patch('app.services.streaming_orchestrator.app_global_config').start()
        self.mock_app_config_orchestrator.streaming = {
            "youtube_api_key": None,
            "youtube_client_secrets_file": None,
            "youtube_credentials_file": None,
            "youtube_service_account_json_path": None, # Forcing it to rely on env or default for this test
        }


    def tearDown(self):
        patch.stopall()

    def test_start_stream_success(self):
        self.mock_ffmpeg_instance.start.return_value = True
        self.mock_youtube_instance.get_live_stream_status.return_value = {"raw_status": "ready", "is_live": False}

        orchestrator = StreamingOrchestrator(config=self.stream_config)
        orchestrator.start_stream()

        self.mock_ffmpeg_manager_class.assert_called_once_with(config=self.stream_config, logger_instance=orchestrator.logger)
        self.mock_ffmpeg_instance.start.assert_called_once()
        self.assertTrue(orchestrator._is_active)
        if GOOGLE_API_LIBS_AVAILABLE:
             self.mock_youtube_instance.get_live_stream_status.assert_called_with(self.stream_config.youtube_live_stream_id)


    def test_start_stream_ffmpeg_failure(self):
        self.mock_ffmpeg_instance.start.return_value = False

        orchestrator = StreamingOrchestrator(config=self.stream_config)
        orchestrator.start_stream()

        self.mock_ffmpeg_instance.start.assert_called_once()
        self.assertFalse(orchestrator._is_active)

    def test_stop_stream(self):
        # Simulate stream being active
        self.mock_ffmpeg_instance.is_running.return_value = True
        self.mock_ffmpeg_instance.start.return_value = True # Ensure it can "start"

        orchestrator = StreamingOrchestrator(config=self.stream_config)
        orchestrator.start_stream() # Sets up ffmpeg_manager instance
        orchestrator.stop_stream()

        self.mock_ffmpeg_instance.stop.assert_called_once()
        self.assertFalse(orchestrator._is_active)
        self.assertIsNone(orchestrator.ffmpeg_manager) # Ensure manager is cleared

    def test_get_stream_status_ffmpeg_running_youtube_live(self):
        self.mock_ffmpeg_instance.is_running.return_value = True
        self.mock_ffmpeg_instance.pid = 1234
        self.mock_youtube_instance.get_live_stream_status.return_value = {"raw_status": "active", "is_live": True, "health": "good"}

        orchestrator = StreamingOrchestrator(config=self.stream_config)
        orchestrator.ffmpeg_manager = self.mock_ffmpeg_instance # Manually assign started manager

        status = orchestrator.get_stream_status()

        self.assertTrue(status['is_active'])
        self.assertTrue(status['ffmpeg_running'])
        self.assertEqual(status['ffmpeg_pid'], 1234)
        self.assertEqual(status['youtube_status']['raw_status'], "active")

    def test_get_stream_status_no_youtube_id(self):
        config_no_yt_id = self.stream_config._replace(youtube_live_stream_id=None)
        self.mock_ffmpeg_instance.is_running.return_value = True

        orchestrator = StreamingOrchestrator(config=config_no_yt_id)
        orchestrator.ffmpeg_manager = self.mock_ffmpeg_instance

        status = orchestrator.get_stream_status()
        self.assertTrue(status['is_active']) # Active due to FFmpeg
        self.assertTrue(status['ffmpeg_running'])
        if GOOGLE_API_LIBS_AVAILABLE:
            self.assertIn("Not checked", status['youtube_status'])
        else:
            self.assertIn("YouTubeManager not available", status['youtube_status'])


    def test_update_configuration_stream_running(self):
        # Simulate stream is running
        self.mock_ffmpeg_instance.is_running.return_value = True
        self.mock_ffmpeg_instance.start.return_value = True # For the restart

        orchestrator = StreamingOrchestrator(config=self.stream_config)
        orchestrator.ffmpeg_manager = self.mock_ffmpeg_instance # Assume it's running

        new_config = self.stream_config._replace(fps=60)
        orchestrator.update_configuration(new_config)

        self.mock_ffmpeg_instance.stop.assert_called_once()
        # FFmpegManager should be re-instantiated, so the start call is on the new instance
        self.assertEqual(self.mock_ffmpeg_manager_class.call_count, 2) # Once in init, once in start_stream after update
        self.assertTrue(self.mock_ffmpeg_manager_class.return_value.start.called) # Check start on the (new) instance
        self.assertEqual(orchestrator.config.fps, 60)


if __name__ == '__main__':
    unittest.main()

```
