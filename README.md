<div align="center">
<h1 align="center">MoneyPrinterTurbo 💸</h1>

<p align="center">
  <a href="https://github.com/harry0703/MoneyPrinterTurbo/stargazers"><img src="https://img.shields.io/github/stars/harry0703/MoneyPrinterTurbo.svg?style=for-the-badge" alt="Stargazers"></a>
  <a href="https://github.com/harry0703/MoneyPrinterTurbo/issues"><img src="https://img.shields.io/github/issues/harry0703/MoneyPrinterTurbo.svg?style=for-the-badge" alt="Issues"></a>
  <a href="https://github.com/harry0703/MoneyPrinterTurbo/network/members"><img src="https://img.shields.io/github/forks/harry0703/MoneyPrinterTurbo.svg?style=for-the-badge" alt="Forks"></a>
  <a href="https://github.com/harry0703/MoneyPrinterTurbo/blob/main/LICENSE"><img src="https://img.shields.io/github/license/harry0703/MoneyPrinterTurbo.svg?style=for-the-badge" alt="License"></a>
</p>
<br>
<!-- Remove the Chinese language switch, as this will be the English README -->
<!-- <h3>简体中文 | <a href="README-en.md">English</a></h3> -->
<div align="center">
  <a href="https://trendshift.io/repositories/8731" target="_blank"><img src="https://trendshift.io/api/badge/repositories/8731" alt="harry0703%2FMoneyPrinterTurbo | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</div>
<br>
Just provide a video <b>theme</b> or <b>keywords</b>, and it will automatically generate the video script, video materials, subtitles, and background music, then synthesize a high-definition short video.
<br>

<h4>Web Interface</h4>

![](docs/webui.jpg)

<h4>API Interface</h4>

![](docs/api.jpg)

</div>

## Special Thanks 🙏

Due to the **deployment** and **usage** of this project presenting **certain challenges** for some novice users, special thanks go to
the **RecCloud (AI-powered Multimedia Service Platform)** website for providing a free `AI Video Generator` service based on this project. It allows direct online use without needing local deployment, which is very convenient.

- Chinese Version: https://reccloud.cn
- English Version: https://reccloud.com

![](docs/reccloud.cn.jpg)

## Sponsorship Thanks 🙏

Thanks to PicWish https://picwish.com for their support and sponsorship of this project, enabling its continuous updates and maintenance.

PicWish focuses on the **image processing field**, offering a rich set of **image processing tools** that simplify complex operations, truly making image processing easier.

![picwish.jpg](docs/picwish.jpg)

## Features 🎯

- [x] Complete **MVC architecture**, code is **clearly structured**, easy to maintain, and supports both `API` and `Web Interface`.
- [x] Supports **AI automatic generation** of video scripts, and also allows for **custom scripts**.
- [x] Supports multiple **HD video** dimensions:
    - [x] Portrait 9:16, `1080x1920`
    - [x] Landscape 16:9, `1920x1080`
- [x] Supports **batch video generation**, allowing multiple videos to be generated at once, so you can choose the most satisfactory one.
- [x] Supports setting **video clip duration**, making it easy to adjust the frequency of material switching.
- [x] Supports **Chinese** and **English** video scripts.
- [x] Supports **multiple voice synthesis** options, with **real-time previews**.
- [x] Supports **subtitle generation**, with adjustable `font`, `position`, `color`, `size`, and `outline` settings.
- [x] Supports **background music**, either random or from a specified file, with adjustable `background music volume`.
- [x] Video materials are sourced from **HD, royalty-free** stock, and you can also use your own **local materials**.
- [x] Supports multiple LLM providers including **OpenAI**, **Moonshot**, **Azure**, **gpt4free**, **one-api**, **Qwen (Alibaba Tongyi Qianwen)**, **Google Gemini**, **Ollama**, **DeepSeek**, **Ernie (Baidu Wenxin Yiyan)**, and **Pollinations**.
    - For users in China, **DeepSeek** or **Moonshot** are recommended as LLM providers (directly accessible in China, no VPN needed; registration provides free credits, generally sufficient for use).
- [x] Supports **Azure TTS**, **Google Cloud TTS**, **SiliconFlow TTS** (leveraging Azure features via `edge-tts` and new adapters for Google Cloud and SiliconFlow).

### Future Plans 📅

- [ ] GPT-SoVITS voice cloning support.
- [ ] Optimize voice synthesis using large models to make synthesized voices more natural and emotionally rich.
- [ ] Add video transition effects to make videos appear smoother.
- [ ] Increase video material sources and optimize the relevance between video materials and scripts.
- [ ] Add video length options: short, medium, long.
- [ ] Support more voice synthesis providers, such as OpenAI TTS.
- [ ] Automatic upload to YouTube platform.

## Video Demos 📺

### Portrait 9:16

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

### Landscape 16:9

<table>
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
(The `ffmpeg_path` is now under `[streaming]` section in `config.toml` as `streaming.ffmpeg_path`)


### ❓ImageMagick security policy prevents operations with temporary files like @/tmp/tmpur5hyyto.txt

These policies can be found in ImageMagick's `policy.xml` configuration file.
This file is usually located in `/etc/ImageMagick-X/` or a similar location in your ImageMagick installation directory.
Modify the entry containing `pattern="@"` by changing `rights="none"` to `rights="read|write"` to allow read and write operations for files.

### ❓OSError: [Errno 24] Too many open files

This issue is caused by system limits on the number of open files. It can be resolved by increasing this limit.

Check the current limit:
```shell
ulimit -n
```

If it's too low, you can increase it, for example:
```shell
ulimit -n 10240
```

### ❓Whisper model download fails with errors like:

`LocalEntryNotfoundEror: Cannot find an appropriate cached snapshotfolderfor the specified revision on the local disk and outgoing trafic has been disabled. To enablerepo look-ups and downloads online, pass 'local files only=False' as input.`

Or:

`An error occured while synchronizing the model Systran/faster-whisper-large-v3 from the Hugging Face Hub: An error happened while trying to locate the files on the Hub and we cannot find the appropriate snapshot folder for the specified revision on the local disk. Please check your internet connection and try again. Trying to load the model directly from the local cache, if it exists.`

Solution: [Click here to see how to manually download the model from a cloud drive](#subtitle-generation-) (Points to the subtitle generation section which has the links).

## Feedback and Suggestions 📢

- You can submit an [issue](https://github.com/harry0703/MoneyPrinterTurbo/issues)
  or a [pull request](https://github.com/harry0703/MoneyPrinterTurbo/pulls).

## License 📝

Click to view the [`LICENSE`](LICENSE) file.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=harry0703/MoneyPrinterTurbo&type=Date)](https://star-history.com/#harry0703/MoneyPrinterTurbo&Date)