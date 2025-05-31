<div align="center">
<h1 align="center">HarmoniStream AI 🎶📻</h1>

<p align="center">
  <!-- Using existing license badge, other badges can be updated if the repo URL changes -->
  <a href="https://github.com/harry0703/MoneyPrinterTurbo/blob/main/LICENSE"><img src="https://img.shields.io/github/license/harry0703/MoneyPrinterTurbo.svg?style=for-the-badge" alt="License"></a>
</p>
<br>
<b>HarmoniStream AI</b> is a configurable stream orchestrator that continuously plays media content from Google Cloud Storage (GCS) to an RTMP endpoint (e.g., YouTube Live, Twitch). It uses FFmpeg for media processing and streaming, and is designed for creating scheduled or dynamically-driven live audio/video streams.
<br>
</div>

## Overview

HarmoniStream AI is designed to automate continuous live streaming. By configuring playlists and schedules in a JSON file (`stream_config.json`), the application can manage an uninterrupted broadcast, handling transitions between different content blocks, rotating through playlists, and ensuring a fallback mechanism is in place for resilience. It leverages FFmpeg for robust media handling and streaming to any standard RTMP server.

## Features 🎯

- **Continuous Streaming:** Designed for 24/7 playback of media files from Google Cloud Storage.
- **RTMP Output:** Streams to any RTMP-compatible ingest server (e.g., YouTube Live, Twitch, Google Cloud Media CDN).
- **Configuration-Driven:** All aspects of the stream (playlists, schedule, global settings) are managed via a central `stream_config.json` file.
- **Static Playlists:** Define fixed sequences of GCS media paths.
- **Scheduled Playback (Basic):** Initial support for playing playlists in a defined order based on the schedule array in the config.
- **Playlist Rotation (Basic):** Basic support for rotating through a list of playlists when the main schedule is not active.
- **Fallback Mechanism:** Automatically switches to a predefined fallback playlist if issues occur with the primary content or FFmpeg process.
- **FFmpeg Integration:** Utilizes FFmpeg for actual media processing and streaming, allowing for flexibility in media formats and output settings.
- **Google Cloud Storage (GCS) Input:** Media content is sourced directly from GCS paths.

### Future Plans 📅

- **Advanced Scheduling:** Implement full time-based scheduling with start times, durations, and conflict resolution.
- **Dynamic Playlist Generation:** Fully implement `dynamic_rule` playlists, potentially integrating with a new AI-driven curation model.
- **More Output Targets:** Support for other streaming protocols or platforms.
- **OBS Integration (Conceptual):** Potential integration for scene switching or status updates with OBS Studio.
- **Enhanced Transitions:** More sophisticated audio/video transitions between playlist items managed by FFmpeg.
- **Monitoring & API:** Add a small API for monitoring orchestrator status and potentially controlling it remotely.
- **Improved GCS Authentication for FFmpeg:** Explore more robust ways for FFmpeg to access GCS resources if they are not public (e.g., using service account impersonation or signed URLs for FFmpeg inputs).

## System Requirements 📦

- Python 3.10 or newer.
- FFmpeg installed and accessible in the system's PATH (or path specified in `stream_config.json` under `global_settings`).
- Network connectivity for accessing Google Cloud Storage and the RTMP server.
- (Optional) Google Cloud SDK (`gcloud`) configured for Application Default Credentials, or a service account key file for GCS access if media items are not public and direct GCS paths are used by FFmpeg.
- For AI Music Generation (Conceptual):
    - Python packages: `magenta`, `tensorflow`, `tf_slim`, `pretty_midi`, `numpy`, `scipy`.
    - System dependencies: `fluidsynth` and a General MIDI SoundFont (e.g., `fluid-soundfont-gm`). These are included in the Docker build.

## Quick Start & Installation Guide

This section guides you through setting up and running the HarmoniStream AI orchestrator.

### Prerequisites

