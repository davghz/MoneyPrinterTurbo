"""
This module provides a manager class for controlling FFmpeg processes,
primarily for video streaming purposes.
"""
import subprocess
import shlex
import os
import time
from typing import List, Tuple, Optional, Dict

from loguru import logger

# Attempt to import StreamConfig, handle if module is not found during early dev stages
try:
    from app.services.streaming_interface import StreamConfig
except ImportError:
    logger.warning(
        "StreamConfig not found. FFmpegManager might not function correctly "
        "without app.services.streaming_interface.StreamConfig."
    )
    # Define a dummy StreamConfig if not available, for basic standalone functionality
    from dataclasses import dataclass
    @dataclass
    class StreamConfig:
        stream_key: str = "test"
        rtmp_url: str = "rtmp://localhost/live"
        resolution: str = "1280x720"
        fps: int = 30
        video_bitrate: str = "2500k"
        audio_bitrate: str = "128k"
        ffmpeg_input_source: str = "lavfi:testsrc=size=1280x720:rate=30"


class FFmpegManager:
    """
    Manages FFmpeg processes for streaming.

    This class handles building FFmpeg commands, starting, stopping,
    and monitoring FFmpeg subprocesses based on a given StreamConfig.
    """

    def __init__(self, config: StreamConfig, logger_instance=None):
        """
        Initializes the FFmpegManager.

        Args:
            config: A StreamConfig object containing stream parameters.
            logger_instance: An optional Loguru logger instance. If None, a default
                             logger will be used.
        """
        self.config = config
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__) # Bind class name to logger
        self.ffmpeg_process: Optional[subprocess.Popen] = None

        from app.config import config as app_global_config # Import here to avoid top-level circular if not careful
        self.ffmpeg_path: str = app_global_config.streaming.get("ffmpeg_path", "ffmpeg")
        if self.ffmpeg_path != "ffmpeg": # Log only if it's not the default
            self.logger.info(f"Using custom FFmpeg path: '{self.ffmpeg_path}'")
        else:
            self.logger.debug(f"Using default FFmpeg path: '{self.ffmpeg_path}'")


    def _is_file_or_url(self, source: str) -> bool:
        """Checks if the source is likely a file path or URL."""
        return (
            os.path.exists(source) or
            source.startswith("rtmp://") or
            source.startswith("rtmps://") or
            source.startswith("http://") or
            source.startswith("https://") or
            source.endswith((".mp4", ".ts", ".m3u8", ".flv", ".mkv", ".avi", ".mov"))
        )

    def build_ffmpeg_command(self) -> List[str]:
        """
        Constructs the FFmpeg command as a list of arguments.

        Returns:
            A list of strings representing the FFmpeg command and its arguments.
        """
        cmd = [self.ffmpeg_path]

        # Input source handling
        input_source = self.config.ffmpeg_input_source
        if self._is_file_or_url(input_source):
            cmd.extend(["-re", "-i", input_source])
        elif input_source.startswith("lavfi:") or input_source.startswith("color="): # FFmpeg generated input
            cmd.extend(["-f", "lavfi", "-i", input_source])
        elif input_source in ["screen", "desktop", "camera"]: # Abstract sources
            # Platform-dependent source translation needed here.
            # This is a placeholder and would need significant expansion for cross-platform support.
            if sys.platform == "win32":
                if input_source == "desktop":
                    cmd.extend(["-f", "gdigrab", "-framerate", str(self.config.fps), "-i", "desktop"])
                else: # camera/screen might need more specific device names
                    self.logger.warning(f"'{input_source}' on Windows needs specific device input. Using testsrc.")
                    cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])
            elif sys.platform == "darwin": # macOS
                if input_source == "camera":
                     cmd.extend(["-f", "avfoundation", "-framerate", str(self.config.fps), "-i", "0"]) # '0' for default camera
                elif input_source == "screen": # Screen capture needs more setup on macOS
                    self.logger.warning(f"'screen' capture on macOS requires specific setup. Using testsrc.")
                    cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])
                else:
                    cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])
            elif sys.platform.startswith("linux"):
                if input_source == "screen": # X11 screen grab
                    # Assumes display :0.0, adjust if necessary
                    cmd.extend(["-f", "x11grab", "-framerate", str(self.config.fps), "-s", self.config.resolution, "-i", ":0.0"])
                else:
                    self.logger.warning(f"'{input_source}' on Linux needs specific device input. Using testsrc.")
                    cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])
            else: # Fallback for other OS
                self.logger.warning(f"Abstract source '{input_source}' not configured for {sys.platform}. Using testsrc.")
                cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])
        else: # If not recognized, treat as a direct FFmpeg input string that might need shlex parsing
             self.logger.warning(f"Unrecognized ffmpeg_input_source '{input_source}'. Attempting direct use or fallback to testsrc.")
             # A more robust solution might try to parse it or have stricter formats.
             # For now, if it's not a file/URL or known pattern, fallback.
             cmd.extend(["-f", "lavfi", "-i", f"testsrc=size={self.config.resolution}:rate={self.config.fps}"])


        # Video Encoding
        cmd.extend([
            "-vcodec", "libx264",
            "-pix_fmt", "yuv420p",
            "-s", self.config.resolution,
            "-r", str(self.config.fps),
            "-b:v", self.config.video_bitrate,
            "-g", str(self.config.fps * 2),  # Keyframe interval
            "-preset", "ultrafast", # Prioritize low CPU usage
            "-tune", "zerolatency", # Good for streaming
        ])

        # Audio Encoding
        cmd.extend([
            "-acodec", "aac",
            "-b:a", self.config.audio_bitrate,
            "-ar", "44100",
            "-ac", "2",
        ])

        # Output Format & Destination
        rtmp_output_url = f"{self.config.rtmp_url.rstrip('/')}/{self.config.stream_key}"
        cmd.extend([
            "-f", "flv",
            "-fflags", "+nobuffer", # Reduce latency
            "-avioflags", "direct", # Reduce latency
            "-flags", "+global_header", # Needed by some RTMP servers
            rtmp_output_url
        ])

        # General flags
        cmd.extend(["-hide_banner", "-nostats", "-loglevel", "error"])

        self.logger.debug(f"Built FFmpeg command: {' '.join(shlex.quote(str(c)) for c in cmd)}")
        return cmd

    def start(self) -> bool:
        """
        Starts the FFmpeg streaming process.

        Returns:
            True if the process started successfully, False otherwise.
        """
        if self.is_running():
            self.logger.warning("FFmpeg process start requested, but it is already running.")
            return False

        command = self.build_ffmpeg_command()
        # Log the command at DEBUG level for less noise, INFO for actual start action
        self.logger.debug(f"FFmpeg command to be executed: {' '.join(shlex.quote(str(c)) for c in command)}")
        self.logger.info(f"Attempting to start FFmpeg process...")

        try:
            self.ffmpeg_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, # Decode stdout/stderr as text
                errors='ignore', # Ignore decoding errors
                # Close FDs on Unix-like systems for cleaner process management
                close_fds=sys.platform != "win32"
            )

            time.sleep(0.5) # Allow FFmpeg a moment to start or fail

            if self.ffmpeg_process.poll() is not None:
                # Process terminated quickly, indicating an error
                # Capture output before it's lost
                stdout_output, stderr_output = self.ffmpeg_process.communicate()
                self.logger.error(
                    f"FFmpeg process terminated immediately upon start. Exit code: {self.ffmpeg_process.returncode}\n"
                    f"FFmpeg STDOUT:\n{stdout_output}\n"
                    f"FFmpeg STDERR:\n{stderr_output}"
                )
                self.ffmpeg_process = None # Clear the process object
                return False

            self.logger.info(f"FFmpeg process started successfully with PID: {self.ffmpeg_process.pid}.")
            return True
        except FileNotFoundError:
            self.logger.error(
                f"FFmpeg executable not found at path: '{self.ffmpeg_path}'. "
                "Please ensure FFmpeg is installed and the path is correct in your configuration or system PATH."
            )
            self.ffmpeg_process = None
            return False
        except PermissionError:
            self.logger.error(
                f"Permission denied when trying to execute FFmpeg at path: '{self.ffmpeg_path}'. "
                "Please check file permissions."
            )
            self.ffmpeg_process = None
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while starting FFmpeg process: {e}", exc_info=True)
            if self.ffmpeg_process and self.ffmpeg_process.poll() is None: # If process started but then error
                self.ffmpeg_process.kill() # Ensure it's killed if Popen succeeded but something else failed
            self.ffmpeg_process = None
            return False

    def stop(self) -> None:
        """
        Stops the FFmpeg streaming process if it is running.
        Sends SIGTERM first, then SIGKILL if it doesn't terminate within timeout.
        """
        if not self.is_running() or not self.ffmpeg_process: # Added not self.ffmpeg_process for robustness
            self.logger.info("FFmpeg stop request: Process is not running or already stopped.")
            self.ffmpeg_process = None
            return

        pid = self.ffmpeg_process.pid
        self.logger.info(f"Attempting to stop FFmpeg process with PID: {pid}...")
        try:
            self.logger.debug(f"Sending SIGTERM to FFmpeg process PID: {pid}.")
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5) # Wait for graceful termination
                self.logger.info(f"FFmpeg process PID: {pid} terminated gracefully (SIGTERM).")
            except subprocess.TimeoutExpired:
                self.logger.warning(f"FFmpeg process PID: {pid} did not terminate after 5s (SIGTERM). Sending SIGKILL.")
                self.ffmpeg_process.kill()
                try:
                    self.ffmpeg_process.wait(timeout=2) # Wait for kill
                    self.logger.info(f"FFmpeg process PID: {pid} killed (SIGKILL).")
                except subprocess.TimeoutExpired:
                    self.logger.error(f"FFmpeg process PID: {pid} did not terminate even after SIGKILL. Manual intervention may be required.")
            except Exception as e_wait: # Catch other errors during wait (e.g., InterruptedError)
                 self.logger.error(f"Error while waiting for FFmpeg process PID: {pid} to terminate: {e_wait}", exc_info=True)

        except ProcessLookupError: # Process might have already died
             self.logger.warning(f"FFmpeg process PID: {pid} already exited before stop was fully processed.")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during FFmpeg process (PID: {pid}) termination: {e}", exc_info=True)
        finally:
            # Ensure stdout/stderr are read to prevent pipe buffer issues if Popen used text=True and pipes
            if self.ffmpeg_process and hasattr(self.ffmpeg_process, 'stdout') and self.ffmpeg_process.stdout:
                 try: self.ffmpeg_process.stdout.close()
                 except Exception: pass
            if self.ffmpeg_process and hasattr(self.ffmpeg_process, 'stderr') and self.ffmpeg_process.stderr:
                 try: self.ffmpeg_process.stderr.close()
                 except Exception: pass
            self.ffmpeg_process = None # Mark as stopped

    def is_running(self) -> bool:
        """
        Checks if the FFmpeg process is currently running.

        Returns:
            True if the process is running, False otherwise.
        """
        return self.ffmpeg_process is not None and self.ffmpeg_process.poll() is None

    def get_output(self, max_lines: int = 20) -> Tuple[List[str], List[str]]:
        """
        Reads recent lines from FFmpeg's stdout and stderr. (Non-blocking)

        Args:
            max_lines: Maximum number of recent lines to return for stdout/stderr.

        Returns:
            A tuple containing two lists: (stdout_lines, stderr_lines).
            Each list contains decoded string lines. Returns empty lists if process
            is not available or output cannot be read.
        """
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        if not self.ffmpeg_process:
            self.logger.debug("get_output called but FFmpeg process is not set.")
            return stdout_lines, stderr_lines

        # This method is primarily for getting output after a process has terminated or if it failed quickly.
        # For continuous live output monitoring, a threaded approach for reading pipes is necessary.
        # Popen's communicate() is blocking until EOF, so it's used here with a small timeout
        # if the process has already terminated.

        if self.ffmpeg_process.poll() is not None: # Process has terminated
            self.logger.debug(f"FFmpeg process (PID: {self.ffmpeg_process.pid}) has terminated. Reading remaining output.")
            try:
                # Use a timeout even for communicate as a safeguard
                out_bytes, err_bytes = self.ffmpeg_process.communicate(timeout=1)
                if out_bytes:
                    stdout_lines = out_bytes.splitlines()[-max_lines:]
                if err_bytes:
                    stderr_lines = err_bytes.splitlines()[-max_lines:]
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Timeout expired while reading output from terminated FFmpeg process PID: {self.ffmpeg_process.pid}.")
            except Exception as e:
                self.logger.error(f"Error reading output from terminated FFmpeg process PID: {self.ffmpeg_process.pid}: {e}", exc_info=True)
        else:
            self.logger.debug(f"get_output called for running FFmpeg process (PID: {self.ffmpeg_process.pid}). This method is not designed for live tailing of logs.")
            # Implement non-blocking reads or a separate log handling mechanism for live logs.
            # For now, return empty for live processes to avoid blocking.
            # Example (conceptual, non-blocking reads are platform-dependent and complex):
            # if self.ffmpeg_process.stdout:
            #    stdout_lines.append(self.ffmpeg_process.stdout.readline().strip()) # This would still block
            pass

        return stdout_lines, stderr_lines

