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

<!-- Video Demos section removed as it was specific to MoneyPrinterTurbo -->

<table>
<thead>
<tr>
<th align="center"><g-emoji class="g-emoji" alias="arrow_forward">▶️</g-emoji> "How to Add Joy to Life"</th>
<th align="center"><g-emoji class="g-emoji" alias="arrow_forward">▶️</g-emoji> "The Role of Money"<br>More realistic synthesized voice</th>
<th align="center"><g-emoji class="g-emoji" alias="arrow_forward">▶️</g-emoji> "What is the Meaning of Life"</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><video src="https://github.com/harry0703/MoneyPrinterTurbo/assets/4928832/a84d33d5-27a2-4aba-8fd0-9fb2bd91c6a6"></video></td>
<td align="center"><video src="https://github.com/harry0703/MoneyPrinterTurbo/assets/4928832/af2f3b0b-002e-49fe-b161-18ba91c055e8"></video></td>
<td align="center"><video src="https://github.com/harry0703/MoneyPrinterTurbo/assets/4928832/112c9564-d52b-4472-99ad-970b75f66476"></video></td>
</tr>
</tbody>
</table>

## System Requirements 📦

- Python 3.10 or newer.
- FFmpeg installed and accessible in the system's PATH (or path specified in `stream_config.json`).
- Network connectivity for accessing Google Cloud Storage and the RTMP server.
- (Optional) Google Cloud SDK (`gcloud`) configured for Application Default Credentials, or a service account key file for GCS access if media items are not public.

## Quick Start & Installation Guide

This section guides you through setting up and running the HarmoniStream AI orchestrator.

### Prerequisites

