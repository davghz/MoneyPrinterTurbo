import os
import platform
import sys
from uuid import uuid4

import streamlit as st
from loguru import logger

# Add the root directory of the project to the system path to allow importing modules from the project
root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
    # print("******** sys.path ********") # Original print, commented out
    # print(sys.path)
    # print("")

from app.config import config
from app.models.schema import (
    MaterialInfo,
    VideoAspect,
    VideoConcatMode,
    VideoParams,
    VideoTransitionMode,
)
from app.services import llm, voice
from app.services import task as tm
from app.utils import utils

st.set_page_config(
    page_title="MoneyPrinterTurbo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Report a bug": "https://github.com/harry0703/MoneyPrinterTurbo/issues",
        "About": "# MoneyPrinterTurbo\nSimply provide a topic or keyword for a video, and it will "
        "automatically generate the video copy, video materials, video subtitles, "
        "and video background music before synthesizing a high-definition short "
        "video.\n\nhttps://github.com/harry0703/MoneyPrinterTurbo",
    },
)


streamlit_style = """
<style>
h1 {
    padding-top: 0 !important;
}
</style>
"""
st.markdown(streamlit_style, unsafe_allow_html=True)

# Define resource directories
font_dir = os.path.join(root_dir, "resource", "fonts")
song_dir = os.path.join(root_dir, "resource", "songs")
i18n_dir = os.path.join(root_dir, "webui", "i18n")
config_file = os.path.join(root_dir, "webui", ".streamlit", "webui.toml") # Not used in this script, but defined
system_locale = utils.get_system_locale() # e.g., "en_US" or "zh_CN"

# Load language files first to determine available languages
locales = utils.load_locales(i18n_dir)
available_lang_codes = list(locales.keys())

# Determine a sensible default language, prioritizing English
default_app_lang = "en" if "en" in available_lang_codes else (available_lang_codes[0] if available_lang_codes else "en")

if "video_subject" not in st.session_state:
    st.session_state["video_subject"] = ""
if "video_script" not in st.session_state:
    st.session_state["video_script"] = ""
if "video_terms" not in st.session_state:
    st.session_state["video_terms"] = ""

if "ui_language" not in st.session_state:
    config_lang = config.ui.get("language") # Language saved from previous session
    sys_locale_lang = system_locale.split('_')[0] if system_locale else default_app_lang # e.g., 'en' from 'en_US'

    if config_lang and config_lang in available_lang_codes:
        st.session_state["ui_language"] = config_lang
    elif sys_locale_lang in available_lang_codes:
        st.session_state["ui_language"] = sys_locale_lang
    else:
        st.session_state["ui_language"] = default_app_lang


# Create a top bar containing the title and language selection
title_col, lang_col = st.columns([3, 1])

with title_col:
    st.title(f"MoneyPrinterTurbo v{config.project_version}")

with lang_col:
    display_languages = []
    selected_idx = 0
    # Ensure 'en' is an option if en.json exists, and try to make it default if no valid selection
    current_selected_code = st.session_state.get("ui_language", default_app_lang)

    # Populate display_languages and find the index of the current language
    if available_lang_codes:
        for i, code in enumerate(available_lang_codes):
            lang_name = locales.get(code, {}).get('Language', code) # Get display name, fallback to code
            display_languages.append(f"{code} - {lang_name}")
            if code == current_selected_code:
                selected_idx = i

        # If current_selected_code was not found among loaded locales, default to English if possible
        if current_selected_code not in available_lang_codes and default_app_lang in available_lang_codes:
            selected_idx = available_lang_codes.index(default_app_lang)
    else: # Fallback if no locale files were loaded at all
        display_languages.append(f"{default_app_lang} - English (Default)")
        selected_idx = 0


    selected_language_display = st.selectbox(
        "Language", # Changed from "Language / 语言"
        options=display_languages,
        index=selected_idx,
        key="top_language_selector",
        label_visibility="collapsed",
    )
    if selected_language_display:
        code = selected_language_display.split(" - ")[0].strip()
        if code in locales: # Ensure selected code is valid and loaded
            st.session_state["ui_language"] = code
            config.ui["language"] = code # Save preference

# This list might be used elsewhere or be for reference; ensure it's up-to-date if so.
support_locales = [
    "zh-CN",
    "zh-HK",
    "zh-TW",
    "de-DE",
    "en-US", # Should map to 'en' from en.json effectively
    "fr-FR",
    "vi-VN",
    "th-TH",
]


def get_all_fonts():
    fonts = []
    for root, dirs, files in os.walk(font_dir):
        for file in files:
            if file.endswith(".ttf") or file.endswith(".ttc"):
                fonts.append(file)
    fonts.sort()
    return fonts


