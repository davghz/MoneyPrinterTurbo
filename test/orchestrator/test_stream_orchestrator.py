import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import tempfile
import json
import os
import threading
import time # For run_loop tests

# Add project root to sys.path to allow direct import of app modules
import sys
# This assumes 'test' is a top-level directory alongside 'app' or 'main.py' is in root
# Adjust if your project structure is different
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from app.orchestrator.stream_orchestrator import StreamOrchestrator
from app.services.streaming_interface import StreamConfig # Needed for assertions

# Suppress most logger output during tests
patch('loguru.logger.add', lambda *args, **kwargs: None).start()
patch('loguru.logger.success', lambda *args, **kwargs: None).start()
patch('loguru.logger.info', lambda *args, **kwargs: None).start()
patch('loguru.logger.warning', lambda *args, **kwargs: None).start()
# patch('loguru.logger.error', lambda *args, **kwargs: None).start() # Keep errors for debugging tests
# patch('loguru.logger.critical', lambda *args, **kwargs: None).start()

class TestStreamOrchestrator(unittest.TestCase):

    def _create_temp_config_file(self, config_data: dict) -> str:
        """Helper to create a temporary JSON config file."""
        try:
            temp_file = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding='utf-8')
            json.dump(config_data, temp_file)
            temp_file.close()
            self.addCleanup(lambda: os.remove(temp_file.name) if os.path.exists(temp_file.name) else None)
            return temp_file.name
        except Exception as e:
            # Fallback if NamedTemporaryFile has issues on some systems, e.g. Windows permissions
            # This is less ideal as it doesn't guarantee unique names as well.
            dummy_dir = os.path.join(project_root, "test_temp_configs")
            os.makedirs(dummy_dir, exist_ok=True)
            temp_file_path = os.path.join(dummy_dir, f"temp_config_{time.time_ns()}.json")
            with open(temp_file_path, "w", encoding='utf-8') as f:
                json.dump(config_data, f)
            self.addCleanup(lambda: os.remove(temp_file_path) if os.path.exists(temp_file_path) else None)
            return temp_file_path


    def setUp(self):
        """Set up for test cases."""
        # Patch external dependencies
        self.mock_ffmpeg_manager_class = patch('app.orchestrator.stream_orchestrator.FFmpegManager').start()
        self.mock_youtube_manager_class = patch('app.orchestrator.stream_orchestrator.YouTubeManager').start()

        # Store mock instances
        self.mock_ffmpeg_instance = self.mock_ffmpeg_manager_class.return_value
        self.mock_youtube_instance = self.mock_youtube_manager_class.return_value

        # Default valid config data (can be overridden in specific tests)
        self.default_config_data = {
            "global_settings": {
                "youtube_rtmp_url": "rtmp://fake.youtube.com/live2",
                "youtube_stream_key": "test_stream_key",
                "default_video_resolution": "1920x1080",
                "default_video_bitrate": "4000k",
                "default_audio_bitrate": "128k",
                "default_fps": 30,
                "ffmpeg_path": "/usr/bin/ffmpeg",
                "log_level": "DEBUG"
            },
            "playlists": [
                {
                    "id": "p1_static_loop",
                    "name": "Playlist 1 (Static, Loop)",
                    "type": "static",
                    "items": ["gs://bucket/item1.mp3", "gs://bucket/item2.aac"],
                    "loop": True
                },
                {
                    "id": "p2_static_noloop",
                    "name": "Playlist 2 (Static, No Loop)",
                    "type": "static",
                    "items": ["gs://bucket/item3.wav"],
                    "loop": False
                },
                {
                    "id": "p3_dynamic",
                    "name": "Playlist 3 (Dynamic)",
                    "type": "dynamic_rule",
                    "rules": {"genre": "electronic"}
                }
            ],
            "schedule": [
                {"playlist_id": "p1_static_loop", "duration_minutes": 10},
                {"playlist_id": "p2_static_noloop"}
            ],
            "rotation": {
                "enabled": True,
                "playlist_ids": ["p1_static_loop", "p2_static_noloop"],
                "rotate_every_minutes": 30
            },
            "fallback": {
                "playlist_id": "p1_static_loop" # Using p1 as fallback for testing
            }
        }
        self.valid_config_file_path = self._create_temp_config_file(self.default_config_data)

        # Ensure patches are stopped after each test method.
        # self.addCleanup(patch.stopall) # This is often cleaner than stopping one by one if many patches
                                        # but can sometimes conflict if patches are started in setUpClass
                                        # For now, let's stop them explicitly if needed or rely on start() context management.
                                        # The patch().start() returns a mock, addCleanup can use its .stop()
        self.addCleanup(self.mock_ffmpeg_manager_class.stop)
        self.addCleanup(self.mock_youtube_manager_class.stop)


    # --- Test Configuration Loading ---
    def test_load_config_success(self):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)
        self.assertIsNotNone(orchestrator.config)
        self.assertEqual(orchestrator.config["global_settings"]["ffmpeg_path"], "/usr/bin/ffmpeg")
        self.assertTrue(orchestrator.ffmpeg_manager is not None) # Check if managers were initialized

    def test_load_config_file_not_found(self):
        orchestrator = StreamOrchestrator(config_file_path="non_existent_file.json")
        self.assertIsNone(orchestrator.config)
        self.assertIsNone(orchestrator.ffmpeg_manager) # Managers should not init if config fails

    @patch('json.load')
    def test_load_config_invalid_json(self, mock_json_load):
        mock_json_load.side_effect = json.JSONDecodeError("Error", "doc", 0)
        # Need to mock open as well for this specific json.load side effect test
        with patch('builtins.open', mock_open(read_data="invalid json data")):
            orchestrator = StreamOrchestrator(config_file_path="dummy_path_for_invalid_json.json")
            self.assertIsNone(orchestrator.config)

    def test_load_config_missing_essential_keys(self):
        bad_config_data = {"playlists": [], "fallback": {}} # Missing global_settings
        bad_config_file = self._create_temp_config_file(bad_config_data)
        orchestrator = StreamOrchestrator(config_file_path=bad_config_file)
        self.assertIsNone(orchestrator.config)

        bad_config_data_2 = {"global_settings": {}, "fallback": {}} # Missing playlists
        bad_config_file_2 = self._create_temp_config_file(bad_config_data_2)
        orchestrator_2 = StreamOrchestrator(config_file_path=bad_config_file_2)
        self.assertIsNone(orchestrator_2.config)

        bad_config_data_3 = {"global_settings": {}, "playlists": []} # Missing fallback
        bad_config_file_3 = self._create_temp_config_file(bad_config_data_3)
        orchestrator_3 = StreamOrchestrator(config_file_path=bad_config_file_3)
        self.assertIsNone(orchestrator_3.config)

    # --- Test Manager Initialization ---
    def test_initialize_managers(self):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)
        self.mock_ffmpeg_manager_class.assert_called_once_with(
            ffmpeg_exe_path=self.default_config_data["global_settings"]["ffmpeg_path"],
            logger_instance=orchestrator.logger # orchestrator.logger is a BoundLogger, check type or content
        )
        self.mock_youtube_manager_class.assert_called_once_with(
            api_key=self.default_config_data["global_settings"].get('youtube_api_key'),
            client_secrets_file=self.default_config_data["global_settings"].get('youtube_client_secrets_file'),
            credentials_file=self.default_config_data["global_settings"].get('youtube_credentials_file'),
            logger_instance=orchestrator.logger
        )
        self.assertIsNotNone(orchestrator.ffmpeg_manager)
        self.assertIsNotNone(orchestrator.youtube_manager)

    # --- Test Playlist and Item Selection Logic ---
    def test_get_playlist_by_id(self):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)
        playlist = orchestrator._get_playlist_by_id("p1_static_loop")
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist["name"], "Playlist 1 (Static, Loop)")

        playlist_none = orchestrator._get_playlist_by_id("non_existent_id")
        self.assertIsNone(playlist_none)

    def test_determine_playlist_from_schedule_first(self):
        config_data = self.default_config_data.copy()
        # Ensure schedule is prioritized
        config_data["schedule"] = [{"playlist_id": "p2_static_noloop"}]
        config_data["rotation"] = {"enabled": True, "playlist_ids": ["p1_static_loop"]}
        temp_config_file = self._create_temp_config_file(config_data)

        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        playlist_id = orchestrator._determine_playlist_from_schedule_or_rotation()
        self.assertEqual(playlist_id, "p2_static_noloop")

    def test_determine_playlist_from_rotation_if_no_schedule(self):
        config_data = self.default_config_data.copy()
        config_data["schedule"] = [] # Empty schedule
        config_data["rotation"] = {"enabled": True, "playlist_ids": ["p1_static_loop", "p2_static_noloop"]}
        temp_config_file = self._create_temp_config_file(config_data)

        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        playlist_id = orchestrator._determine_playlist_from_schedule_or_rotation()
        self.assertEqual(playlist_id, "p1_static_loop") # Should pick first from rotation

    def test_determine_playlist_none_if_no_schedule_or_rotation(self):
        config_data = self.default_config_data.copy()
        config_data["schedule"] = []
        config_data["rotation"] = {"enabled": False, "playlist_ids": []} # Disabled/empty rotation
        temp_config_file = self._create_temp_config_file(config_data)

        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        playlist_id = orchestrator._determine_playlist_from_schedule_or_rotation()
        self.assertIsNone(playlist_id)

    def test_select_next_item_static_playlist_loop(self):
        config_data = self.default_config_data.copy()
        # Use only p1_static_loop for this test by modifying schedule
        config_data["schedule"] = [{"playlist_id": "p1_static_loop"}]
        config_data["rotation"] = {"enabled": False}
        temp_config_file = self._create_temp_config_file(config_data)
        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)

        items_in_p1 = config_data["playlists"][0]["items"]

        # First call: selects p1, then first item
        self.assertEqual(orchestrator._select_next_item_logic(), items_in_p1[0])
        self.assertEqual(orchestrator.current_playlist_config["id"], "p1_static_loop")
        self.assertEqual(orchestrator.current_playlist_item_index, 0)

        # Second call: second item from p1
        self.assertEqual(orchestrator._select_next_item_logic(), items_in_p1[1])
        self.assertEqual(orchestrator.current_playlist_item_index, 1)

        # Third call: loops back to first item from p1
        self.assertEqual(orchestrator._select_next_item_logic(), items_in_p1[0])
        self.assertEqual(orchestrator.current_playlist_item_index, 0)

    def test_select_next_item_static_playlist_no_loop_then_schedule(self):
        config_data = self.default_config_data.copy()
        # Schedule: p2 (no loop, 1 item), then p1 (loop, 2 items)
        config_data["schedule"] = [
            {"playlist_id": "p2_static_noloop"},
            {"playlist_id": "p1_static_loop"}
        ]
        config_data["rotation"] = {"enabled": False}
        temp_config_file = self._create_temp_config_file(config_data)
        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)

        item_in_p2 = config_data["playlists"][1]["items"][0]
        items_in_p1 = config_data["playlists"][0]["items"]

        # Call 1: Selects p2, then its first (and only) item
        self.assertEqual(orchestrator._select_next_item_logic(), item_in_p2)
        self.assertEqual(orchestrator.current_playlist_config["id"], "p2_static_noloop")
        self.assertEqual(orchestrator.current_playlist_item_index, 0)

        # Call 2: p2 ends, should select p1, then its first item
        self.assertEqual(orchestrator._select_next_item_logic(), items_in_p1[0])
        self.assertEqual(orchestrator.current_playlist_config["id"], "p1_static_loop")
        self.assertEqual(orchestrator.current_playlist_item_index, 0)

        # Call 3: second item from p1
        self.assertEqual(orchestrator._select_next_item_logic(), items_in_p1[1])
        self.assertEqual(orchestrator.current_playlist_item_index, 1)

    def test_select_next_item_no_valid_items_available(self):
        config_data = { # Minimal config with no valid items/schedule/rotation
            "global_settings": self.default_config_data["global_settings"],
            "playlists": [{"id": "empty_p", "type": "static", "items": []}], # empty playlist
            "schedule": [],
            "rotation": {"enabled": False},
            "fallback": {"playlist_id": "empty_p"} # Fallback is also empty
        }
        temp_config_file = self._create_temp_config_file(config_data)
        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        self.assertIsNone(orchestrator._select_next_item_logic())

    # --- Test Fallback Logic ---
    def test_get_fallback_item_success(self):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)
        # Fallback playlist p1_static_loop has "gs://bucket/item1.mp3" as first item
        expected_fallback_item = self.default_config_data["playlists"][0]["items"][0]
        self.assertEqual(orchestrator._get_fallback_item(), expected_fallback_item)

    def test_get_fallback_item_no_fallback_playlist_id(self):
        config_data = self.default_config_data.copy()
        config_data["fallback"] = {} # No playlist_id
        temp_config_file = self._create_temp_config_file(config_data)
        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        self.assertIsNone(orchestrator._get_fallback_item())

    def test_get_fallback_item_playlist_not_found_or_invalid(self):
        config_data = self.default_config_data.copy()
        config_data["fallback"] = {"playlist_id": "non_existent_fallback"}
        temp_config_file = self._create_temp_config_file(config_data)
        orchestrator = StreamOrchestrator(config_file_path=temp_config_file)
        self.assertIsNone(orchestrator._get_fallback_item())

        config_data["fallback"] = {"playlist_id": "p3_dynamic"} # Dynamic playlist as fallback
        config_data["playlists"].append({"id": "empty_fallback", "type": "static", "items": []})
        config_data["fallback"] = {"playlist_id": "empty_fallback"} # Empty static playlist
        temp_config_file_2 = self._create_temp_config_file(config_data)
        orchestrator_2 = StreamOrchestrator(config_file_path=temp_config_file_2)
        self.assertIsNone(orchestrator_2._get_fallback_item())


    # --- Test `stop()` method ---
    def test_stop_method_signals_shutdown_and_stops_ffmpeg(self):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)
        self.mock_ffmpeg_instance.is_running.return_value = True # Simulate FFmpeg running

        orchestrator.stop()

        self.assertTrue(orchestrator.shutdown_event.is_set())
        self.mock_ffmpeg_instance.stop.assert_called_once()

    # --- High-level run_loop tests (simplified due to threading and time) ---
    # These tests will use threading.Event to signal completion from the run_loop thread or timeout.

    @patch.object(StreamOrchestrator, '_select_next_item_logic')
    def test_run_loop_plays_item_successfully(self, mock_select_item):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)

        test_gcs_path = "gs://bucket/test_item.mp3"
        mock_select_item.return_value = test_gcs_path

        self.mock_ffmpeg_instance.start.return_value = True # FFmpeg starts successfully
        # Simulate FFmpeg running for a short period then stopping
        self.mock_ffmpeg_instance.is_running.side_effect = [True, True, False]
        # self.mock_ffmpeg_instance.ffmpeg_process might be None if not set by start mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        self.mock_ffmpeg_instance.ffmpeg_process = mock_process # Ensure it's set for wait()

        loop_finished_event = threading.Event()

        def target_run_loop():
            orchestrator.run_loop()
            loop_finished_event.set() # Signal that run_loop exited

        orchestrator_thread = threading.Thread(target=target_run_loop)
        orchestrator_thread.start()

        # Let the loop run for a couple of iterations (enough for one item)
        time.sleep(0.1) # Small delay to allow loop to start and process one item

        orchestrator.stop() # Signal shutdown
        orchestrator_thread.join(timeout=5) # Wait for thread to finish

        self.assertTrue(loop_finished_event.is_set(), "run_loop did not finish in time.")

        expected_stream_config_arg = StreamConfig(
            stream_key=self.default_config_data["global_settings"]["youtube_stream_key"],
            rtmp_url=self.default_config_data["global_settings"]["youtube_rtmp_url"],
            resolution=self.default_config_data["global_settings"]["default_video_resolution"],
            fps=self.default_config_data["global_settings"]["default_fps"],
            video_bitrate=self.default_config_data["global_settings"]["default_video_bitrate"],
            audio_bitrate=self.default_config_data["global_settings"]["default_audio_bitrate"],
            ffmpeg_input_source=test_gcs_path,
            youtube_live_stream_id=self.default_config_data["global_settings"].get("youtube_live_stream_id")
        )
        self.mock_ffmpeg_instance.start.assert_called_once_with(expected_stream_config_arg)
        self.assertTrue(mock_process.wait.called)


    @patch.object(StreamOrchestrator, '_select_next_item_logic')
    @patch.object(StreamOrchestrator, '_get_fallback_item')
    def test_run_loop_ffmpeg_start_failure_triggers_fallback(self, mock_get_fallback, mock_select_item):
        orchestrator = StreamOrchestrator(config_file_path=self.valid_config_file_path)

        normal_item_path = "gs://bucket/normal_item.mp3"
        fallback_item_path = "gs://bucket/fallback_item.mp3"

        # First call to _select_next_item_logic returns normal item
        # Subsequent calls (after fallback) might happen, ensure it doesn't loop indefinitely if fallback also fails
        mock_select_item.side_effect = [normal_item_path, None, None] # Normal, then nothing for next normal attempt
        mock_get_fallback.return_value = fallback_item_path

        # FFmpeg start fails for normal item, succeeds for fallback
        self.mock_ffmpeg_instance.start.side_effect = [False, True]
        self.mock_ffmpeg_instance.is_running.side_effect = [True, True, False] # For fallback item

        mock_fallback_process = MagicMock()
        mock_fallback_process.returncode = 0

        # This setup is a bit tricky because start is called twice.
        # We need ffmpeg_process to be set correctly for the second (fallback) call.
        def set_process_on_fallback_start(*args, **kwargs):
            if args[0].ffmpeg_input_source == fallback_item_path:
                self.mock_ffmpeg_instance.ffmpeg_process = mock_fallback_process
                return True # Fallback starts
            return False # Normal item fails to start
        self.mock_ffmpeg_instance.start.side_effect = set_process_on_fallback_start

        loop_finished_event = threading.Event()
        def target_run_loop():
            orchestrator.run_loop()
            loop_finished_event.set()

        orchestrator_thread = threading.Thread(target=target_run_loop)
        orchestrator_thread.start()

        time.sleep(0.2) # Allow for initial attempt, fallback attempt
        orchestrator.stop()
        orchestrator_thread.join(timeout=5)
        self.assertTrue(loop_finished_event.is_set(), "run_loop did not finish in time for fallback test.")

        self.assertTrue(orchestrator.fallback_triggered, "Fallback should have been triggered and remained active or re-triggered.")
        mock_get_fallback.assert_called() # Was called at least once

        # Check calls to ffmpeg_manager.start
        # Call 1 (normal item)
        expected_normal_config = StreamConfig(ffmpeg_input_source=normal_item_path, **self._get_global_stream_params())
        # Call 2 (fallback item)
        expected_fallback_config = StreamConfig(ffmpeg_input_source=fallback_item_path, **self._get_global_stream_params())

        calls = self.mock_ffmpeg_instance.start.call_args_list
        self.assertTrue(len(calls) >= 2, "FFmpeg start should be called at least twice")
        self.assertEqual(calls[0][0][0], expected_normal_config) # First argument of first call
        self.assertEqual(calls[1][0][0], expected_fallback_config) # First argument of second call

    def _get_global_stream_params(self): # Helper for expected StreamConfig
        gs = self.default_config_data["global_settings"]
        return {
            "stream_key": gs["youtube_stream_key"], "rtmp_url": gs["youtube_rtmp_url"],
            "resolution": gs["default_video_resolution"], "fps": gs["default_fps"],
            "video_bitrate": gs["default_video_bitrate"], "audio_bitrate": gs["default_audio_bitrate"],
            "youtube_live_stream_id": gs.get("youtube_live_stream_id")
        }

if __name__ == "__main__":
    unittest.main()

```
