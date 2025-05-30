"""
This module defines the StreamingOrchestrator class, a concrete implementation
of the StreamingService interface. It coordinates FFmpeg for streaming and
optionally interacts with YouTube for stream status.
"""
import os # Added import for os.environ.get
from typing import Dict, Any, Optional

from loguru import logger

try:
    from app.services.streaming_interface import StreamingService, StreamConfig
    from app.services.ffmpeg_manager import FFmpegManager
    from app.services.youtube_manager import YouTubeManager, GOOGLE_API_LIBS_AVAILABLE
except ImportError as e:
    logger.error(f"Error importing streaming modules: {e}. Ensure all streaming service components are available.")
    # Provide dummy classes if imports fail, to allow basic loading/type checking elsewhere
    # This is mostly for isolated development; in a full deployment, these should exist.
    if "StreamConfig" not in globals():
        from dataclasses import dataclass
        @dataclass
        class StreamConfig:
            stream_key: str = "dummy"
            rtmp_url: str = "dummy"
            resolution: str = "1280x720"
            fps: int = 30
            video_bitrate: str = "1000k"
            audio_bitrate: str = "128k"
            ffmpeg_input_source: str = "dummy"
            youtube_live_stream_id: Optional[str] = None # Added for clarity

    if "StreamingService" not in globals():
        from abc import ABC, abstractmethod
        class StreamingService(ABC):
            @abstractmethod
            def __init__(self, config: StreamConfig): pass
            @abstractmethod
            def start_stream(self) -> None: pass
            @abstractmethod
            def stop_stream(self) -> None: pass
            @abstractmethod
            def get_stream_status(self) -> Dict[str, Any]: pass
            @abstractmethod
            def update_configuration(self, new_config: StreamConfig) -> None: pass

    if "FFmpegManager" not in globals():
        class FFmpegManager:
            def __init__(self, config: StreamConfig, logger_instance=None): self.logger = logger_instance or logger
            def start(self) -> bool: self.logger.warning("Dummy FFmpegManager: start called"); return False
            def stop(self) -> None: self.logger.warning("Dummy FFmpegManager: stop called")
            def is_running(self) -> bool: return False

    if "YouTubeManager" not in globals():
        GOOGLE_API_LIBS_AVAILABLE = False
        class YouTubeManager:
            def __init__(self, logger_instance=None): self.logger = logger_instance or logger
            def get_live_stream_status(self, stream_id: str) -> dict:
                self.logger.warning("Dummy YouTubeManager: get_live_stream_status called")
                return {"error": "YouTubeManager not fully available"}