1.  **Install Python:** Ensure you have Python 3.10 or newer.
2.  **Install FFmpeg:** FFmpeg must be installed on your system and ideally added to your system's PATH.
    *   **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install ffmpeg`
    *   **MacOS:** `brew install ffmpeg`
    *   **Windows:** Download from [FFmpeg official site](https://ffmpeg.org/download.html) and add the `bin` directory to your PATH.
    *   Alternatively, specify the full path to your FFmpeg executable in `stream_config.json` under `global_settings.ffmpeg_path`.
3.  **Google Cloud Storage (GCS) Access (for FFmpeg):**
    *   Your media files must be stored in GCS and referenced by their `gs://` paths in `stream_config.json`.
    *   FFmpeg will need to access these GCS paths. This typically means either:
        *   The GCS objects are publicly readable (not recommended for private content).
        *   The environment where `main.py` (and thus FFmpeg) runs is authenticated to Google Cloud with permissions to read the GCS buckets/objects. This can be achieved via:
            *   **Application Default Credentials (ADC):** If running on Google Cloud infrastructure (e.g., GCE, GKE), ADC might be configured automatically. Locally, you can set it up using `gcloud auth application-default login`.
            *   **Service Account Key:** Download a JSON service account key with appropriate GCS read permissions (e.g., "Storage Object Viewer"). Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to the path of this key file.
                ```bash
                export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
                ```
    *   Refer to [Google Cloud Authentication documentation](https://cloud.google.com/docs/authentication) for more details.
4.  **AI Music Generation Dependencies (Optional, for future features):**
    *   If you plan to use or develop AI music generation features with Magenta, ensure system dependencies like `fluidsynth` and a soundfont are installed. The provided Dockerfile handles this. For manual setups, install `fluidsynth` and a GM soundfont (e.g., `fluid-soundfont-gm` on Debian/Ubuntu). Python dependencies are in `requirements.txt`.

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/harry0703/MoneyPrinterTurbo.git
    # TODO: Replace with the new repository URL if this project is forked or moved.
    cd MoneyPrinterTurbo
    # TODO: Replace with the new project directory name if changed.
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure the Stream:**
    *   Copy `stream_config.example.json` to `stream_config.json` in the project root.
        ```bash
        cp stream_config.example.json stream_config.json
        ```
    *   Edit `stream_config.json` to define your `global_settings` (RTMP URL, stream key), GCS paths for your media in `playlists`, your `schedule`, etc. Refer to the "Configuration - `stream_config.json`" section below for details.

### Running the Application

Once configured, you can run the StreamOrchestrator from the project root directory using:

```bash
python main.py --config stream_config.json
```

*   If you omit the `--config` argument, `main.py` will try to load `stream_config.json` from the project root. If not found, it will attempt to use `stream_config.example.json`.
*   The application will start, and based on your configuration, it will begin selecting playlists and items to stream via FFmpeg.
*   Press `Ctrl+C` to gracefully shut down the orchestrator.

## Docker Deployment 🐳

The application can also be run using Docker. The provided `Dockerfile` sets up the Python environment and includes FFmpeg and dependencies for Magenta.

1.  **Build the Docker Image:**
    Navigate to the project root directory (where the `Dockerfile` is located) and run:
    ```bash
    docker build -t harmonistream-ai .
    ```
    (Using `harmonistream-ai` as the image name, you can choose your own).

2.  **Run the Docker Container:**
    When running the container, you need to provide your `stream_config.json` and potentially Google Cloud credentials.

    *   **Mounting `stream_config.json`:**
        ```bash
        docker run --rm -it \
          -v /path/to/your/local/stream_config.json:/app/stream_config.json \
          harmonistream-ai
        ```
        Replace `/path/to/your/local/stream_config.json` with the actual path to your configuration file on your host machine. The container's working directory is `/app`, and `main.py` in the Docker `CMD` refers to `stream_config.json` in this directory.

    *   **Google Cloud Authentication in Docker:**
        If your GCS objects are not public, FFmpeg running inside Docker needs to authenticate. The most common way is to use a service account key:
        1.  Ensure your service account key JSON file is available on your host machine (e.g., `/path/to/your/gcp-key.json`).
        2.  Mount the key file into the container and set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable:
            ```bash
            docker run --rm -it \
              -v /path/to/your/local/stream_config.json:/app/stream_config.json \
              -v /path/to/your/gcp-key.json:/app/gcp-key.json \
              -e GOOGLE_APPLICATION_CREDENTIALS="/app/gcp-key.json" \
              harmonistream-ai
            ```
        Replace paths as needed. Ensure the service account key has permissions to read the GCS buckets/objects specified in your `stream_config.json`.

    *   **Using a custom config path with Docker CMD override:**
        If you want the Docker container to use a config file with a different name or path inside the container (that you mount), you can override the CMD:
        ```bash
        docker run --rm -it \
          -v /path/to/your/custom_config.json:/app/my_custom_config.json \
          harmonistream-ai python main.py --config /app/my_custom_config.json
        ```

## Core Components

HarmoniStream AI is built around the following key components:

*   **`StreamOrchestrator` (`app/orchestrator/stream_orchestrator.py`):** The main engine that loads `stream_config.json`, manages the playback schedule, selects media items, and controls FFmpeg for streaming.
*   **`FFmpegManager` (`app/services/ffmpeg_manager.py`):** A utility class responsible for building FFmpeg commands based on stream parameters and managing the FFmpeg subprocess.
*   **`YouTubeManager` (`app/services/youtube_manager.py`):** (Currently for future enhancements) A class for interacting with the YouTube Data API v3, potentially for fetching live stream status or verifying stream keys.
*   **`StreamConfig` Data Structure (`app/services/streaming_interface.py`):** Defines the parameters for a single FFmpeg streaming process (input, output, encoding, etc.).
*   **`stream_config.json`:** The central JSON configuration file defining global settings, playlists, schedule, rotation, and fallback behavior.
*   **Magenta & TensorFlow (for AI Music Generation - Conceptual/Future):** Python libraries for potential future integration of AI-generated music segments. Core dependencies (`magenta`, `tensorflow`, `tf_slim`, `pretty_midi`, `numpy`, `scipy`) and system tools (`fluidsynth`, `fluid-soundfont-gm`) are included in the Docker setup.

## Configuration - `stream_config.json`

For advanced stream orchestration, particularly for setting up continuous, scheduled, or rotated playlist playback, a separate JSON configuration file named `stream_config.json` can be used. This file allows for a detailed definition of global streaming parameters, content playlists, playback schedules, rotation rules, and fallback mechanisms.

An example of this configuration can be found in `stream_config.example.json` in the root of the project.

A very minimal example:
```json
{
  "global_settings": {
    "youtube_rtmp_url": "rtmp://your.rtmp.server/live",
    "youtube_stream_key": "your_stream_key",
    "ffmpeg_path": "ffmpeg"
  },
  "playlists": [
    {
      "id": "main_content",
      "name": "Main Content Loop",
      "type": "static",
      "items": [
        "gs://your-gcs-bucket/media/video1.mp4",
        "gs://your-gcs-bucket/media/audio_segment.mp3"
      ],
      "loop": true
    }
  ],
  "schedule": [
    { "playlist_id": "main_content" }
  ],
  "fallback": {
    "playlist_id": "main_content"
  }
}
```

### File Structure Overview

The `stream_config.json` file has the following main sections:

1.  **`global_settings` (Object):** Defines global parameters for the streaming output.
    *   `youtube_rtmp_url` (string): Full RTMP URL for the primary streaming ingest (e.g., "rtmp://a.rtmp.youtube.com/live2").
    *   `youtube_stream_key` (string): The stream key for the primary RTMP endpoint.
    *   `default_video_resolution` (string): Default video resolution if generating video content (e.g., "1920x1080"). Used by FFmpeg.
    *   `default_video_bitrate` (string): Default video bitrate (e.g., "4500k"). Used by FFmpeg.
    *   `default_audio_bitrate` (string): Default audio bitrate (e.g., "128k"). Used by FFmpeg.
    *   `default_fps` (integer): Default frames per second if generating video (e.g., 30). Used by FFmpeg.
    *   `ffmpeg_path` (string): Optional. Path to the FFmpeg executable. Defaults to "ffmpeg" if not specified (expecting it to be in system PATH).
    *   `log_level` (string): Logging level for the streaming orchestrator (e.g., "INFO", "DEBUG").

2.  **`playlists` (Array of Objects):** Defines all available playlists that can be scheduled or rotated.
    *   Each playlist object contains:
        *   `id` (string): A unique identifier for the playlist (e.g., "lofi_chill", "nature_sounds").
        *   `name` (string): A user-friendly name for the playlist (e.g., "Lofi Chill Vibes").
        *   `description` (string, optional): A brief description of the playlist's content.
        *   `type` (string): Specifies the type of playlist.
            *   `"static"`: The playlist consists of a fixed list of media items.
            *   `"dynamic_rule"`: (Conceptual for future development) The playlist is generated based on rules. The orchestrator will initially only fully support "static".
        *   **For `type: "static"`:**
            *   `items` (array of strings): An ordered list of full GCS paths to the audio/video files (e.g., "gs://your-bucket/audio/track1.mp3").
            *   `loop` (boolean, optional): Whether the playlist should loop automatically. Defaults to `true`.
        *   **For `type: "dynamic_rule"`:**
            *   `rules` (object): Defines the criteria for dynamic playlist generation (e.g., `{"genre": "lofi", "duration_hours": 2}`). (Currently logged by orchestrator but not used for generation).

3.  **`schedule` (Array of Objects):** Defines a time-based playback schedule. Items are processed in order.
    *   Each schedule object contains:
        *   `playlist_id` (string): The ID of the playlist to play (must match an `id` in the `playlists` array).
        *   `start_time_utc` (string, optional): The specific UTC time (ISO 8601 format, e.g., "YYYY-MM-DDTHH:MM:SSZ") when this playlist should start. If omitted, it implies sequential playback (plays immediately after the previous scheduled item finishes or on startup if it's the first item).
        *   `duration_minutes` (integer, optional): How long this playlist should play before moving to the next scheduled item or falling back to rotation.
            *   If omitted and the playlist's `loop` is `false`, it plays through once.
            *   If omitted and `loop` is `true`, it plays indefinitely until a *subsequent timed* schedule item interrupts it.

4.  **`rotation` (Object, optional):** Defines a simpler, non-timed sequence of playlists to play when no specific schedule is active or after the schedule completes.
    *   `enabled` (boolean): Set to `true` to enable playlist rotation.
    *   `playlist_ids` (array of strings): An ordered list of playlist IDs to cycle through.
    *   `rotate_every_minutes` (integer, optional): If provided, each playlist in the rotation will play for this duration before switching to the next. If not provided, each playlist plays through completely (respecting its own `loop` setting) before rotating.

5.  **`fallback` (Object):** Defines a specific playlist to use in critical failure scenarios.
    *   `playlist_id` (string): The ID of a highly reliable playlist (e.g., a single, long, tested audio file) to switch to if the main scheduled/rotated content fails to play, or if an external trigger (like an OBS disconnect, for future implementation) occurs.

This `stream_config.json` provides a flexible way to manage a continuous streaming broadcast, combining scheduled programming with rotated content and ensuring a fallback option is always available. The streaming orchestrator component will be responsible for interpreting this configuration file and managing the FFmpeg processes accordingly.

<!-- Obsolete sections (Subtitle Generation, Background Music, Subtitle Fonts) removed. -->

## Common Issues 🤔

### ❓RuntimeError: No ffmpeg exe could be found

Normally, ffmpeg is downloaded and detected automatically.
However, if there's an issue with your environment that prevents automatic download, you might encounter this error:

```
RuntimeError: No ffmpeg exe could be found.
Install ffmpeg on your system, or set the IMAGEIO_FFMPEG_EXE environment variable.
```

In this case, you can download ffmpeg from https://www.gyan.dev/ffmpeg/builds/, unzip it, and set `ffmpeg_path` in your `config.toml` to the actual path of the executable.

```toml
[app]
# Please set according to your actual path. Note that Windows path separators are \\
ffmpeg_path = "C:\\Users\\yourname\\Downloads\\ffmpeg.exe"
```
(Note: The `ffmpeg_path` mentioned in the old common issue for `config.toml` is now configured in `stream_config.json` under `global_settings`.)

### ❓OSError: [Errno 24] Too many open files (Linux/MacOS)

This issue can occur with long-running applications that handle many files or network connections. It's caused by system limits on the number of open file descriptors.

Check the current limit:
```shell
ulimit -n
```

If it's too low, you can increase it, for example:
```shell
ulimit -n 10240
```

### ❓ FFmpeg errors when accessing GCS paths

If FFmpeg reports errors like "Permission denied" or "File not found" for `gs://` paths, ensure that the environment where FFmpeg is running (your local machine or the Docker container) is properly authenticated to Google Cloud and has permissions to read from the specified GCS buckets/objects. Refer to the "Google Cloud Storage (GCS) Access" subsection in the "Prerequisites" section above. For Docker, pay special attention to mounting service account keys and setting `GOOGLE_APPLICATION_CREDENTIALS`.

## Feedback and Suggestions 📢

- You can submit an [issue](https://github.com/harry0703/MoneyPrinterTurbo/issues)
  or a [pull request](https://github.com/harry0703/MoneyPrinterTurbo/pulls).

## License 📝

Click to view the [`LICENSE`](LICENSE) file.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=harry0703/MoneyPrinterTurbo&type=Date)](https://star-history.com/#harry0703/MoneyPrinterTurbo&Date)