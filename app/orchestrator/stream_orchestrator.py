import json
import os
import threading # Added for shutdown_event
from typing import Any, Dict, List, Optional

from loguru import logger

# Adjust imports based on actual project structure
# Assuming 'services' is a sibling directory to 'orchestrator' within 'app'
from ..services.ffmpeg_manager import FFmpegManager
from ..services.youtube_manager import YouTubeManager
from ..services.streaming_interface import StreamConfig


class StreamOrchestrator:
    """
    Manages the overall streaming lifecycle, including loading configuration,
    initializing streaming components (FFmpeg, YouTube API), selecting content
    based on schedule/rotation, and managing the streaming process.
    """

    def __init__(self, config_file_path: str):
        """
        Initializes the StreamOrchestrator.

        Args:
            config_file_path: Path to the stream_config.json file.
        """
        self.config_file_path: str = config_file_path
        self.config: Optional[Dict[str, Any]] = None
        self.logger = logger.bind(name=self.__class__.__name__)

        self.ffmpeg_manager: Optional[FFmpegManager] = None
        self.youtube_manager: Optional[YouTubeManager] = None # For future health checks, etc.

        self.current_playlist_config: Optional[Dict[str, Any]] = None # Stores the config dict of the current playlist
        self.current_playlist_item_index: int = -1
        self.current_ffmpeg_process = None # Stores the Popen object from FFmpegManager
        self.fallback_triggered: bool = False
        self.shutdown_event = threading.Event() # For signalling the run_loop to stop

        self.logger.info(f"StreamOrchestrator initializing with config: {config_file_path}")

        if self._load_config():
            self._initialize_managers()
        else:
            self.logger.error("StreamOrchestrator initialization failed due to config loading errors.")

    def _load_config(self) -> bool:
        """
        Reads and parses the JSON configuration file.

        Performs basic validation for essential keys.

        Returns:
            True if configuration is loaded and valid, False otherwise.
        """
        self.logger.info(f"Loading stream configuration from: {self.config_file_path}")
        if not os.path.exists(self.config_file_path):
            self.logger.error(f"Configuration file not found: {self.config_file_path}")
            return False

        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON configuration: {e}")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while loading config: {e}", exc_info=True)
            return False

        # Basic validation
        if self.config:
            required_keys = ["global_settings", "playlists", "fallback"]
            for key in required_keys:
                if key not in self.config:
                    self.logger.error(f"Missing essential key '{key}' in configuration.")
                    self.config = None # Invalidate config
                    return False

            if not isinstance(self.config.get("playlists"), list):
                self.logger.error("'playlists' key must be a list.")
                self.config = None
                return False

            self.logger.success("Stream configuration loaded and validated successfully.")
            return True

        self.logger.error("Configuration is empty after loading attempt.")
        return False

    def _initialize_managers(self) -> None:
        """
        Initializes FFmpegManager and YouTubeManager based on loaded configuration.
        """
        if not self.config or "global_settings" not in self.config:
            self.logger.error("Cannot initialize managers: config or global_settings missing.")
            return

        global_settings = self.config["global_settings"]
        ffmpeg_exe_path = global_settings.get('ffmpeg_path', 'ffmpeg')

        self.logger.info(f"Initializing FFmpegManager with path: {ffmpeg_exe_path}")
        self.ffmpeg_manager = FFmpegManager(
            ffmpeg_exe_path=ffmpeg_exe_path,
            logger_instance=self.logger
        )

        self.logger.info("Initializing YouTubeManager...")
        self.youtube_manager = YouTubeManager(
            api_key=global_settings.get('youtube_api_key'), # From stream_config, not global app config
            client_secrets_file=global_settings.get('youtube_client_secrets_file'),
            credentials_file=global_settings.get('youtube_credentials_file'),
            logger_instance=self.logger
        )
        # Note: YouTubeManager might not be directly used for basic file-to-RTMP streaming initially,
        # but it's good to have for future API interactions like stream health checks.

        self.logger.success("Streaming managers initialized.")


    def _get_playlist_by_id(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a playlist configuration dictionary by its ID.

        Args:
            playlist_id: The ID of the playlist to find.

        Returns:
            The playlist dictionary if found, otherwise None.
        """
        if not self.config or "playlists" not in self.config:
            return None

        for playlist in self.config["playlists"]:
            if playlist.get("id") == playlist_id:
                return playlist
        self.logger.warning(f"Playlist with ID '{playlist_id}' not found in configuration.")
        return None

    def _determine_playlist_from_schedule_or_rotation(self) -> Optional[str]:
        """
        Determines the next playlist ID to play based on schedule or rotation.
        This is a very basic initial implementation:
        - Takes the first item from schedule if available.
        - Else, takes the first item from rotation if available and enabled.
        Does not yet handle time-based scheduling, played state, or rotation sequence.
        """
        if not self.config:
            return None

        # Priority 1: Schedule (very basic - first item)
        schedule_config = self.config.get("schedule")
        if schedule_config and isinstance(schedule_config, list) and schedule_config:
            # In a real scenario, you'd check start_time_utc, duration, and if already played.
            # For now, just grab the first one.
            first_scheduled_item = schedule_config[0]
            playlist_id = first_scheduled_item.get("playlist_id")
            if playlist_id:
                self.logger.info(f"Selected playlist '{playlist_id}' from schedule (first item).")
                return playlist_id
            else:
                self.logger.warning("First scheduled item has no 'playlist_id'.")

        # Priority 2: Rotation (very basic - first item)
        rotation_config = self.config.get("rotation")
        if rotation_config and rotation_config.get("enabled") and isinstance(rotation_config.get("playlist_ids"), list):
            rotation_playlist_ids = rotation_config["playlist_ids"]
            if rotation_playlist_ids:
                playlist_id = rotation_playlist_ids[0]
                self.logger.info(f"Selected playlist '{playlist_id}' from rotation (first item).")
                return playlist_id
            else:
                self.logger.warning("Rotation enabled but 'playlist_ids' is empty.")

        self.logger.info("No playlist determined from schedule or rotation (initial basic logic).")
        return None


    def _select_next_item_logic(self) -> Optional[str]:
        """
        Selects the next GCS path to stream based on the current playlist,
        schedule, or rotation.

        Returns:
            A GCS path string if an item is selected, otherwise None.
        """
        if not self.config:
            self.logger.error("Cannot select item: configuration not loaded.")
            return None

        # 1. Handle current playlist if active
        if self.current_playlist_config:
            playlist_type = self.current_playlist_config.get("type")
            playlist_id = self.current_playlist_config.get("id", "Unknown")

            if playlist_type == "static":
                items = self.current_playlist_config.get("items", [])
                if not items:
                    self.logger.warning(f"Current static playlist '{playlist_id}' has no items. Clearing current playlist.")
                    self.current_playlist_config = None # Move to select new playlist
                    # Fall through to select a new playlist
                else:
                    self.current_playlist_item_index += 1
                    if self.current_playlist_item_index < len(items):
                        item_gcs_path = items[self.current_playlist_item_index]
                        self.logger.info(f"Selected item {self.current_playlist_item_index + 1}/{len(items)} "
                                         f"from playlist '{playlist_id}': {item_gcs_path}")
                        return item_gcs_path
                    else: # End of playlist
                        if self.current_playlist_config.get("loop", True):
                            self.logger.info(f"Looping playlist '{playlist_id}'.")
                            self.current_playlist_item_index = 0
                            item_gcs_path = items[self.current_playlist_item_index]
                            self.logger.info(f"Selected item 1/{len(items)} (loop) "
                                             f"from playlist '{playlist_id}': {item_gcs_path}")
                            return item_gcs_path
                        else:
                            self.logger.info(f"Finished non-looping playlist '{playlist_id}'. Clearing current playlist.")
                            self.current_playlist_config = None # Mark current playlist as finished
                            self.current_playlist_item_index = -1
                            # Fall through to select a new playlist

            elif playlist_type == "dynamic_rule":
                self.logger.info(f"Playlist '{playlist_id}' is dynamic_rule. Orchestrator currently logs and skips. "
                                 "This type will be handled by the PlaylistManagerService.")
                self.current_playlist_config = None # Cannot process, clear to select new
                # Fall through

        # 2. If no current playlist (or it just finished), determine next from schedule/rotation
        if not self.current_playlist_config:
            self.logger.debug("No active playlist or current one finished. Determining next playlist...")
            next_playlist_id = self._determine_playlist_from_schedule_or_rotation()

            if next_playlist_id:
                self.current_playlist_config = self._get_playlist_by_id(next_playlist_id)
                if self.current_playlist_config:
                    self.logger.info(f"Switched to new playlist: '{self.current_playlist_config.get('name', next_playlist_id)}'")
                    self.current_playlist_item_index = -1 # Reset for the new playlist
                    # Recursively call or repeat logic to get the first item of this new playlist
                    return self._select_next_item_logic()
                else:
                    self.logger.error(f"Failed to load configuration for determined playlist ID: {next_playlist_id}")
                    # Potentially trigger fallback here in a more robust implementation
                    return None # Could not load the determined playlist
            else:
                self.logger.warning("No new playlist determined from schedule or rotation.")
                # Potentially trigger fallback here
                return None

        self.logger.debug("No item selected by _select_next_item_logic.")
        return None

    def _get_fallback_item(self) -> Optional[str]:
        """
        Retrieves the GCS path of the first item from the configured fallback playlist.
        """
        if not self.config:
            self.logger.error("Cannot get fallback item: configuration not loaded.")
            return None

        fallback_config = self.config.get('fallback', {})
        fallback_playlist_id = fallback_config.get('playlist_id')

        if not fallback_playlist_id:
            self.logger.warning("No fallback playlist_id configured.")
            return None

        fallback_playlist = self._get_playlist_by_id(fallback_playlist_id)
        if fallback_playlist and fallback_playlist.get('type') == 'static':
            items = fallback_playlist.get('items')
            if items and isinstance(items, list) and len(items) > 0:
                # For simplicity, always use the first item of the fallback playlist.
                # The main loop treats this as a single, repeating item if fallback continues.
                item_gcs_path = items[0]
                self.logger.info(f"Selected fallback item: {item_gcs_path} from playlist '{fallback_playlist_id}'")
                return item_gcs_path
            else:
                self.logger.error(f"Fallback playlist '{fallback_playlist_id}' is static but has no items or items are not a list.")
        else:
            self.logger.error(f"Fallback playlist '{fallback_playlist_id}' not found or is not of type 'static'.")

        return None

    def run_loop(self) -> None:
        """
        The main continuous loop for the orchestrator.
        Selects items, starts FFmpeg, monitors, and handles transitions/fallbacks.
        """
        self.logger.info("StreamOrchestrator run_loop starting.")
        if not self.config or not self.ffmpeg_manager:
            self.logger.critical("Orchestrator cannot run: Config or FFmpegManager not initialized.")
            return

        while not self.shutdown_event.is_set():
            gcs_path_to_play: Optional[str] = None

            if self.fallback_triggered:
                self.logger.info("In fallback mode. Attempting to get fallback item.")
                gcs_path_to_play = self._get_fallback_item()
                if not gcs_path_to_play:
                    self.logger.error("Fallback triggered, but no fallback item could be retrieved. Idling for 60s.")
                    self.shutdown_event.wait(timeout=60)
                    continue
            else: # Normal operation
                gcs_path_to_play = self._select_next_item_logic()
                if gcs_path_to_play:
                    # Successfully got a normal item, ensure fallback mode is off for this attempt
                    self.fallback_triggered = False
                else: # No normal item available
                    self.logger.warning("No items available from schedule/rotation. Triggering fallback.")
                    self.fallback_triggered = True
                    gcs_path_to_play = self._get_fallback_item()
                    if not gcs_path_to_play:
                        self.logger.error("Fallback triggered, but no fallback item available. Idling for 30s.")
                        self.shutdown_event.wait(timeout=30)
                        continue

            # If we have a GCS path (either normal or fallback)
            self.logger.info(f"Preparing to play item: {gcs_path_to_play}")

            global_settings = self.config['global_settings']
            item_stream_config = StreamConfig(
                stream_key=global_settings['youtube_stream_key'],
                rtmp_url=global_settings['youtube_rtmp_url'],
                resolution=global_settings.get('default_video_resolution', "1280x720"), # Add defaults
                fps=int(global_settings.get('default_fps', 30)),
                video_bitrate=global_settings.get('default_video_bitrate', "2000k"),
                audio_bitrate=global_settings.get('default_audio_bitrate', "128k"),
                ffmpeg_input_source=gcs_path_to_play,
                youtube_live_stream_id=global_settings.get('youtube_live_stream_id')
            )

            if self.ffmpeg_manager.is_running():
                self.logger.info("FFmpeg is already running from a previous state (unexpected). Stopping it.")
                self.ffmpeg_manager.stop()
                # Add a small delay to ensure FFmpeg fully stops if needed
                self.shutdown_event.wait(timeout=1)


            self.logger.info(f"Starting FFmpeg for item: {gcs_path_to_play}")
            stream_started_successfully = self.ffmpeg_manager.start(item_stream_config)
            self.current_ffmpeg_process = self.ffmpeg_manager.ffmpeg_process

            if stream_started_successfully and self.current_ffmpeg_process:
                self.logger.success(f"Successfully started streaming: {gcs_path_to_play}")
                # If we successfully started a normal (non-fallback) item, fallback_triggered is already False.
                # If we successfully started a fallback item, fallback_triggered is True. This is correct.

                while not self.shutdown_event.is_set():
                    if not self.ffmpeg_manager.is_running():
                        self.logger.info(f"FFmpeg process for {gcs_path_to_play} stopped running.")
                        break
                    self.shutdown_event.wait(timeout=1) # Check for shutdown signal periodically

                if self.shutdown_event.is_set():
                    self.logger.info("Shutdown signal received during item playback.")
                    if self.ffmpeg_manager.is_running(): # Ensure it's stopped if loop broken by shutdown
                         self.ffmpeg_manager.stop()
                    # Fall through to process cleanup and exit main loop

                # Wait for FFmpeg process to fully terminate and get exit code
                if self.current_ffmpeg_process: # Check if it wasn't cleared by an external stop()
                    self.current_ffmpeg_process.wait() # Wait for FFmpeg to fully exit
                    exit_code = self.current_ffmpeg_process.returncode
                    self.current_ffmpeg_process = None
                else: # Process might have been stopped and cleared by self.stop()
                    exit_code = 0 # Assume graceful stop if process object is gone

                if self.shutdown_event.is_set():
                    self.logger.info("Exiting run_loop due to shutdown signal.")
                    break # Exit main while loop

                if exit_code == 0:
                    self.logger.success(f"Item '{gcs_path_to_play}' finished playing successfully or was intentionally stopped.")
                    if self.fallback_triggered:
                        self.logger.info("Fallback item finished. Next iteration will attempt normal selection again.")
                        # Fallback is not reset here; it's reset if _select_next_item_logic (the initial one) succeeds.
                        # If it was a fallback item that just played, self.fallback_triggered is still true.
                        # The next iteration's _select_next_item_logic will be called first. If it finds an item,
                        # it will then set self.fallback_triggered = False.
                else:
                    self.logger.error(f"FFmpeg process for '{gcs_path_to_play}' failed with exit code {exit_code}.")
                    # stdout, stderr = self.ffmpeg_manager.get_output() # Assuming get_output fetches after process end
                    # self.logger.error(f"FFmpeg recent stdout: {stdout}")
                    # self.logger.error(f"FFmpeg recent stderr: {stderr}") # Be cautious with large outputs

                    if not self.fallback_triggered:
                        self.logger.info("Triggering fallback due to FFmpeg failure.")
                        self.fallback_triggered = True
                        # Loop will attempt _get_fallback_item()
                    else:
                        self.logger.error("Fallback item also failed. Idling for 60 seconds.")
                        self.shutdown_event.wait(timeout=60)
            else: # FFmpeg failed to start
                self.logger.error(f"FFmpeg failed to start for item: {gcs_path_to_play}.")
                if not self.fallback_triggered:
                    self.logger.info("Triggering fallback due to FFmpeg startup failure.")
                    self.fallback_triggered = True
                else:
                    self.logger.error("Fallback item also failed to start. Idling for 60 seconds.")
                    self.shutdown_event.wait(timeout=60)

            if self.shutdown_event.is_set():
                self.logger.info("Shutdown signal detected, exiting run_loop.")
                break

            # Small delay if nothing was processed to prevent tight CPU loop if all paths lead to no action
            if not gcs_path_to_play: # Should be rare given the logic, but as a safeguard
                self.logger.debug("No item was processed in this iteration. Short sleep.")
                self.shutdown_event.wait(timeout=5)


        self.logger.info("StreamOrchestrator run_loop finished.")
        # Ensure FFmpeg is stopped if loop exited for any reason other than explicit stop command
        if self.ffmpeg_manager and self.ffmpeg_manager.is_running():
            self.logger.info("Run_loop ending, ensuring FFmpeg is stopped.")
            self.ffmpeg_manager.stop()

    def stop(self) -> None:
        """
        Signals the orchestrator to shut down its main loop and stop streaming.
        """
        self.logger.info("Stop requested for StreamOrchestrator.")
        self.shutdown_event.set()

        # Stop FFmpeg if it's running
        if self.ffmpeg_manager and self.ffmpeg_manager.is_running():
            self.logger.info("Stopping FFmpeg manager...")
            self.ffmpeg_manager.stop()

        # Wait for the FFmpeg process Popen object, if it exists
        process_to_wait = self.current_ffmpeg_process
        if process_to_wait and hasattr(process_to_wait, 'poll') and process_to_wait.poll() is None:
            self.logger.info("Waiting for current FFmpeg process to terminate...")
            try:
                process_to_wait.wait(timeout=10) # Wait up to 10 seconds
                if process_to_wait.poll() is None:
                    self.logger.warning("FFmpeg process did not terminate in time after stop. Forcing kill.")
                    process_to_wait.kill() # Force kill if still running
            except Exception as e: # TimeoutExpired or other
                self.logger.error(f"Error waiting for FFmpeg process: {e}. Attempting to kill.")
                try:
                    process_to_wait.kill()
                except Exception as kill_e:
                    self.logger.error(f"Error killing FFmpeg process: {kill_e}")
        self.current_ffmpeg_process = None # Clear it after handling

        self.logger.info("StreamOrchestrator stopped.")


if __name__ == '__main__':
    # Example of how to test (requires a stream_config.json)
    # Create a dummy stream_config.json for testing in the root of the project
    # {
    #   "global_settings": {"ffmpeg_path": "ffmpeg", "youtube_rtmp_url": "rtmp://localhost/live", "youtube_stream_key": "test"},
    #   "playlists": [
    #     {"id": "p1", "name": "Playlist 1", "type": "static", "items": ["gs://bucket/item1.mp3", "gs://bucket/item2.mp3"], "loop": true}
    #   ],
    #   "schedule": [{"playlist_id": "p1"}],
    #   "fallback": {"playlist_id": "p1"}
    # }

    # Determine project root to find a potential stream_config.json
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_script_dir, "..", ".."))

    # Prioritize stream_config.json if it exists, otherwise use stream_config.example.json
    actual_config_path = os.path.join(project_root, "stream_config.json")
    example_config_path = os.path.join(project_root, "stream_config.example.json")

    test_config_path_to_use = None
    if os.path.exists(actual_config_path):
        test_config_path_to_use = actual_config_path
        logger.info(f"Using actual 'stream_config.json' for testing: {test_config_path_to_use}")
    elif os.path.exists(example_config_path):
        test_config_path_to_use = example_config_path
        logger.info(f"Using 'stream_config.example.json' for testing: {test_config_path_to_use}")
    else:
        logger.error(f"No stream_config file found for testing. Checked for: \n1. {actual_config_path}\n2. {example_config_path}\nCannot run example.")
        exit(1)

    orchestrator = StreamOrchestrator(config_file_path=test_config_path_to_use)

    if orchestrator.config and orchestrator.ffmpeg_manager:
        logger.info("Orchestrator initialized successfully with config.")

        # To run the loop in a thread for testing:
        # loop_thread = threading.Thread(target=orchestrator.run_loop, daemon=True)
        # logger.info("Starting run_loop in a test thread...")
        # loop_thread.start()

        # logger.info("Simulating main program running for a bit (e.g., 10-20 seconds)...")
        # logger.info("You should see FFmpeg startup if items are selected.")
        # logger.info("Check for 'lavfi:testsrc' if using default example config.")
        # time.sleep(20) # Let it run for a while

        # logger.info("Requesting orchestrator to stop...")
        # orchestrator.stop()

        # logger.info("Waiting for loop thread to join...")
        # loop_thread.join(timeout=15) # Wait for the loop thread to finish
        # if loop_thread.is_alive():
        #     logger.warning("Loop thread did not join in time.")

        # logger.info("Test finished.")

        # Simplified test for now: just select a few items without running the full loop
        logger.info("\n--- Testing item selection (without starting FFmpeg) ---")
        for i in range(5):
            item = orchestrator._select_next_item_logic()
            if item:
                logger.info(f"Attempt {i+1}: Selected item: {item} (Fallback mode: {orchestrator.fallback_triggered})")
                if orchestrator.current_playlist_config:
                    logger.debug(f"  Current playlist: {orchestrator.current_playlist_config.get('id')}, "
                                 f"Item index: {orchestrator.current_playlist_item_index}")
            else:
                logger.warning(f"Attempt {i+1}: No item selected. (Fallback mode: {orchestrator.fallback_triggered})")
                # If fallback is triggered and no fallback item, it will log an error and then this.
                # If normal selection fails and then fallback also fails, this will be hit.
                if orchestrator.fallback_triggered and not orchestrator._get_fallback_item():
                    logger.info("This is expected if fallback is triggered and no valid fallback item is configured.")
                break
        logger.info("--- Item selection test finished ---")
        orchestrator.stop() # Cleanly set shutdown event for any internal waits that might be happening.

    else:
        logger.error("Orchestrator initialization failed. Check logs.")

```
