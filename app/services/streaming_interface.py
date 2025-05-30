"""
This module defines the interface for video streaming services.

It includes:
- StreamConfig: A data structure to hold configuration parameters for a video stream.
- StreamingService: An abstract base class that defines the contract for services
  that can start, stop, and manage video streams.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class StreamConfig:
    """
    Configuration for a video stream.

    Attributes:
        stream_key: The stream key for the streaming platform (e.g., YouTube).
        rtmp_url: The RTMP URL of the streaming ingest point (e.g., Media CDN).
        resolution: The video resolution, formatted as "WIDTHxHEIGHT" (e.g., "1920x1080").
        fps: Frames per second for the video stream.
        video_bitrate: Target video bitrate for encoding (e.g., "4500k").
        audio_bitrate: Target audio bitrate for encoding (e.g., "128k").
        ffmpeg_input_source: The source input for FFmpeg. This could be a device,
                             a file path, a URL, or a generated pattern like "testsrc".
                             Example: "/path/to/video.mp4", "screen_capture_device",
                                      "color=c=blue:s=1280x720:r=30" (FFmpeg lavfi source).
        youtube_live_stream_id: Optional. The specific YouTube Live Stream ID.
                                This is used by `YouTubeManager` to fetch stream status
                                directly if provided. If None, status checks for YouTube
                                might be limited or rely on other methods.
    """
    stream_key: str
    rtmp_url: str
    resolution: str
    fps: int
    video_bitrate: str
    audio_bitrate: str
    ffmpeg_input_source: str
    youtube_live_stream_id: Optional[str] = None

class StreamingService(ABC):
    """
    Abstract Base Class for video streaming services.

    This interface defines the essential methods that a streaming service
    implementation should provide to manage a video stream's lifecycle.
    Implementations should handle exceptions gracefully and provide clear logging
    for diagnostics.
    """

    @abstractmethod
    def __init__(self, config: StreamConfig):
        """
        Initializes the streaming service with the given configuration.

        Args:
            config: A StreamConfig object containing the initial stream settings.
        """
        self.config = config
        self._is_active = False # Example internal state

    @abstractmethod
    def start_stream(self) -> None:
        """
        Starts the video stream.

        Implementations should handle the setup of the streaming process (e.g., FFmpeg)
        and begin transmitting video data to the specified RTMP endpoint.
        This method should raise an exception if the stream cannot be started.
        """
        pass

    @abstractmethod
    def stop_stream(self) -> None:
        """
        Stops the currently active video stream.

        Implementations should ensure that the streaming process is cleanly terminated.
        If no stream is active, this method might do nothing or log a warning.
        """
        pass

    @abstractmethod
    def get_stream_status(self) -> Dict[str, Any]:
        """
        Retrieves the current status of the video stream.

        Returns:
            A dictionary containing status information. Common keys might include:
            - 'is_active': bool (True if the stream is currently running)
            - 'uptime_seconds': int (Duration the stream has been active, in seconds)
            - 'errors': list (A list of error messages, if any)
            - 'pid': int (Process ID of the streaming process, e.g. FFmpeg PID)
            Specific implementations can add more provider-specific status details.
        """
        pass

    @abstractmethod
    def update_configuration(self, new_config: StreamConfig) -> None:
        """
        Updates the configuration of an active stream (if supported) or for the next stream.

        Some streaming parameters might be updatable on-the-fly, while others might
        require stopping and restarting the stream. Implementations should clarify
        this behavior.

        Args:
            new_config: A StreamConfig object with the new settings.

        Raises:
            NotImplementedError: If live updates are not supported.
        """
        # Default implementation could be to just update the config
        # and let the next start_stream call use it, or raise error if live update expected.
        # For now, let's assume it updates for the next start or if the implementation supports live updates.
        self.config = new_config
        logger.info("Stream configuration updated. Changes may apply on next stream start or if live update is supported.")
        # To be more explicit if live updates are not supported by default:
        # raise NotImplementedError("Live configuration updates are not supported by this service by default.")
        pass

# Example usage (not part of the interface file, just for illustration)
if __name__ == "__main__":
    from loguru import logger # Added for the update_configuration example

    # This is a concrete implementation example, not to be included in the interface file.
    class MyExampleStreamingService(StreamingService):
        def __init__(self, config: StreamConfig):
            super().__init__(config)
            logger.info(f"MyExampleStreamingService initialized with config: {config}")

        def start_stream(self) -> None:
            if self._is_active:
                logger.warning("Stream is already active.")
                return
            logger.info(f"Starting stream with input: {self.config.ffmpeg_input_source} to {self.config.rtmp_url}/{self.config.stream_key}")
            # Actual FFmpeg command execution would go here
            self._is_active = True
            logger.info("Stream started (simulated).")

        def stop_stream(self) -> None:
            if not self._is_active:
                logger.warning("Stream is not active, nothing to stop.")
                return
            logger.info("Stopping stream (simulated).")
            # Actual FFmpeg process termination would go here
            self._is_active = False
            logger.info("Stream stopped (simulated).")

        def get_stream_status(self) -> Dict[str, Any]:
            logger.info("Getting stream status.")
            return {
                'is_active': self._is_active,
                'uptime_seconds': 60 if self._is_active else 0, # Simulated
                'errors': [],
                'pid': 12345 if self._is_active else None # Simulated
            }

        def update_configuration(self, new_config: StreamConfig) -> None:
            super().update_configuration(new_config) # Calls base implementation
            logger.info("MyExampleStreamingService configuration updated.")
            if self._is_active:
                logger.info("Stream is active. Depending on implementation, restart might be needed for all changes to apply.")


    # Example instantiation and usage:
    default_config = StreamConfig(
        stream_key="my_secret_stream_key",
        rtmp_url="rtmp://a.rtmp.youtube.com/live2",
        resolution="1280x720",
        fps=30,
        video_bitrate="2500k",
        audio_bitrate="128k",
        ffmpeg_input_source="color=c=red:s=1280x720:r=30" # FFmpeg test source
    )

    service = MyExampleStreamingService(config=default_config)
    status = service.get_stream_status()
    logger.info(f"Initial status: {status}")

    service.start_stream()
    status = service.get_stream_status()
    logger.info(f"Status after start: {status}")
    
    new_fps_config = StreamConfig(
        stream_key="my_secret_stream_key",
        rtmp_url="rtmp://a.rtmp.youtube.com/live2",
        resolution="1280x720",
        fps=60, # Changed FPS
        video_bitrate="3000k", # Changed bitrate
        audio_bitrate="128k",
        ffmpeg_input_source="color=c=blue:s=1280x720:r=60"
    )
    service.update_configuration(new_fps_config)
    logger.info(f"Updated service config to: {service.config}")


    service.stop_stream()
    status = service.get_stream_status()
    logger.info(f"Status after stop: {status}")

    # Example of a config for a local file
    file_input_config = StreamConfig(
        stream_key="local_test",
        rtmp_url="rtmp://localhost/live", # Example for a local RTMP server
        resolution="640x360",
        fps=24,
        video_bitrate="1000k",
        audio_bitrate="96k",
        ffmpeg_input_source="/path/to/your/test_video.mp4" # Replace with an actual file path
    )
    # file_service = MyExampleStreamingService(config=file_input_config)
    # file_service.start_stream()
    # ...
    # file_service.stop_stream()