1.  **Install Python:** Ensure you have Python 3.10 or newer.
2.  **Install FFmpeg:** FFmpeg must be installed on your system and ideally added to your system's PATH.
    *   **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install ffmpeg`
    *   **MacOS:** `brew install ffmpeg`
    *   **Windows:** Download from [FFmpeg official site](https://ffmpeg.org/download.html) and add the `bin` directory to your PATH.
3.  **Google Cloud Storage (GCS) Access:**
    *   Your media files must be stored in GCS.
    *   FFmpeg will need to access these GCS paths. This typically means either:
        *   The GCS objects are publicly readable (not recommended for private content).
        *   The environment where `main.py` (and thus FFmpeg) runs is authenticated to Google Cloud with permissions to read the GCS buckets/objects. This can be achieved via:
            *   **Application Default Credentials (ADC):** If running on Google Cloud infrastructure (e.g., GCE, GKE), ADC might be configured automatically. Locally, you can set it up using `gcloud auth application-default login`.
            *   **Service Account Key:** Download a JSON service account key with appropriate GCS read permissions (e.g., "Storage Object Viewer"). Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to the path of this key file.
                ```bash
                export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
                ```
    *   Refer to [Google Cloud Authentication documentation](https://cloud.google.com/docs/authentication) for more details.

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
    *   Copy `stream_config.example.json` to `stream_config.json`.
        ```bash
        cp stream_config.example.json stream_config.json
        ```
    *   Edit `stream_config.json` to define your `global_settings` (RTMP URL, stream key), GCS paths for your media in `playlists`, your `schedule`, etc. Refer to the "Configuration - `stream_config.json`" section below for details.

### Running the Application

Once configured, you can run the StreamOrchestrator using:

```bash
python main.py --config /path/to/your/stream_config.json
```

*   If you omit the `--config` argument, `main.py` will try to load `stream_config.json` from the project root. If not found, it will attempt to use `stream_config.example.json`.
*   The application will start, and based on your configuration, it will begin selecting playlists and items to stream via FFmpeg.
*   Press `Ctrl+C` to gracefully shut down the orchestrator.

## Docker Deployment 🐳

The application can also be run using Docker. The provided `Dockerfile` sets up the Python environment and includes FFmpeg.

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
        Replace `/path/to/your/local/stream_config.json` with the actual path to your configuration file on your host machine. The container expects it at `/app/stream_config.json` (this is the default path `main.py` will look for if `--config` is not specified in the Docker `CMD` or if `stream_config.json` is specified in `CMD` as it is now).

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

<!-- The "Streaming Management" and "Playlist Handling & Scheduling Engine" sections that were previously added are now superseded by the "Core Components" and the general description of HarmoniStream AI. -->
<!-- Details of GCSContentManager, PlaylistGenerator, PlaylistScheduler are removed as they are not directly used by the current StreamOrchestrator which relies on stream_config.json for playlist definitions. -->

## Configuration - `stream_config.json`
<thead>
<tr>
<th align="center"><g-emoji class="g-emoji" alias="arrow_forward">▶️</g-emoji> "What is the Meaning of Life"</th>
<th align="center"><g-emoji class="g-emoji" alias="arrow_forward">▶️</g-emoji> "Why Exercise"</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><video src="https://github.com/harry0703/MoneyPrinterTurbo/assets/4928832/346ebb15-c55f-47a9-a653-114f08bb8073"></video></td>
<td align="center"><video src="https://github.com/harry0703/MoneyPrinterTurbo/assets/4928832/271f2fae-8283-44a0-8aa0-0ed8f9a6fa87"></video></td>
</tr>
</tbody>
</table>

## System Requirements 📦

- Recommended minimum CPU: **4 cores** or more, Memory: **4GB** or more. A dedicated graphics card is not mandatory.
- Windows 10, MacOS 11.0, or newer operating systems.

## Quick Start 🚀

### Run in Google Colab
Avoid local environment configuration; click to quickly experience MoneyPrinterTurbo directly in Google Colab.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/harry0703/MoneyPrinterTurbo/blob/main/docs/MoneyPrinterTurbo.ipynb)

### Windows One-Click Installer

Download the one-click installer package, unzip, and use directly (ensure the path does not contain **Chinese characters**, **special symbols**, or **spaces**).

- Baidu Netdisk (v1.2.6): https://pan.baidu.com/s/1wg0UaIyXpO3SqIpaq790SQ?pwd=sbqx Access Code: sbqx
- Google Drive (v1.2.6): https://drive.google.com/file/d/1HsbzfT7XunkrCrHw5ncUjFX8XX4zAuUh/view?usp=sharing

After downloading, it is recommended to first **double-click** `update.bat` to update to the **latest code**, then double-click `start.bat` to launch.

After starting, it will automatically open your browser (if it opens to a blank page, try using **Chrome** or **Edge**).

## Installation and Deployment 📥

### Prerequisites

- Avoid using **non-English characters in paths** to prevent unforeseen issues.
- Ensure your **network connection** is stable; VPNs should be set to `global traffic` mode if used.

#### ① Clone the Code

```shell
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
```

#### ② Modify Configuration File (Optional, can also be configured in the WebUI after startup)

- Copy `config.example.toml` and rename it to `config.toml`.
- Following the instructions in `config.toml`, configure `pexels_api_keys` and `llm_provider`, and set up the relevant API keys for the chosen LLM provider.

### Docker Deployment 🐳

#### ① Start Docker

If Docker is not installed, please install it first: https://www.docker.com/products/docker-desktop/

For Windows systems, refer to Microsoft's documentation:
1. https://learn.microsoft.com/en-us/windows/wsl/install
2. https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers

```shell
cd MoneyPrinterTurbo
docker-compose up
```

> Note: The latest versions of Docker install Docker Compose as a plugin. The command is now `docker compose up`.

#### ② Access Web Interface

Open your browser and navigate to http://0.0.0.0:8501

#### ③ Access API Documentation

Open your browser and navigate to http://0.0.0.0:8080/docs or http://0.0.0.0:8080/redoc

### Manual Deployment 📦

> Video Tutorials (in Chinese)

- Full usage demonstration: https://v.douyin.com/iFhnwsKY/
- How to deploy on Windows: https://v.douyin.com/iFyjoW3M

#### ① Create a Virtual Environment

It is recommended to use [conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html) to create a Python virtual environment.

```shell
git clone https://github.com/harry0703/MoneyPrinterTurbo.git
cd MoneyPrinterTurbo
conda create -n MoneyPrinterTurbo python=3.11
conda activate MoneyPrinterTurbo
pip install -r requirements.txt
```

#### ② Install ImageMagick

- Windows:
    - Download from https://imagemagick.org/script/download.php. Choose the Windows version, and make sure to select a **static** library version, e.g., ImageMagick-7.1.1-32-Q16-x64-**static**.exe.
    - Install the downloaded ImageMagick. **Do not modify the default installation path.**
    - Modify `imagemagick_path` in your `config.toml` file to your **actual installation path**.
- MacOS:
  ```shell
  brew install imagemagick
  ```
- Ubuntu:
  ```shell
  sudo apt-get install imagemagick
  ```
- CentOS:
  ```shell
  sudo yum install ImageMagick
  ```

#### ③ Start Web Interface 🌐

Ensure you are in the MoneyPrinterTurbo project `root directory` when executing these commands.

###### Windows

```bat
webui.bat
```

###### MacOS or Linux

```shell
sh webui.sh
```

After starting, it will automatically open your browser (if it opens to a blank page, try using **Chrome** or **Edge**).

#### ④ Start API Service 🚀

```shell
python main.py
```

After starting, you can view the `API documentation` at http://127.0.0.1:8080/docs or http://127.0.0.1:8080/redoc to debug interfaces online and quickly experience the service.

## Speech Synthesis 🗣

The project supports multiple speech synthesis services:

- **Azure TTS**: Includes voices supported via `edge-tts` (V1 voices) and Azure Cognitive Services Speech SDK (V2 voices). V2 voices generally offer higher quality and require configuration of an Azure Speech Key and Region.
- **Google Cloud TTS**: Support for Google Cloud Text-to-Speech service. Requires authentication configuration (via a service account JSON file or Application Default Credentials).
- **SiliconFlow TTS**: Support for SiliconFlow TTS service, requiring an API Key.

**Voice Selection Convention**:
- **Azure**: Use Azure's voice name directly, e.g., `zh-CN-XiaoyiNeural-Female` or `en-US-AndrewMultilingualNeural-V2-Male`.
- **Google Cloud TTS**: Prefix the Google Cloud voice ID with `google:`, e.g., `google:en-US-Wavenet-D`.
- **SiliconFlow TTS**: Prefix the SiliconFlow voice ID with `siliconflow:`, e.g., `siliconflow:FunAudioLLM/CosyVoice2-0.5B:alex-Male`.

A list of supported Azure and some SiliconFlow voices can be found in: [Voice List](./docs/voice-list.txt). For a comprehensive list of available Google Cloud TTS voices, please refer to the official Google Cloud documentation or query via the API (which may be integrated into the UI in the future).

Please configure the API keys and other necessary parameters for the respective service providers in your `config.toml` file, referring to `config.example.toml` for details.

## Streaming Management

The system now includes capabilities for live streaming to platforms like YouTube Live and Google Cloud Media CDN.

### Overview
This feature allows the application to take an input video source (e.g., a generated video, a screen capture, or a test pattern) and stream it live to a configured RTMP endpoint. It uses FFmpeg for the actual streaming and can interact with YouTube's API for stream status monitoring.

### Key Components
*   **`StreamingOrchestrator`**: The main service class (`app.services.streaming_orchestrator.StreamingOrchestrator`) that manages the overall streaming lifecycle. It uses `FFmpegManager` for video processing and `YouTubeManager` for platform interactions.
*   **`FFmpegManager`**: A utility class (`app.services.ffmpeg_manager.FFmpegManager`) responsible for building and managing FFmpeg commands and processes.
*   **`YouTubeManager`**: A class (`app.services.youtube_manager.YouTubeManager`) for interacting with the YouTube Data API v3, primarily for fetching live stream status and potentially verifying stream keys.
*   **`StreamConfig`**: A data structure (`app.services.streaming_interface.StreamConfig`) that holds all necessary configuration for a single stream, such as RTMP URL, stream key, video/audio settings, and the FFmpeg input source.

### Setup and Configuration
Proper setup is crucial for the streaming functionality.

1.  **Configuration File**: All streaming-related settings are centralized under the `[streaming]` section in your `config.toml` file. Refer to `config.example.toml` for a detailed list of options and their descriptions.

2.  **Google Cloud Project**:
    *   Ensure you have a Google Cloud Project set up.
    *   Enable the **YouTube Data API v3**.
    *   If using Google Cloud Media CDN, set it up as per the [Google Cloud Media CDN Setup Guide](./docs/google_cloud_media_cdn_setup.md).

3.  **Authentication (for YouTubeManager)**:
    *   **Service Account (Recommended for backend)**: Create a service account in your GCP project, grant it appropriate roles (e.g., "YouTube API Services Viewer" or roles with live streaming permissions if managing streams), and download its JSON key file. Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the path of this file, or specify the path in `config.toml` (`streaming.youtube_service_account_json_path`).
    *   **OAuth 2.0 (for user-based actions)**: If you need the application to act on behalf of a specific YouTube user (e.g., to manage their streams), you'll need to perform an OAuth 2.0 flow. Configure `youtube_client_secrets_file` (path to your `client_secret.json`) and `youtube_credentials_file` (path to store the obtained tokens) in `config.toml`. The first run might require interactive authorization.
    *   **API Key (Limited)**: A YouTube Data API v3 key (`youtube_api_key` in config) can be used for some read-only operations but is not sufficient for managing or verifying user-specific live streams.

4.  **Media CDN**:
    *   Follow the [Google Cloud Media CDN Setup Guide](./docs/google_cloud_media_cdn_setup.md) to manually configure your live input endpoint on Media CDN.
    *   Obtain the **RTMP Ingest URL** and **Stream Key** from your Media CDN input configuration.
    *   Set these in `config.toml` under `streaming.media_cdn_rtmp_url` and `streaming.media_cdn_stream_key`.

5.  **Key Configuration Parameters & Environment Variables**:
    *   `YOUTUBE_LIVE_STREAM_ID` (or `streaming.youtube_live_stream_id` in config): The specific YouTube Live Stream ID to monitor.
    *   `MEDIA_CDN_RTMP_URL` (or `streaming.media_cdn_rtmp_url`): The RTMP server URL.
    *   `MEDIA_CDN_STREAM_KEY` (or `streaming.media_cdn_stream_key`): The stream key for the RTMP server.
    *   Other defaults like resolution, FPS, bitrates, and FFmpeg input source are also configurable in `config.toml` or via corresponding environment variables.

### FFmpeg
*   FFmpeg is required for video processing and streaming. Ensure it is installed on the system where the application runs.
*   The path to the FFmpeg executable can be specified in `config.toml` (`streaming.ffmpeg_path`) or via the `FFMPEG_PATH` environment variable if it's not in the system's default PATH.

### Conceptual Usage
While the exact method of triggering streams will depend on the application's API or UI (not covered here), the conceptual flow is:
1.  Load or define a `StreamConfig` object with all necessary parameters (RTMP URL, stream key, video settings, input source).
2.  Instantiate the `StreamingOrchestrator` with this `StreamConfig`.
3.  Call `orchestrator.start_stream()` to begin streaming.
4.  Use `orchestrator.get_stream_status()` to monitor.
5.  Call `orchestrator.stop_stream()` to end the stream.
6.  Configuration can be updated using `orchestrator.update_configuration(new_config)`, which will typically restart an active stream.

## Playlist Handling & Scheduling Engine

The application includes a sophisticated engine for dynamic playlist creation and management, primarily designed for continuous audio streaming (e.g., an AI-driven radio station).

### Overview
This engine allows for the creation of playlists from a library of audio content stored in Google Cloud Storage (GCS). It supports dynamic playlist generation based on various criteria, scheduling of these playlists, and handling of transitions between tracks.

### Key Components
*   **`PlaylistManagerService` (`app/services/playlist/playlist_manager_service.py`):** The main facade for interacting with the playlist system. It coordinates the generator and scheduler to create, schedule, and advance playlists.
*   **`GCSContentManager` (`app/services/playlist/gcs_content_manager.py`):** Responsible for accessing the audio library in Google Cloud Storage. It lists available audio tracks and retrieves their metadata. Metadata for each track (e.g., `track.mp3`) is expected to be in a corresponding JSON file (e.g., `track.mp3.meta.json`) in GCS.
*   **`PlaylistGenerator` (`app/services/playlist/playlist_generator.py`):** Creates new playlists by selecting tracks from the `GCSContentManager` based on specified criteria (like genre or mood tags) or default settings (e.g., target item count).
*   **`PlaylistScheduler` (`app/services/playlist/scheduler.py`):** Manages an in-memory queue of playlists, controls the playback order, and tracks the status of the current playlist and item.
*   **Data Models (`app/services/playlist/models.py`):** Defines core data structures like `PlaylistItem` (representing an audio track with its metadata, including transition information) and `Playlist` (an ordered collection of `PlaylistItem` objects with scheduling and status attributes).

### Features
*   **Dynamic Playlist Generation:** Create playlists on-the-fly based on content tags, desired duration, or item count.
*   **GCS Integration:** Leverages Google Cloud Storage for storing and retrieving the audio content library. Track metadata is stored alongside audio files.
*   **Configurable Transitions:** Supports defining transitions (e.g., crossfade, fade-in, none) between tracks. The specifics are detailed in `docs/playlist_transition_strategy.md`.
*   **Scheduling:** A simple in-memory queue manages the order of playlists. Playlists can be added to the front or back of the queue.
*   **Configuration:** Playlist behavior (default item count, GCS bucket, supported audio types, default transitions) is configurable via `config.toml` under the `[playlist]` section.

### Future Considerations (Conceptual)
*   **Advanced Scheduling:** Integration with more robust scheduling systems like Cloud Composer or Apache Airflow for complex, time-based playlist scheduling and event triggering.
*   **AI-Driven Curation:** Enhancing `PlaylistGenerator` with AI models to create more contextually relevant and engaging playlists based on deeper content analysis or user preferences.
*   **Persistent State:** Moving playlist and schedule state from in-memory to a persistent database for resilience.

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

## Subtitle Generation 📜

Currently, two methods for subtitle generation are supported:

- **edge**: Generates `quickly`, performs better, and has no specific requirements for computer configuration, but quality may be unstable.
- **whisper**: Generates `slowly`, performs worse, has certain requirements for computer configuration, but `quality is more reliable`.

You can switch between these by modifying `subtitle_provider` in the `config.toml` file.

It is recommended to use the `edge` mode. If the generated subtitle quality is poor, then switch to `whisper` mode.

> Note:

1. In whisper mode, a model file of about 3GB needs to be downloaded from HuggingFace. Please ensure your network is stable.
2. If left blank, subtitles will not be generated.

> As HuggingFace might be inaccessible in some regions, you can use the following methods to download the `whisper-large-v3` model file:

Download links:

- Baidu Netdisk: https://pan.baidu.com/s/11h3Q6tsDtjQKTjUu3sc5cA?pwd=xjs9
- Kuake Netdisk: https://pan.quark.cn/s/3ee3d991d64b

After downloading and unzipping the model, place the entire directory into `.\MoneyPrinterTurbo\models`.
The final file path should look like this: `.\MoneyPrinterTurbo\models\whisper-large-v3`

```
MoneyPrinterTurbo  
  ├─models
  │   └─whisper-large-v3
  │          config.json
  │          model.bin
  │          preprocessor_config.json
  │          tokenizer.json
  │          vocabulary.json
```

## Background Music 🎵

Background music for videos is located in the project's `resource/songs` directory.
> The project currently includes some default music sourced from YouTube videos. If there are any copyright infringements, please delete them.

## Subtitle Fonts 🅰

Fonts for rendering video subtitles are located in the project's `resource/fonts` directory. You can also add your own fonts here.

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