def get_all_songs():
    songs = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3"):
                songs.append(file)
    return songs


def open_task_folder(task_id):
    try:
        sys_platform = platform.system() # Renamed to avoid conflict with sys module
        path_to_open = os.path.join(root_dir, "storage", "tasks", task_id)
        if os.path.exists(path_to_open):
            if sys_platform == "Windows":
                os.system(f"start {path_to_open}")
            elif sys_platform == "Darwin": # macOS
                os.system(f"open {path_to_open}")
            # Add for Linux if desired:
            # elif sys_platform == "Linux":
            #     os.system(f"xdg-open {path_to_open}")
    except Exception as e:
        logger.error(f"Failed to open task folder: {e}")


def scroll_to_bottom():
    js = """
    <script>
        console.log("scroll_to_bottom");
        function scroll(dummy_var_to_force_repeat_execution){
            var sections = parent.document.querySelectorAll('section.main');
            console.log(sections);
            for(let index = 0; index<sections.length; index++) {
                sections[index].scrollTop = sections[index].scrollHeight;
            }
        }
        scroll(1);
    </script>
    """
    st.components.v1.html(js, height=0, width=0)


def init_log():
    logger.remove()
    _lvl = "DEBUG" # Default level, can be made configurable

    def format_record(record):
        # Get the full file path from the log record
        file_path = record["file"].path
        # Convert the absolute path to a path relative to the project root directory
        relative_path = os.path.relpath(file_path, root_dir)
        # Update the file path in the record
        record["file"].path = f"./{relative_path}"
        # Return the modified format string
        # You can adjust the format here as needed
        record["message"] = record["message"].replace(root_dir, ".") # Shorten paths in messages

        _format = (
            "<green>{time:%Y-%m-%d %H:%M:%S}</> | "
            + "<level>{level}</> | "
            + '"{file.path}:{line}":<blue> {function}</> '
            + "- <level>{message}</>"
            + "\n"
        )
        return _format

    logger.add(
        sys.stdout,
        level=_lvl,
        format=format_record,
        colorize=True,
    )

init_log()

# Ensure locales is loaded; it should be from above, but defensive re-load/check if needed.
# locales = utils.load_locales(i18n_dir)
en_translations = locales.get("en", {}).get("Translation", {})

def tr(key: str) -> str:
    """
    Translates a given key using the currently selected UI language.
    Falls back to English if the key is not found in the selected language,
    or returns the key itself if not found in English either.
    """
    selected_lang_code = st.session_state.get("ui_language", default_app_lang) # Use determined default_app_lang

    primary_loc_data = locales.get(selected_lang_code, {})
    translation = primary_loc_data.get("Translation", {}).get(key)

    if translation is None and selected_lang_code != "en":
        translation = en_translations.get(key)
        # Optional: log fallback if needed, but can be noisy
        # if translation is not None:
        #     logger.debug(f"Key '{key}' not found in '{selected_lang_code}', using English fallback.")

    if translation is None: # Fallback to the key itself if no translation found
        # logger.warning(f"Translation key '{key}' not found in '{selected_lang_code}' or English fallback.")
        return key

    return translation