class StreamingOrchestrator(StreamingService):
    """
    Orchestrates video streaming using FFmpeg and can optionally interact with
    YouTube via YouTubeManager for stream status.
    """

    def __init__(self, config: StreamConfig, logger_instance=None):
        """
        Initializes the StreamingOrchestrator.

        Args:
            config: The initial StreamConfig for the stream.
            logger_instance: An optional Loguru logger. If None, a default one is used.
        """
        super().__init__(config)
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)
        self.ffmpeg_manager: Optional[FFmpegManager] = None

        # Initialize YouTubeManager, passing configured auth parameters
        # This assumes app_config.streaming holds these values from config.toml/env
        from app.config import config as app_global_config
        yt_config = app_global_config.streaming

        if GOOGLE_API_LIBS_AVAILABLE:
            try:
                self.youtube_manager: Optional[YouTubeManager] = YouTubeManager(
                    client_secrets_file=yt_config.get("youtube_client_secrets_file"),
                    credentials_file=yt_config.get("youtube_credentials_file"),
                    api_key=yt_config.get("youtube_api_key"),
                    service_account_json_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or yt_config.get("youtube_service_account_json_path"), # Prioritize env, then config for SA path
                    logger_instance=self.logger
                )
                if self.youtube_manager.youtube_service:
                    self.logger.info("YouTubeManager initialized successfully.")
                else:
                    self.logger.warning("YouTubeManager initialized but failed to get authenticated service. YouTube features may be limited.")
                    self.youtube_manager = None # Ensure it's None if service is not available
            except Exception as e:
                self.logger.error(f"Failed to initialize YouTubeManager: {e}. YouTube status checks will be unavailable.", exc_info=True)
                self.youtube_manager = None
        else:
            self.logger.warning("Google API libraries not available. YouTubeManager will not be used.")
            self.youtube_manager = None

        self.logger.info(f"StreamingOrchestrator initialized with config: {self.config}")

    def start_stream(self) -> None:
        """
        Starts the FFmpeg streaming process based on the current configuration.
        """
        self.logger.info(f"Attempting to start stream with config: {self.config}")

        if self.ffmpeg_manager and self.ffmpeg_manager.is_running():
            self.logger.warning("Stream is already running.")
            return

        # Pre-flight YouTube check (best-effort, informational)
        # Assumes 'youtube_live_stream_id' might be part of StreamConfig or a custom attribute
        youtube_stream_id_to_check = getattr(self.config, 'youtube_live_stream_id', None)
        if self.youtube_manager and youtube_stream_id_to_check:
            self.logger.info(f"Performing pre-flight check for YouTube Live Stream ID: {youtube_stream_id_to_check}")
            try:
                yt_status = self.youtube_manager.get_live_stream_status(youtube_stream_id_to_check)
                self.logger.info(f"YouTube pre-flight status for stream ID '{youtube_stream_id_to_check}': {yt_status}")
                # Log warning if stream is not in an ideal state, but proceed
                if yt_status.get('is_live') or yt_status.get('raw_status') not in ['ready', 'active', 'liveStarting', 'idle']: # 'idle' means it's valid but not streaming
                     self.logger.warning(
                        f"YouTube stream '{youtube_stream_id_to_check}' status is '{yt_status.get('raw_status')}' (is_live: {yt_status.get('is_live')}). "
                        "Attempting to start FFmpeg; this might activate the stream or lead to issues if stream is in an unexpected state."
                    )
            except Exception as e:
                self.logger.error(f"Could not get YouTube pre-flight status for '{youtube_stream_id_to_check}': {e}", exc_info=True)
        elif self.youtube_manager and not youtube_stream_id_to_check:
            self.logger.info("No 'youtube_live_stream_id' provided in StreamConfig, skipping YouTube pre-flight status check.")
        elif not self.youtube_manager:
             self.logger.info("YouTubeManager not available, skipping YouTube pre-flight status check.")


        try:
            self.ffmpeg_manager = FFmpegManager(config=self.config, logger_instance=self.logger)
            if self.ffmpeg_manager.start():
                self.logger.success("FFmpeg stream process started successfully.")
                self._is_active = True
            else:
                self.logger.error("FFmpegManager failed to start the stream process.")
                self.ffmpeg_manager = None # Ensure manager is cleared if start fails
                self._is_active = False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while starting FFmpegManager: {e}", exc_info=True)
            self.ffmpeg_manager = None
            self._is_active = False


    def stop_stream(self) -> None:
        """
        Stops the FFmpeg streaming process if it is running.
        """
        self.logger.info("Attempting to stop stream.")
        if self.ffmpeg_manager and self.ffmpeg_manager.is_running():
            self.ffmpeg_manager.stop()
            self.logger.info("FFmpeg stream stopped.")
        else:
            self.logger.info("Stream stop request: FFmpeg process was not running or manager not initialized.")

        self.ffmpeg_manager = None
        self._is_active = False # Set inactive regardless of whether it was running, as stop is called

    def get_stream_status(self) -> Dict[str, Any]:
        """
        Gets the current status of the stream, including FFmpeg status and
        optionally YouTube live stream status if configured.
        """
        status_info: Dict[str, Any] = {
            'is_active': False, # Overall orchestrator status
            'ffmpeg_running': False,
            'youtube_status': None,
            'uptime_seconds': 0, # Placeholder, could be implemented if FFmpegManager tracks start time
            'errors': [],
            'ffmpeg_pid': None
        }

        if self.ffmpeg_manager:
            is_ffmpeg_running = self.ffmpeg_manager.is_running()
            status_info['ffmpeg_running'] = is_ffmpeg_running
            if is_ffmpeg_running:
                status_info['is_active'] = True # If FFmpeg is pushing, consider stream active
                if self.ffmpeg_manager.ffmpeg_process:
                    status_info['ffmpeg_pid'] = self.ffmpeg_manager.ffmpeg_process.pid
                # TODO: Implement uptime calculation if FFmpegManager stores start time

        # YouTube Status Check
        youtube_stream_id_to_check = getattr(self.config, 'youtube_live_stream_id', None)

        if self.youtube_manager and youtube_stream_id_to_check:
            self.logger.debug(f"Getting YouTube status for liveStreamId: {youtube_stream_id_to_check}")
            try:
                yt_status = self.youtube_manager.get_live_stream_status(youtube_stream_id_to_check)
                status_info['youtube_status'] = yt_status
                # If FFmpeg is thought to be running, but YouTube says not live, update is_active
                if status_info['ffmpeg_running'] and yt_status and not yt_status.get('is_live'):
                    self.logger.warning(f"FFmpeg reported running, but YouTube status is '{yt_status.get('raw_status')}' (not live). Orchestrator status reflects YouTube.")
                    status_info['is_active'] = False
                elif status_info['ffmpeg_running'] and yt_status and yt_status.get('is_live'):
                     status_info['is_active'] = True # Both agree it's active
            except Exception as e:
                self.logger.error(f"Could not get YouTube status during status check for stream ID '{youtube_stream_id_to_check}': {e}", exc_info=True)
                status_info['errors'].append(f"YouTube status check failed: {str(e)}")
                status_info['youtube_status'] = {"error": f"Failed to retrieve YouTube status: {str(e)}"}
        elif self.youtube_manager:
             status_info['youtube_status'] = "Not checked (youtube_live_stream_id not configured in StreamConfig)."
        else:
            status_info['youtube_status'] = "YouTubeManager not available (Google API libs missing or init failed)."

        self.logger.debug(f"Current stream status: {status_info}")
        return status_info

    def update_configuration(self, new_config: StreamConfig) -> None:
        """
        Updates the stream configuration. If the stream is active,
        it will be stopped and restarted with the new configuration.
        """
        self.logger.info(f"Updating stream configuration. New config: {new_config}")
        should_restart = False
        if self.ffmpeg_manager and self.ffmpeg_manager.is_running():
            self.logger.info("Stream is currently active. It will be stopped and restarted to apply new configuration.")
            self.stop_stream() # This also sets self.ffmpeg_manager to None
            should_restart = True

        super().update_configuration(new_config) # This updates self.config

        if should_restart:
            self.logger.info("Restarting stream with new configuration.")
            self.start_stream()
        else:
            self.logger.info("New configuration will apply on the next stream start.")

```
