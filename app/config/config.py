import os
import shutil
import socket

import toml
from loguru import logger

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
config_file = f"{root_dir}/config.toml"


def load_config():
    # fix: IsADirectoryError: [Errno 21] Is a directory: '/MoneyPrinterTurbo/config.toml'
    if os.path.isdir(config_file):
        shutil.rmtree(config_file)

    if not os.path.isfile(config_file):
        example_file = f"{root_dir}/config.example.toml"
        if os.path.isfile(example_file):
            shutil.copyfile(example_file, config_file)
            logger.info("copy config.example.toml to config.toml")

    logger.info(f"load config from file: {config_file}")

    try:
        _config_ = toml.load(config_file)
    except Exception as e:
        logger.warning(f"load config failed: {str(e)}, try to load as utf-8-sig")
        with open(config_file, mode="r", encoding="utf-8-sig") as fp:
            _cfg_content = fp.read()
            _config_ = toml.loads(_cfg_content)
    return _config_


def save_config():
    with open(config_file, "w", encoding="utf-8") as f:
        _cfg["app"] = app
        _cfg["azure"] = azure
        _cfg["siliconflow"] = siliconflow
        _cfg["google_tts"] = google_tts
        _cfg["streaming"] = streaming # Save streaming config
        _cfg["ui"] = ui
        f.write(toml.dumps(_cfg))


_cfg = load_config()
app = _cfg.get("app", {})
whisper = _cfg.get("whisper", {})
proxy = _cfg.get("proxy", {})
azure = _cfg.get("azure", {})
siliconflow = _cfg.get("siliconflow", {})
google_tts = _cfg.get("google_tts", {
    "service_account_key_path": os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"), # This is for TTS client, not YouTube API directly unless same SA is used
    "default_language_code": os.environ.get("GOOGLE_TTS_LANGUAGE_CODE", "en-US"),
    "default_voice_name": os.environ.get("GOOGLE_TTS_VOICE_NAME", "en-US-Wavenet-D"),
    "default_audio_encoding": os.environ.get("GOOGLE_TTS_AUDIO_ENCODING", "MP3"),
})
streaming = _cfg.get("streaming", {
    "youtube_api_key": os.environ.get("YOUTUBE_API_KEY"),
    "youtube_client_secrets_file": os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE"),
    "youtube_credentials_file": os.environ.get("YOUTUBE_CREDENTIALS_FILE"),
    "youtube_live_stream_id": os.environ.get("YOUTUBE_LIVE_STREAM_ID"),
    "media_cdn_rtmp_url": os.environ.get("MEDIA_CDN_RTMP_URL", "rtmp://localhost/live"),
    "media_cdn_stream_key": os.environ.get("MEDIA_CDN_STREAM_KEY", "test"),
    "default_resolution": os.environ.get("STREAMING_DEFAULT_RESOLUTION", "1920x1080"),
    "default_fps": int(os.environ.get("STREAMING_DEFAULT_FPS", 30)),
    "default_video_bitrate": os.environ.get("STREAMING_DEFAULT_VIDEO_BITRATE", "4500k"),
    "default_audio_bitrate": os.environ.get("STREAMING_DEFAULT_AUDIO_BITRATE", "128k"),
    "ffmpeg_input_source": os.environ.get("STREAMING_FFMPEG_INPUT_SOURCE", "lavfi:testsrc=size=1920x1080:rate=30:duration=3600"),
    "ffmpeg_path": os.environ.get("FFMPEG_PATH", "ffmpeg"),
})
ui = _cfg.get(
    "ui",
    {
        "hide_log": False,
    },
)

hostname = socket.gethostname()

log_level = _cfg.get("log_level", "DEBUG")
listen_host = _cfg.get("listen_host", "0.0.0.0")
listen_port = _cfg.get("listen_port", 8080)
project_name = _cfg.get("project_name", "MoneyPrinterTurbo")
project_description = _cfg.get(
    "project_description",
    "<a href='https://github.com/harry0703/MoneyPrinterTurbo'>https://github.com/harry0703/MoneyPrinterTurbo</a>",
)
project_version = _cfg.get("project_version", "1.2.6")
reload_debug = False

imagemagick_path = app.get("imagemagick_path", "")
if imagemagick_path and os.path.isfile(imagemagick_path):
    os.environ["IMAGEMAGICK_BINARY"] = imagemagick_path

ffmpeg_path = app.get("ffmpeg_path", "")
if ffmpeg_path and os.path.isfile(ffmpeg_path):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

logger.info(f"{project_name} v{project_version}")

# Import StreamConfig here to avoid circular dependency if it's moved to a models file later
# and to make the get_default_stream_config method work.
try:
    from app.services.streaming_interface import StreamConfig
except ImportError:
    # Define a dummy StreamConfig if not available, for basic standalone functionality
    # This should ideally not happen if project structure is correct.
    from dataclasses import dataclass
    @dataclass
    class StreamConfig:
        stream_key: str
        rtmp_url: str
        resolution: str
        fps: int
        video_bitrate: str
        audio_bitrate: str
        ffmpeg_input_source: str
        youtube_live_stream_id: Optional[str] = None


def get_default_stream_config() -> StreamConfig:
    """
    Constructs a StreamConfig object from the default streaming settings
    loaded from config.toml or environment variables.
    """
    return StreamConfig(
        stream_key=streaming.get("media_cdn_stream_key", "test"),
        rtmp_url=streaming.get("media_cdn_rtmp_url", "rtmp://localhost/live"),
        resolution=streaming.get("default_resolution", "1920x1080"),
        fps=int(streaming.get("default_fps", 30)),
        video_bitrate=streaming.get("default_video_bitrate", "4500k"),
        audio_bitrate=streaming.get("default_audio_bitrate", "128k"),
        ffmpeg_input_source=streaming.get("ffmpeg_input_source", "lavfi:testsrc=size=1920x1080:rate=30:duration=3600"),
        youtube_live_stream_id=streaming.get("youtube_live_stream_id")
    )