# Create basic settings expander
if not config.app.get("hide_config", False):
    with st.expander(tr("Basic Settings"), expanded=False):
        config_panels = st.columns(3)
        left_config_panel = config_panels[0]
        middle_config_panel = config_panels[1]
        right_config_panel = config_panels[2]

        # Left panel - Log settings
        with left_config_panel:
            # Whether to hide the configuration panel
            hide_config = st.checkbox(
                tr("Hide Basic Settings"), value=config.app.get("hide_config", False)
            )
            config.app["hide_config"] = hide_config

            # Whether to disable log display
            hide_log = st.checkbox(
                tr("Hide Log"), value=config.ui.get("hide_log", False)
            )
            config.ui["hide_log"] = hide_log

        # Middle panel - LLM Settings
        with middle_config_panel:
            st.write(tr("LLM Settings"))
            llm_providers = [
                "OpenAI", "Moonshot", "Azure", "Qwen", "DeepSeek", "Gemini",
                "Ollama", "G4f", "OneAPI", "Cloudflare", "ERNIE", "Pollinations",
            ]
            saved_llm_provider = config.app.get("llm_provider", "OpenAI").lower()
            saved_llm_provider_index = 0
            try:
                saved_llm_provider_index = [p.lower() for p in llm_providers].index(saved_llm_provider)
            except ValueError:
                logger.warning(f"Saved LLM provider '{saved_llm_provider}' not in list. Defaulting to OpenAI.")
                saved_llm_provider_index = 0 # Default to OpenAI

            llm_provider_display = st.selectbox(
                tr("LLM Provider"),
                options=llm_providers,
                index=saved_llm_provider_index,
            )
            llm_helper = st.container()
            llm_provider = llm_provider_display.lower() # Use the display name for logic, assuming it matches keys
            config.app["llm_provider"] = llm_provider

            llm_api_key = config.app.get(f"{llm_provider}_api_key", "")
            llm_secret_key = config.app.get(f"{llm_provider}_secret_key", "")
            llm_base_url = config.app.get(f"{llm_provider}_base_url", "")
            llm_model_name = config.app.get(f"{llm_provider}_model_name", "")
            llm_account_id = config.app.get(f"{llm_provider}_account_id", "")

            tips = ""
            # --- LLM Provider Tips (Translated Headers, content needs i18n via tr() for full localization) ---
            if llm_provider == "ollama":
                if not llm_model_name: llm_model_name = "qwen:7b"
                if not llm_base_url: llm_base_url = "http://localhost:11434/v1"
                with llm_helper: tips = tr("ollama_tips") # Key for Ollama tips in JSON
            elif llm_provider == "openai":
                if not llm_model_name: llm_model_name = "gpt-3.5-turbo"
                with llm_helper: tips = tr("openai_tips")
            elif llm_provider == "moonshot":
                if not llm_model_name: llm_model_name = "moonshot-v1-8k"
                with llm_helper: tips = tr("moonshot_tips")
            elif llm_provider == "oneapi":
                if not llm_model_name: llm_model_name = "claude-3-5-sonnet-20240620"
                with llm_helper: tips = tr("oneapi_tips")
            elif llm_provider == "qwen":
                if not llm_model_name: llm_model_name = "qwen-max"
                with llm_helper: tips = tr("qwen_tips")
            elif llm_provider == "g4f":
                if not llm_model_name: llm_model_name = "gpt-3.5-turbo"
                with llm_helper: tips = tr("g4f_tips")
            elif llm_provider == "azure":
                with llm_helper: tips = tr("azure_llm_tips") # Differentiate from Azure TTS
            elif llm_provider == "gemini":
                if not llm_model_name: llm_model_name = "gemini-1.0-pro"
                with llm_helper: tips = tr("gemini_tips")
            elif llm_provider == "deepseek":
                if not llm_model_name: llm_model_name = "deepseek-chat"
                if not llm_base_url: llm_base_url = "https://api.deepseek.com"
                with llm_helper: tips = tr("deepseek_tips")
            elif llm_provider == "ernie":
                with llm_helper: tips = tr("ernie_tips")
            elif llm_provider == "pollinations":
                if not llm_model_name: llm_model_name = "openai-fast" # Changed from 'default'
                with llm_helper: tips = tr("pollinations_tips")

            # This warning should ideally also use tr() for its text if it's meant to be multilingual
            if st.session_state["ui_language"] == "zh": # Show this specific tip only if UI is Chinese
                 st.warning(tr("china_users_llm_recommendation")) # Key for this specific warning

            if tips: st.info(tips)

            st_llm_api_key = st.text_input(tr("API Key"), value=llm_api_key, type="password", key=f"{llm_provider}_api_key_input")
            st_llm_base_url = st.text_input(tr("Base Url"), value=llm_base_url,  key=f"{llm_provider}_base_url_input")

            if llm_provider != "ernie":
                st_llm_model_name = st.text_input(tr("Model Name"), value=llm_model_name, key=f"{llm_provider}_model_name_input")
                if st_llm_model_name: config.app[f"{llm_provider}_model_name"] = st_llm_model_name
            else: # ERNIE might not use model_name in the same way via UI
                st_llm_model_name = None

            if st_llm_api_key: config.app[f"{llm_provider}_api_key"] = st_llm_api_key
            if st_llm_base_url: config.app[f"{llm_provider}_base_url"] = st_llm_base_url
            # Model name already saved above if not ERNIE

            if llm_provider == "ernie":
                st_llm_secret_key = st.text_input(tr("Secret Key"), value=llm_secret_key, type="password", key=f"{llm_provider}_secret_key_input")
                config.app[f"{llm_provider}_secret_key"] = st_llm_secret_key

            if llm_provider == "cloudflare":
                st_llm_account_id = st.text_input(tr("Account ID"), value=llm_account_id, key=f"{llm_provider}_account_id_input")
                if st_llm_account_id: config.app[f"{llm_provider}_account_id"] = st_llm_account_id

        # Right panel - Video Source API Key Settings
        with right_config_panel:
            st.write(tr("Video Source Settings"))

            def get_keys_from_config(cfg_key_in_app: str) -> str:
                api_keys_val = config.app.get(cfg_key_in_app, [])
                return ", ".join(api_keys_val) if isinstance(api_keys_val, list) else api_keys_val

            def save_keys_to_config(cfg_key_in_app: str, value_str: str):
                processed_value = [k.strip() for k in value_str.split(",") if k.strip()]
                config.app[cfg_key_in_app] = processed_value if processed_value else []


            pexels_api_keys_str = get_keys_from_config("pexels_api_keys")
            pexels_api_keys_input = st.text_input(tr("Pexels API Key"), value=pexels_api_keys_str, type="password", help=tr("pexels_api_key_help"))
            if pexels_api_keys_input != pexels_api_keys_str : save_keys_to_config("pexels_api_keys", pexels_api_keys_input)

            pixabay_api_keys_str = get_keys_from_config("pixabay_api_keys")
            pixabay_api_keys_input = st.text_input(tr("Pixabay API Key"), value=pixabay_api_keys_str, type="password", help=tr("pixabay_api_key_help"))
            if pixabay_api_keys_input != pixabay_api_keys_str: save_keys_to_config("pixabay_api_keys", pixabay_api_keys_input)