# Example usage (for testing this module directly)
if __name__ == "__main__":
    import sys
    logger.remove() # Remove default handler
    logger.add(sys.stderr, level="DEBUG") # Add back with DEBUG level

    test_config = StreamConfig(
        stream_key="test_stream",
        rtmp_url="rtmp://localhost/live", # Replace with a test RTMP server if available
        resolution="640x360",
        fps=15,
        video_bitrate="500k",
        audio_bitrate="64k",
        # Using lavfi test source for cross-platform compatibility
        ffmpeg_input_source="lavfi:testsrc=size=640x360:rate=15"
        # ffmpeg_input_source="color=c=blue:s=640x360:r=15" # Alternative test source
    )

    # Test with a file input if you have one
    # test_video_file = "path/to/your/test.mp4"
    # if os.path.exists(test_video_file):
    #     test_config.ffmpeg_input_source = test_video_file
    # else:
    #     logger.warning(f"Test video file not found: {test_video_file}. Using default testsrc.")


    manager = FFmpegManager(config=test_config)

    logger.info("Building FFmpeg command...")
    cmd = manager.build_ffmpeg_command()
    logger.info(f"Command: {' '.join(shlex.quote(str(c)) for c in cmd)}")

    logger.info("Starting FFmpeg...")
    if manager.start():
        logger.info("FFmpeg started. Streaming for 10 seconds...")
        time.sleep(10)

        if manager.is_running():
            logger.info("FFmpeg is still running.")
        else:
            logger.error("FFmpeg stopped prematurely.")
            out, err = manager.get_output()
            logger.info(f"FFmpeg stdout:\n{''.join(out)}")
            logger.error(f"FFmpeg stderr:\n{''.join(err)}")

        logger.info("Stopping FFmpeg...")
        manager.stop()
        if not manager.is_running():
            logger.info("FFmpeg stopped successfully.")
        else:
            logger.error("FFmpeg did not stop as expected.")
    else:
        logger.error("FFmpeg failed to start.")

    logger.info("Test finished.")