# Main UI layout panels
llm_provider_from_config = config.app.get("llm_provider", "").lower() # Renamed to avoid conflict
panel = st.columns(3)
left_panel = panel[0]
middle_panel = panel[1]
right_panel = panel[2]

params = VideoParams(video_subject="") # Initialize with empty subject
uploaded_files = []

with left_panel:
    with st.container(border=True):
        st.write(tr("Video Script Settings"))
        params.video_subject = st.text_input(
            tr("Video Subject"),
            value=st.session_state["video_subject"],
            key="video_subject_input", # Unique key for this input
        ).strip()

        video_languages_options = [(tr("Auto Detect"), "")] + [(code, code) for code in support_locales]

        # Find index for current language selection
        current_lang_code_idx = 0
        if params.video_language:
            try:
                current_lang_code_idx = [opt[1] for opt in video_languages_options].index(params.video_language)
            except ValueError: # If saved lang not in options, default to "Auto Detect"
                 current_lang_code_idx = 0


        selected_lang_display_idx = st.selectbox(
            tr("Script Language"),
            index=current_lang_code_idx,
            options=range(len(video_languages_options)),
            format_func=lambda x: video_languages_options[x][0],
        )
        params.video_language = video_languages_options[selected_lang_display_idx][1]

        if st.button(tr("Generate Video Script and Keywords"), key="auto_generate_script"):
            if not params.video_subject:
                 st.error(tr("Video Subject Cannot Be Empty for AI generation")) # New key
            else:
                with st.spinner(tr("Generating Video Script and Keywords")):
                    script = llm.generate_script(
                        video_subject=params.video_subject, language=params.video_language
                    )
                    terms = llm.generate_terms(params.video_subject, script) # Uses subject and new script
                    if "Error: " in script:
                        st.error(tr(script) if not script.startswith("Error: ") else script) # Display direct error
                    elif isinstance(terms, str) and "Error: " in terms: # Check if terms is error string
                        st.error(tr(terms) if not terms.startswith("Error: ") else terms)
                    else:
                        st.session_state["video_script"] = script
                        st.session_state["video_terms"] = ", ".join(terms) if isinstance(terms, list) else terms

        params.video_script = st.text_area(
            tr("Video Script"), value=st.session_state["video_script"], height=280
        )

        if st.button(tr("Generate Video Keywords"), key="auto_generate_terms"):
            if not params.video_script: # Script is needed for this
                st.error(tr("Video Script Cannot Be Empty to Generate Keywords")) # New key
            elif not params.video_subject:
                 st.error(tr("Video Subject Cannot Be Empty to Generate Keywords")) # New key for context
            else:
                with st.spinner(tr("Generating Video Keywords")):
                    terms = llm.generate_terms(params.video_subject, params.video_script)
                    if isinstance(terms, str) and "Error: " in terms:
                        st.error(tr(terms) if not terms.startswith("Error: ") else terms)
                    else:
                        st.session_state["video_terms"] = ", ".join(terms) if isinstance(terms, list) else terms

        params.video_terms = st.text_area(
            tr("Video Keywords"), value=st.session_state["video_terms"]
        )

with middle_panel:
    with st.container(border=True):
        st.write(tr("Video Settings"))
        video_concat_modes = [(tr("Sequential"), "sequential"), (tr("Random"), "random")]
        video_sources = [
            (tr("Pexels"), "pexels"), (tr("Pixabay"), "pixabay"), (tr("Local file"), "local")
            # (tr("TikTok"), "douyin"), (tr("Bilibili"), "bilibili"), (tr("Xiaohongshu"), "xiaohongshu"), # Commented out as per original
        ]

        saved_video_source_name = config.app.get("video_source", "pexels")
        try:
            saved_video_source_index = [v[1] for v in video_sources].index(saved_video_source_name)
        except ValueError:
            saved_video_source_index = 0 # Default to Pexels if saved not in list

        selected_video_source_idx = st.selectbox(
            tr("Video Source"),
            options=range(len(video_sources)),
            format_func=lambda x: video_sources[x][0],
            index=saved_video_source_index,
        )
        params.video_source = video_sources[selected_video_source_idx][1]
        config.app["video_source"] = params.video_source

        if params.video_source == "local":
            uploaded_files = st.file_uploader(
                tr("Upload Local Files"), # Key "Upload Local Files"
                type=["mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png", "bmp"], # Added bmp
                accept_multiple_files=True,
            )

        # Video Concat Mode
        current_concat_mode_val = params.video_concat_mode.value if isinstance(params.video_concat_mode, Enum) else params.video_concat_mode
        try:
            concat_mode_idx = [opt[1] for opt in video_concat_modes].index(current_concat_mode_val)
        except ValueError:
            concat_mode_idx = 1 # Default to Random

        selected_concat_idx = st.selectbox(
            tr("Video Concat Mode"), index=concat_mode_idx,
            options=range(len(video_concat_modes)),
            format_func=lambda x: video_concat_modes[x][0],
        )
        params.video_concat_mode = VideoConcatMode(video_concat_modes[selected_concat_idx][1])

        # Video Transition Mode
        video_transition_modes = [
            (tr("None"), VideoTransitionMode.none.value), (tr("Shuffle"), VideoTransitionMode.shuffle.value),
            (tr("FadeIn"), VideoTransitionMode.fade_in.value), (tr("FadeOut"), VideoTransitionMode.fade_out.value),
            (tr("SlideIn"), VideoTransitionMode.slide_in.value), (tr("SlideOut"), VideoTransitionMode.slide_out.value),
        ]
        current_transition_mode_val = params.video_transition_mode.value if isinstance(params.video_transition_mode, Enum) else params.video_transition_mode
        try:
            transition_mode_idx = [opt[1] for opt in video_transition_modes].index(current_transition_mode_val)
        except ValueError:
            transition_mode_idx = 0 # Default to None

        selected_transition_idx = st.selectbox(
            tr("Video Transition Mode"), options=range(len(video_transition_modes)),
            format_func=lambda x: video_transition_modes[x][0], index=transition_mode_idx,
        )
        params.video_transition_mode = VideoTransitionMode(video_transition_modes[selected_transition_idx][1])

        video_aspect_ratios = [
            (tr("Portrait"), VideoAspect.portrait.value), (tr("Landscape"), VideoAspect.landscape.value),
        ]
        current_aspect_val = params.video_aspect.value if isinstance(params.video_aspect, Enum) else params.video_aspect
        try:
            aspect_ratio_idx = [opt[1] for opt in video_aspect_ratios].index(current_aspect_val)
        except ValueError:
            aspect_ratio_idx = 0 # Default to Portrait

        selected_aspect_idx = st.selectbox(
            tr("Video Ratio"), options=range(len(video_aspect_ratios)),
            format_func=lambda x: video_aspect_ratios[x][0], index=aspect_ratio_idx,
        )
        params.video_aspect = VideoAspect(video_aspect_ratios[selected_aspect_idx][1])

        params.video_clip_duration = st.selectbox(tr("Clip Duration"), options=[2, 3, 4, 5, 6, 7, 8, 9, 10], index=3) # Default to 5s
        params.video_count = st.selectbox(tr("Number of Videos Generated Simultaneously"), options=[1, 2, 3, 4, 5], index=0)

    with st.container(border=True):
        st.write(tr("Audio Settings"))

        # TTS Server Selection
        tts_servers = [
            ("azure-tts-v1", tr("Azure TTS v1 (Edge)")), # Using tr() for display names
            ("azure-tts-v2", tr("Azure TTS v2 (SDK)")),
            ("siliconflow", tr("SiliconFlow TTS")),
            ("google", tr("Google Cloud TTS")), # Added Google TTS
        ]
        saved_tts_server = config.ui.get("tts_server", "azure-tts-v1") # Default if not set

        try:
            saved_tts_server_index = [s[0] for s in tts_servers].index(saved_tts_server)
        except ValueError:
            logger.warning(f"Saved TTS server '{saved_tts_server}' not in list. Defaulting to Azure TTS v1.")
            saved_tts_server_index = 0

        selected_tts_server_display_idx = st.selectbox(
            tr("TTS Servers"), options=range(len(tts_servers)),
            format_func=lambda x: tts_servers[x][1], index=saved_tts_server_index,
        )
        selected_tts_server_code = tts_servers[selected_tts_server_display_idx][0]
        config.ui["tts_server"] = selected_tts_server_code

        # Voice selection logic based on chosen TTS server
        filtered_voices = []
        if selected_tts_server_code == "siliconflow":
            filtered_voices = voice.get_siliconflow_voices()
        elif selected_tts_server_code == "google":
            # Assuming get_google_voices() exists or is added to voice.py or a new manager
            # For now, let's assume it returns a list like other providers
            # You might need to instantiate GoogleCloudTTS().get_available_voices() here if it's not too slow
            try:
                gctts = GoogleCloudTTS() # This will initialize client
                filtered_voices = gctts.get_available_voices(language_code=params.video_language or None) # Filter by script lang if set
            except Exception as e:
                logger.error(f"Could not fetch Google TTS voices: {e}")
                filtered_voices = []
            if not filtered_voices: # Fallback or if no language specified
                 filtered_voices = ["google:en-US-Wavenet-D (Example)"] # Provide an example if list is empty
        else: # Azure V1 or V2
            all_azure_voices = voice.get_all_azure_voices(filter_locals=None)
            for v_az in all_azure_voices:
                if selected_tts_server_code == "azure-tts-v2":
                    if "V2" in v_az: filtered_voices.append(v_az)
                else: # azure-tts-v1
                    if "V2" not in v_az: filtered_voices.append(v_az)

        # Create friendly names for display
        friendly_names = {
            v_name: (
                v_name.replace("Female", tr("Female")).replace("Male", tr("Male")).replace("Neural", "")
                if "google:" not in v_name else v_name # Keep Google names as is for now or use a different formatting
            )
            for v_name in filtered_voices
        }

        saved_voice_name = config.ui.get("voice_name", "")
        current_voice_idx = 0
        voice_keys_list = list(friendly_names.keys())

        if saved_voice_name in friendly_names:
            current_voice_idx = voice_keys_list.index(saved_voice_name)
        elif filtered_voices: # If saved voice not found, try to pick a default based on lang
            for i, v_key in enumerate(voice_keys_list):
                if v_key.lower().startswith(st.session_state["ui_language"].lower()):
                    current_voice_idx = i
                    break
            if current_voice_idx == 0 and saved_voice_name not in friendly_names : # If still 0 and not found, it's the first item
                 params.voice_name = voice_keys_list[0] if voice_keys_list else ""
                 config.ui["voice_name"] = params.voice_name

        if not friendly_names:
            st.warning(tr("No voices available for the selected TTS server. Please select another server or check configuration."))
            params.voice_name = ""
        else:
            selected_friendly_voice_name = st.selectbox(
                tr("Speech Synthesis"),
                options=list(friendly_names.values()),
                index=current_voice_idx
            )
            # Find the actual voice name (key) corresponding to the selected friendly name
            for original_name, friendly_display_name in friendly_names.items():
                if friendly_display_name == selected_friendly_voice_name:
                    params.voice_name = original_name
                    config.ui["voice_name"] = original_name
                    break

        # Play Voice Button
        if params.voice_name and st.button(tr("Play Voice")):
            play_text = params.video_script or params.video_subject or tr("Voice Example")
            with st.spinner(tr("Synthesizing Voice")):
                temp_audio_file = os.path.join(utils.storage_dir("temp", create=True), f"test_voice_{uuid4()}.mp3")

                # Construct voice_name with prefix for Google for the tts() function
                actual_tts_voice_name = params.voice_name
                if selected_tts_server_code == "google" and not params.voice_name.startswith("google:"):
                     actual_tts_voice_name = f"google:{params.voice_name}"
                elif selected_tts_server_code == "siliconflow" and not params.voice_name.startswith("siliconflow:"):
                    actual_tts_voice_name = f"siliconflow:{params.voice_name}" # Assuming siliconflow voices in list already have prefix

                tts_sub_maker = voice.tts(
                    text=play_text,
                    voice_name=actual_tts_voice_name,
                    voice_rate=params.voice_rate,
                    voice_file=temp_audio_file,
                    voice_volume=params.voice_volume
                )
                if not tts_sub_maker or not os.path.exists(temp_audio_file): # Check if file was created
                    logger.error(f"Failed to synthesize test voice for {params.voice_name}")
                    st.error(tr("Failed to synthesize test voice."))
                else:
                    st.audio(temp_audio_file, format="audio/mp3")
                    # utils.safe_remove(temp_audio_file) # Add a helper for safe removal if needed

        # Conditional API Key/Region inputs
        if selected_tts_server_code == "azure-tts-v2" or (params.voice_name and "V2" in params.voice_name and "google:" not in params.voice_name and "siliconflow:" not in params.voice_name):
            azure_speech_region = st.text_input(tr("Speech Region"), value=config.azure.get("speech_region", ""), key="azure_speech_region_input")
            azure_speech_key = st.text_input(tr("Speech Key"), value=config.azure.get("speech_key", ""), type="password", key="azure_speech_key_input")
            config.azure["speech_region"] = azure_speech_region
            config.azure["speech_key"] = azure_speech_key
        elif selected_tts_server_code == "siliconflow":
            siliconflow_api_key = st.text_input(tr("SiliconFlow API Key"), value=config.siliconflow.get("api_key", ""), type="password", key="siliconflow_api_key_input")
            st.info(f"{tr('SiliconFlow TTS Settings')}:\n- {tr('Speed: Range [0.25, 4.0], default is 1.0')}\n- {tr('Volume: Uses Speech Volume setting, default 1.0 maps to gain 0')}")
            config.siliconflow["api_key"] = siliconflow_api_key
        # Google Cloud TTS uses ADC or GOOGLE_APPLICATION_CREDENTIALS env var by default, or path from main config. No separate UI input here.


        params.voice_volume = st.selectbox(tr("Speech Volume"), options=[0.6,0.8,1.0,1.2,1.5,2.0,3.0,4.0,5.0], index=2)
        params.voice_rate = st.selectbox(tr("Speech Rate"), options=[0.8,0.9,1.0,1.1,1.2,1.3,1.5,1.8,2.0], index=2)

        bgm_options = [
            (tr("No Background Music"), ""), (tr("Random Background Music"), "random"), (tr("Custom Background Music"), "custom")
        ]
        bgm_options_values = [opt[1] for opt in bgm_options]
        try:
            current_bgm_type_idx = bgm_options_values.index(params.bgm_type)
        except ValueError:
            current_bgm_type_idx = 1 # Default to Random

        selected_bgm_idx = st.selectbox(
            tr("Background Music"), index=current_bgm_type_idx,
            options=range(len(bgm_options)),
            format_func=lambda x: bgm_options[x][0],
        )
        params.bgm_type = bgm_options[selected_bgm_idx][1]

        if params.bgm_type == "custom":
            custom_bgm_file_path = st.text_input(tr("Custom Background Music File"), value=params.bgm_file, key="custom_bgm_file_input")
            if custom_bgm_file_path and os.path.exists(custom_bgm_file_path):
                params.bgm_file = custom_bgm_file_path
            elif custom_bgm_file_path:
                st.warning(tr("Custom BGM file path is invalid or file does not exist."))

        params.bgm_volume = st.selectbox(tr("Background Music Volume"), options=[0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0], index=2)

with right_panel:
    with st.container(border=True):
        st.write(tr("Subtitle Settings"))
        params.subtitle_enabled = st.checkbox(tr("Enable Subtitles"), value=params.subtitle_enabled)

        font_names = get_all_fonts()
        try:
            saved_font_name_index = font_names.index(params.font_name) if params.font_name in font_names else 0
        except ValueError: # Should not happen if font_names is not empty
            saved_font_name_index = 0

        params.font_name = st.selectbox(tr("Font"), font_names, index=saved_font_name_index)
        config.ui["font_name"] = params.font_name

        subtitle_positions = [
            (tr("Top"), "top"), (tr("Center"), "center"), (tr("Bottom"), "bottom"), (tr("Custom"), "custom"),
        ]
        subtitle_pos_values = [opt[1] for opt in subtitle_positions]
        try:
            current_subtitle_pos_idx = subtitle_pos_values.index(params.subtitle_position)
        except ValueError:
            current_subtitle_pos_idx = 2 # Default to Bottom

        selected_subtitle_pos_idx = st.selectbox(
            tr("Position"), index=current_subtitle_pos_idx,
            options=range(len(subtitle_positions)),
            format_func=lambda x: subtitle_positions[x][0],
        )
        params.subtitle_position = subtitle_positions[selected_subtitle_pos_idx][1]

        if params.subtitle_position == "custom":
            custom_pos_input = st.text_input(tr("Custom Position (% from top)"), value=str(params.custom_position), key="custom_position_input")
            try:
                params.custom_position = float(custom_pos_input)
                if not (0 <= params.custom_position <= 100):
                    st.error(tr("Please enter a value between 0 and 100"))
            except ValueError:
                st.error(tr("Please enter a valid number"))

        font_cols = st.columns([0.3, 0.7])
        with font_cols[0]:
            params.text_fore_color = st.color_picker(tr("Font Color"), params.text_fore_color)
            config.ui["text_fore_color"] = params.text_fore_color
        with font_cols[1]:
            params.font_size = st.slider(tr("Font Size"), 30, 100, params.font_size)
            config.ui["font_size"] = params.font_size

        stroke_cols = st.columns([0.3, 0.7])
        with stroke_cols[0]:
            params.stroke_color = st.color_picker(tr("Stroke Color"), params.stroke_color)
        with stroke_cols[1]:
            params.stroke_width = st.slider(tr("Stroke Width"), 0.0, 10.0, params.stroke_width)

start_button = st.button(tr("Generate Video"), use_container_width=True, type="primary")
if start_button:
    config.save_config() # Save all UI configurations
    task_id = str(uuid4())
    if not params.video_subject and not params.video_script:
        st.error(tr("Video Script and Subject Cannot Both Be Empty"))
        scroll_to_bottom()
        st.stop()

    if params.video_source not in ["pexels", "pixabay", "local"]:
        st.error(tr("Please Select a Valid Video Source")) # Key for this error
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pexels" and not config.app.get("pexels_api_keys", []): # Check if list is empty
        st.error(tr("Please Enter the Pexels API Key"))
        scroll_to_bottom()
        st.stop()

    if params.video_source == "pixabay" and not config.app.get("pixabay_api_keys", []): # Check if list is empty
        st.error(tr("Please Enter the Pixabay API Key"))
        scroll_to_bottom()
        st.stop()

    if uploaded_files:
        params.video_materials = [] # Reset if new files are uploaded
        local_videos_dir = utils.storage_dir("local_videos", create=True)
        for file in uploaded_files:
            # Ensure unique filenames to avoid overwrite issues if multiple files have same name
            unique_filename = f"{uuid4().hex}_{file.name}"
            file_path = os.path.join(local_videos_dir, unique_filename)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            m = MaterialInfo(provider="local", url=file_path)
            params.video_materials.append(m)
        logger.info(f"Uploaded {len(params.video_materials)} local files.")


    log_container = st.empty()
    log_records = []

    # Ensure logger is re-added if it was removed, or configure it here
    # init_log() # Call if logger might have been cleared elsewhere or for specific config

    # Define a handler to capture logs for display in Streamlit
    def streamlit_log_handler(message):
        log_records.append(message.record["message"])
        if not config.ui.get("hide_log", False):
            with log_container:
                st.code("\n".join(log_records[-20:])) # Display last 20 log lines

    # Add the handler to Loguru. Ensure it's not added multiple times if this block re-runs.
    # A simple way is to remove all handlers and add this one, or use a flag.
    logger.remove() # Remove existing handlers
    logger.add(sys.stdout, level="DEBUG", format=format_record, colorize=True) # Keep console output
    logger.add(streamlit_log_handler, level="INFO", format="{message}") # Add Streamlit handler

    st.toast(tr("Generating Video")) # Key "Generating Video" (toast)
    logger.info(tr("Start Generating Video")) # Key "Start Generating Video"
    logger.info(f"Task parameters: {utils.to_json(params.model_dump())}") # Log the serializable model
    scroll_to_bottom()

    result = tm.start(task_id=task_id, params=params, stop_at="video") # Assuming tm.start is synchronous or handled

    if not result or "videos" not in result or not result["videos"]:
        st.error(tr("Video Generation Failed"))
        logger.error(tr("Video Generation Failed")) # Key "Video Generation Failed"
        scroll_to_bottom()
        st.stop()

    video_files = result.get("videos", [])
    st.success(tr("Video Generation Completed")) # Key "Video Generation Completed"
    try:
        if video_files:
            # Display videos in columns. Adjust number of columns based on number of videos.
            num_videos = len(video_files)
            cols_per_video = 2 # Adjust for desired width + spacing
            player_cols = st.columns(num_videos * cols_per_video + (num_videos -1 if num_videos > 1 else 0) )

            for i, url in enumerate(video_files):
                with player_cols[i * (cols_per_video + (1 if num_videos > 1 else 0))]: # Add spacer column if multiple videos
                    st.video(url)
    except Exception as e_video_display:
        logger.error(f"Error displaying videos: {e_video_display}")
        st.error(tr("Error displaying generated videos.")) # Key for this error

    open_task_folder(task_id)
    logger.info(tr("Video Generation Completed")) # Key "Video Generation Completed" (log)
    scroll_to_bottom()

config.save_config()
