import uuid
import time
import os # Added
import json # Added for __main__ example
from typing import Any, Dict, List, Optional, Tuple # Added Tuple

from loguru import logger
from unittest.mock import MagicMock # Added for __main__ example

# Magenta and audio libraries (may require further setup if not pre-installed)
try:
    import pretty_midi
    import numpy as np
    import soundfile as sf
except ImportError:
    logger.warning("Magenta, pretty_midi, numpy, or soundfile not installed. Magenta generation will fail.")
    pretty_midi = None
    np = None
    sf = None

# Assuming 'app' is in PYTHONPATH. Adjust if necessary.
from app.config.config import Config # Type hint
from app.services.playlist.gcs_content_manager import GCSManager
try:
    from ..services.tts.google_cloud_tts import GoogleCloudTTS
    # Check if Google Cloud TTS specific dependencies are available
    from ..services.tts.google_cloud_tts import GOOGLE_API_LIBS_AVAILABLE as GOOGLE_TTS_API_LIBS_AVAILABLE
except ImportError:
    logger.warning("GoogleCloudTTS service not found or its dependencies are missing. TTS generation will not be available.")
    GoogleCloudTTS = None # Make it a dummy
    GOOGLE_TTS_API_LIBS_AVAILABLE = False

try:
    from google.cloud.texttospeech_v1.types import AudioEncoding
except ImportError:
    logger.warning("Google Cloud TextToSpeech types not available. Explicit audio encoding for TTS might fail.")
    AudioEncoding = None # Make it a dummy

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
except ImportError:
    logger.warning("pydub not installed. Normalization and format conversion will be skipped.")
    AudioSegment = None
    CouldntDecodeError = None


class AudioGenerator:
    """
    Manages the generation of various types of audio content, including
    AI-generated music using Magenta, synthesized soundscapes, and potentially TTS.
    Handles saving generated audio and its metadata to Google Cloud Storage.
    """

    def __init__(self, app_config: Config, gcs_manager: Optional[GCSManager] = None):
        """
        Initializes the AudioGenerator.

        Args:
            app_config: An instance of the main application Config object.
            gcs_manager: Optional. An instance of GCSManager. If None, one will be created.
        """
        self.app_config = app_config
        self.logger = logger.bind(name=self.__class__.__name__)

        # Configuration for audio generation and storage
        # Assuming app_config is an object with attributes like 'playlist', 'audiogenerator'
        # which are dicts for those config sections.
        if not hasattr(self.app_config, 'audiogenerator') or not hasattr(self.app_config, 'playlist'):
            self.logger.critical("app_config object is missing 'audiogenerator' or 'playlist' attributes. AudioGenerator cannot be properly configured.")
            # Or raise ConfigurationError
            # For now, try to get them, allowing for potential AttributeError if not structured as expected.
            # This structure relies on app_config being the 'app.config.config' module or an object mimicking it.
            audiogen_config = {}
            playlist_config = {}
        else:
            audiogen_config = self.app_config.audiogenerator
            playlist_config = self.app_config.playlist

        self.gcs_bucket_name = playlist_config.get('gcs_music_library_bucket')
        if not self.gcs_bucket_name:
            self.logger.error("GCS bucket name for music library not found in config (playlist.gcs_music_library_bucket). AudioGenerator may not function correctly for GCS operations.")
            # Potentially raise an error or handle this state more gracefully

        self.gcs_generated_audio_prefix = audiogen_config.get('gcs_generated_audio_prefix', 'generated_audio/')
        self.default_output_format = audiogen_config.get('default_output_format', 'mp3')
        self.default_sample_rate = int(audiogen_config.get('default_audio_sample_rate', 44100))
        self.default_bitrate = audiogen_config.get('default_audio_bitrate', '192k')

        # Initialize GCSManager
        if gcs_manager:
            self.gcs_manager = gcs_manager
            self.logger.info("Using provided GCSManager instance.")
        else:
            if self.gcs_bucket_name:
                gcs_creds_path = playlist_config.get('gcs_credentials_path') # Use the fetched playlist_config
                self.logger.info(f"Initializing new GCSManager for bucket: {self.gcs_bucket_name}")
                self.gcs_manager = GCSManager(
                    bucket_name=self.gcs_bucket_name,
                    credentials_path=gcs_creds_path,
                    logger_instance=self.logger
                )
            else:
                self.gcs_manager = None
                self.logger.warning("GCSManager not initialized as GCS bucket name is missing.")

        # Magenta Model Placeholders
        self.music_vae_model = None
        self.melody_rnn_model = None
        # TODO: Implement _load_magenta_models() and call it here or on-demand
        self.logger.info("Magenta models are not loaded in this initial version (placeholder).")
        self.magenta_checkpoint_musicvae = audiogen_config.get('magenta_checkpoint_musicvae')
        self.magenta_checkpoint_melodyrnn = audiogen_config.get('magenta_checkpoint_melodyrnn')


        # TTS Client Placeholder
        self.tts_client = None
        # Initialize TTS Client
        if GoogleCloudTTS and GOOGLE_TTS_API_LIBS_AVAILABLE:
            try:
                # GoogleCloudTTS reads its config from app.config.config.google_tts internally
                self.tts_client = GoogleCloudTTS(logger_instance=self.logger.bind(name="GoogleCloudTTS_via_AudioGenerator"))
                self.logger.info("GoogleCloudTTS client initialized.")
            except Exception as e:
                self.logger.error(f"Failed to initialize GoogleCloudTTS client: {e}", exc_info=True)
                self.tts_client = None
        else:
            self.tts_client = None
            self.logger.warning("GoogleCloudTTS client not initialized as the service or its dependencies are unavailable.")

        self._load_magenta_models() # Call model loader

        self.logger.success("AudioGenerator initialized.")

    def _load_magenta_models(self) -> None:
        """
        Placeholder for loading Magenta models.
        Actual model loading from checkpoints is deferred.
        """
        # from unittest.mock import MagicMock # Moved to global imports for __main__

        # Example: Load MusicVAE model
        music_vae_checkpoint_path = self.magenta_checkpoint_musicvae
        if music_vae_checkpoint_path:
            self.logger.info(f"Attempting to load MusicVAE model from: {music_vae_checkpoint_path} (placeholder).")
            # self.music_vae_model = magenta.models.music_vae.MusicVAE(checkpoint_dir_or_path=music_vae_checkpoint_path) # Actual loading
            self.music_vae_model = MagicMock() # Placeholder
            self.logger.info("MusicVAE model 'loaded' (mocked).")
        else:
            self.logger.warning("MusicVAE model checkpoint path not configured. MusicVAE generation will not be available.")
            self.music_vae_model = None

        # Example: Load MelodyRNN model
        melody_rnn_bundle_path = self.magenta_checkpoint_melodyrnn
        if melody_rnn_bundle_path:
            self.logger.info(f"Attempting to load MelodyRNN model from: {melody_rnn_bundle_path} (placeholder).")
            # self.melody_rnn_model = magenta.models.melody_rnn.MelodyRnnModel(bundle_file=melody_rnn_bundle_path) # Actual loading
            self.melody_rnn_model = MagicMock() # Placeholder
            self.logger.info("MelodyRNN model 'loaded' (mocked).")
        else:
            self.logger.warning("MelodyRNN bundle path not configured. MelodyRNN generation will not be available.")
            self.melody_rnn_model = None

        self.logger.info("Magenta model loading step complete (placeholders used).")


    def _prepare_metadata(
        self,
        content_id: str,
        title: str,
        gcs_audio_path: str,
        duration_seconds: float,
        audio_format: str,
        sample_rate: int,
        bitrate: str,
        model_used: Optional[str] = None,
        genre: Optional[str] = None,
        mood_tags: Optional[List[str]] = None,
        generation_seed: Optional[Any] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepares a metadata dictionary for a generated audio track.
        This should align with PlaylistItem fields where applicable.

        Args:
            content_id: Unique ID for the content.
            title: Title of the generated track.
            gcs_audio_path: Full GCS path to the audio file.
            duration_seconds: Duration of the audio in seconds.
            audio_format: Format of the audio (e.g., "mp3", "wav").
            sample_rate: Sample rate in Hz (e.g., 44100).
            bitrate: Bitrate (e.g., "192k").
            model_used: Name/identifier of the generation model/method.
            genre: Optional genre tag.
            mood_tags: Optional list of mood descriptors.
            generation_seed: Optional seed used for generation.
            additional_info: Optional dict for any other relevant metadata.

        Returns:
            A dictionary containing the structured metadata.
        """
        metadata_filename = os.path.basename(gcs_audio_path) + ".meta.json"
        # Assumes gcs_generated_audio_prefix ends with '/'
        gcs_metadata_path = os.path.join(os.path.dirname(gcs_audio_path), metadata_filename)
        # If using os.path.join with GCS paths, it might not produce "gs://bucket/prefix/file" correctly
        # from "gs://bucket/prefix/" and "file". Need to be careful.
        # For GCS, it's often better to construct paths carefully:
        # e.g. f"{os.path.dirname(gcs_audio_path).rstrip('/')}/{metadata_filename}"
        # However, GCSManager's upload method will take blob name, so local path construction is fine.
        # Let's refine gcs_metadata_path based on gcs_audio_path structure:
        # If gcs_audio_path is "gs://bucket_name/prefix/filename.mp3"
        # then metadata path should be "gs://bucket_name/prefix/filename.mp3.meta.json"
        # The GCSManager.upload_text expects blob_name which is "prefix/filename.mp3.meta.json"

        # Correct way to get blob name for metadata, assuming gcs_audio_path is full gs:// path
        audio_blob_name = gcs_audio_path.replace(f"gs://{self.gcs_bucket_name}/", "")
        metadata_blob_name = audio_blob_name + ".meta.json"
        full_gcs_metadata_path = f"gs://{self.gcs_bucket_name}/{metadata_blob_name}"


        metadata = {
            "content_id": content_id,
            "title": title,
            "gcs_path": gcs_audio_path, # Standard field name for PlaylistItem
            "gcs_path_audio": gcs_audio_path, # Redundant but more explicit for internal use
            "gcs_path_metadata": full_gcs_metadata_path,
            "duration_seconds": duration_seconds,
            "audio_properties": { # Nest audio technical details
                "format": audio_format,
                "sample_rate_hz": sample_rate,
                "bitrate_kbps": bitrate # Store consistently, e.g. just number for "192k" -> 192
            },
            "generation_details": { # Nest generation specific info
                "model_used": model_used,
                "generation_seed": generation_seed,
                "creation_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "creation_timestamp_unix": time.time()
            },
            "tags": { # Suggested by PlaylistItem structure
                "genre": genre,
                "mood": mood_tags if mood_tags else []
            },
            "content_type": "generated_audio", # Default content type for these items
            # PlaylistItem transition defaults will be applied by GCSContentManager if not specified here
            # "transition_type_in": "crossfade",
            # "transition_duration_in_ms": 3000,
        }
        if additional_info:
            metadata.update(additional_info) # Merge any other custom fields

        self.logger.debug(f"Prepared metadata for {content_id}: {metadata}")
        return metadata

    # --- Placeholder methods for actual generation logic ---
    # def generate_music_vae_track(self, ...) -> Optional[str]:
    #     self.logger.info("Generating MusicVAE track (not implemented).")
    #     # 1. Load MusicVAE model if not loaded (self.music_vae_model)
    #     # 2. Generate MIDI sequence
    #     # 3. Synthesize MIDI to audio (e.g., using fluidsynth via pretty_midi)
    #     # 4. Normalize audio (e.g., using pydub)
    #     # 5. Save to temp file
    #     # 6. Upload to GCS (using self.gcs_manager) -> returns GCS path
    #     # 7. Prepare metadata
    #     # 8. Upload metadata JSON to GCS (using self.gcs_manager)
    #     return None

    # def generate_melody_rnn_track(self, ...) -> Optional[str]:
    #     self.logger.info("Generating MelodyRNN track (not implemented).")
    #     return None

    # def generate_soundscape(self, type: str, duration_seconds: int) -> Optional[str]:
    #     self.logger.info(f"Generating {type} soundscape (not implemented).")
    #     # e.g., brown noise, pink noise, specific environment like "rain"
    #     return None

    # def _synthesize_midi_to_audio(self, midi_data, output_path_wav: str) -> bool: ...

    def _normalize_and_save_audio(self, local_audio_file_path: str, output_gcs_path_base: str, metadata: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """
        Normalizes audio, converts to target format, uploads audio and metadata to GCS.

        Args:
            local_audio_file_path: Path to the temporary local audio file (likely WAV).
            output_gcs_path_base: Base GCS path for output, without extension
                                  (e.g., "generated_audio/lofi/lofi_track_123").
            metadata: The metadata dictionary prepared by the calling generation method.

        Returns:
            A tuple (final_gcs_audio_path, final_gcs_metadata_path) if successful, else None.
        """
        if not AudioSegment or not CouldntDecodeError: # pydub not available
            self.logger.error("pydub library not available. Skipping normalization and conversion.")
            # Fallback: try to upload the original file if GCS manager is present
            if self.gcs_manager and os.path.exists(local_audio_file_path):
                original_extension = os.path.splitext(local_audio_file_path)[1].strip('.')
                output_audio_gcs_path = f"{output_gcs_path_base}.{original_extension}"
                final_audio_gcs_full_path = f"gs://{self.gcs_bucket_name}/{output_audio_gcs_path}"
                metadata['gcs_path_audio'] = final_audio_gcs_full_path
                metadata['audio_format'] = original_extension # Update format if different

                if not self.gcs_manager.upload_file(local_audio_file_path, output_audio_gcs_path):
                    return None # Upload failed

                output_metadata_gcs_path = f"{output_gcs_path_base}.meta.json"
                final_metadata_gcs_full_path = f"gs://{self.gcs_bucket_name}/{output_metadata_gcs_path}"
                metadata['gcs_path_metadata'] = final_metadata_gcs_full_path
                metadata_json_str = json.dumps(metadata, indent=4, ensure_ascii=False)
                if not self.gcs_manager.upload_string_as_blob(metadata_json_str, output_metadata_gcs_path, 'application/json'):
                    return None # Metadata upload failed
                return final_audio_gcs_full_path, final_metadata_gcs_full_path
            return None

        temp_files_to_clean = [local_audio_file_path]

        try:
            self.logger.debug(f"Loading audio from: {local_audio_file_path}")
            audio_segment = AudioSegment.from_file(local_audio_file_path)
        except CouldntDecodeError as e:
            self.logger.error(f"Could not decode audio file {local_audio_file_path}: {e}")
            return None
        except Exception as e: # Catch other potential pydub errors
            self.logger.error(f"Error loading audio file {local_audio_file_path} with pydub: {e}", exc_info=True)
            return None

        # Normalize Volume
        audiogen_cfg = self.app_config.audiogenerator
        target_peak_dbfs = float(audiogen_cfg.get('normalization_target_peak_dbfs', -1.0))

        if audio_segment.max_dBFS == float('-inf'): # Check for silence
            self.logger.warning(f"Audio file {local_audio_file_path} appears to be silent. Skipping gain application.")
            normalized_segment = audio_segment
        else:
            change_in_dbfs = target_peak_dbfs - audio_segment.max_dBFS
            normalized_segment = audio_segment.apply_gain(change_in_dbfs)
            self.logger.info(f"Normalized audio: peak {audio_segment.max_dBFS:.2f}dBFS -> {normalized_segment.max_dBFS:.2f}dBFS (target {target_peak_dbfs:.2f}dBFS).")

        metadata['normalization_details'] = {
            'type': 'peak_dbfs',
            'target_dbfs': target_peak_dbfs,
            'original_peak_dbfs': audio_segment.max_dBFS if audio_segment.max_dBFS != float('-inf') else None
        }

        # Convert to Target Format
        output_format = str(audiogen_cfg.get('default_output_format', 'mp3')).lower().strip('.')
        temp_converted_audio_path = f"{os.path.splitext(local_audio_file_path)[0]}_norm.{output_format}"
        temp_files_to_clean.append(temp_converted_audio_path)

        export_params = {'format': output_format}
        audio_bitrate = str(audiogen_cfg.get('default_audio_bitrate', '192k'))
        if audio_bitrate:
            export_params['bitrate'] = audio_bitrate

        sample_rate_val = int(audiogen_cfg.get('default_audio_sample_rate', 44100))

        # Apply frame rate conversion before export if necessary
        if normalized_segment.frame_rate != sample_rate_val:
            self.logger.info(f"Converting frame rate from {normalized_segment.frame_rate}Hz to {sample_rate_val}Hz.")
            try:
                normalized_segment = normalized_segment.set_frame_rate(sample_rate_val)
            except Exception as e: # pydub can sometimes fail here with weird inputs
                self.logger.error(f"Failed to set frame rate to {sample_rate_val}Hz: {e}. Using original frame rate: {normalized_segment.frame_rate}Hz.")
                # Update sample_rate_val to actual used rate if conversion failed
                sample_rate_val = normalized_segment.frame_rate


        self.logger.debug(f"Exporting to {temp_converted_audio_path} with format={output_format}, bitrate={audio_bitrate}, sample_rate={sample_rate_val}")

        try:
            # For MP3, pydub's underlying ffmpeg call handles sample rate if it's part of the audio data.
            # Explicitly setting via 'parameters' might be needed if issues arise, but often not.
            # If issues with specific formats, might need: export_params['parameters'] = ['-ar', str(sample_rate_val)]
            normalized_segment.export(temp_converted_audio_path, **export_params)
            self.logger.info(f"Converted and normalized audio saved to: {temp_converted_audio_path}")
        except Exception as e:
            self.logger.error(f"Failed to export audio to {output_format}: {e}", exc_info=True)
            return None # Cleanup will be handled in finally

        # Update Metadata with Final Duration and Audio Properties from the processed file
        try:
            final_segment_for_props = AudioSegment.from_file(temp_converted_audio_path)
            metadata['duration_seconds'] = round(final_segment_for_props.duration_seconds, 3)
            if 'audio_properties' not in metadata: metadata['audio_properties'] = {}
            metadata['audio_properties']['format'] = output_format # Ensure this is the final format
            metadata['audio_properties']['sample_rate_hz'] = final_segment_for_props.frame_rate
            metadata['audio_properties']['channels'] = final_segment_for_props.channels
            metadata['audio_properties']['frame_width_bytes'] = final_segment_for_props.frame_width # Sample width in bytes
            # Bitrate from config is target; actual bitrate might vary. pydub doesn't easily expose actual file bitrate.
            metadata['audio_properties']['bitrate_kbps_target'] = audio_bitrate
        except Exception as e:
            self.logger.warning(f"Could not read properties from final converted file {temp_converted_audio_path}: {e}. Duration and other props might be from pre-conversion stage.")


        # Construct final GCS paths
        output_audio_gcs_filename = f"{os.path.basename(output_gcs_path_base)}.{output_format}"
        # Ensure output_gcs_path_base does not start with gs:// or bucket name for blob path
        clean_output_gcs_path_base = output_gcs_path_base.replace(f"gs://{self.gcs_bucket_name}/", "")

        final_audio_gcs_blob_path = os.path.join(os.path.dirname(clean_output_gcs_path_base), output_audio_gcs_filename)
        final_audio_gcs_full_path = f"gs://{self.gcs_bucket_name}/{final_audio_gcs_blob_path}"

        output_metadata_gcs_blob_path = f"{clean_output_gcs_path_base}.meta.json"
        final_metadata_gcs_full_path = f"gs://{self.gcs_bucket_name}/{output_metadata_gcs_blob_path}"

        metadata['gcs_path'] = final_audio_gcs_full_path # Update standard PlaylistItem field
        metadata['gcs_path_audio'] = final_audio_gcs_full_path
        metadata['gcs_path_metadata'] = final_metadata_gcs_full_path


        # Upload to GCS
        if not self.gcs_manager:
            self.logger.error("GCSManager not available. Cannot upload files.")
            return None

        upload_success = False
        try:
            if self.gcs_manager.upload_file(local_file_path=temp_converted_audio_path, destination_blob_name=final_audio_gcs_blob_path):
                self.logger.success(f"Uploaded processed audio to: {final_audio_gcs_full_path}")

                metadata_json_str = json.dumps(metadata, indent=4, ensure_ascii=False)
                if self.gcs_manager.upload_string_as_blob(data_string=metadata_json_str, destination_blob_name=output_metadata_gcs_blob_path, content_type='application/json'):
                    self.logger.success(f"Uploaded metadata to: {final_metadata_gcs_full_path}")
                    upload_success = True
                else:
                    self.logger.error(f"Failed to upload metadata to {final_metadata_gcs_full_path}. Audio was uploaded to {final_audio_gcs_full_path} but will be orphaned without metadata.")
                    # Consider deleting the audio blob if metadata upload fails:
                    # self.gcs_manager.delete_blob(final_audio_gcs_blob_path)
            else:
                self.logger.error(f"Failed to upload processed audio to {final_audio_gcs_full_path}")

        finally:
            # Cleanup temporary files
            for f_path in temp_files_to_clean:
                if os.path.exists(f_path):
                    try:
                        os.remove(f_path)
                        self.logger.debug(f"Cleaned up temporary file: {f_path}")
                    except Exception as e_clean:
                        self.logger.warning(f"Failed to clean up temporary file {f_path}: {e_clean}")

        if upload_success:
            return final_audio_gcs_full_path, final_metadata_gcs_full_path
        else:
            return None


    def generate_magenta_track(self, genre: str, mood: Optional[List[str]] = None,
                               target_duration_seconds: int = 180,
                               temperature: float = 1.0,
                               seed_midi_path: Optional[str] = None) -> Optional[Tuple[str, str]]:
        """
        Generates a music track using Magenta based on genre and other parameters.
        Currently uses placeholder MIDI generation and synthesis.

        Args:
            genre: "lofi", "edm", "ambient".
            mood: Optional list of mood strings.
            target_duration_seconds: Desired length of the audio track.
            temperature: Controls randomness/creativity.
            seed_midi_path: Optional path to a seed MIDI file.

        Returns:
            A tuple (gcs_audio_path, gcs_metadata_path) if successful, else None.
        """
        self.logger.info(f"Request to generate Magenta track: genre='{genre}', mood={mood}, duration={target_duration_seconds}s, temp={temperature}, seed='{seed_midi_path}'")

        if not pretty_midi or not np or not sf:
            self.logger.error("pretty_midi, numpy, or soundfile not available. Cannot generate Magenta track.")
            return None

        # Model selection (conceptual)
        model_name_for_metadata = "GenericMagentaPlaceholder"
        if genre == "lofi" and self.music_vae_model:
            # model_to_use = self.music_vae_model
            model_name_for_metadata = "MusicVAE_Lofi_Placeholder"
            self.logger.info("Using placeholder for MusicVAE for Lo-fi genre.")
        elif (genre == "edm" or genre == "ambient") and self.melody_rnn_model:
            # model_to_use = self.melody_rnn_model
            model_name_for_metadata = "MelodyRNN_Placeholder"
            self.logger.info(f"Using placeholder for MelodyRNN for {genre} genre.")
        elif self.music_vae_model: # Default to VAE if specific model not chosen but VAE exists
            # model_to_use = self.music_vae_model
            model_name_for_metadata = "MusicVAE_General_Placeholder"
            self.logger.info(f"Using placeholder for MusicVAE as default for {genre} genre.")
        else:
            self.logger.error("No suitable Magenta models are loaded/mocked. Cannot generate track.")
            return None

        # --- Simulate MIDI generation ---
        self.logger.info(f"MIDI generation using {model_name_for_metadata} would occur here. Using placeholder MIDI.")
        midi_data = pretty_midi.PrettyMIDI()
        instrument_program = pretty_midi.instrument_name_to_program('Synth Pad') # Generic
        if genre == "lofi":
            instrument_program = pretty_midi.instrument_name_to_program('Rhodes Piano')
        elif genre == "edm":
            instrument_program = pretty_midi.instrument_name_to_program('Synth Bass 1')

        instrument = pretty_midi.Instrument(program=instrument_program)

        # Simple C-major scale-like pattern for placeholder
        pitches = [60, 62, 64, 65, 67, 69, 71, 72] # C D E F G A B C
        for i, pitch in enumerate(pitches * 2): # Repeat for a bit longer sequence
            note = pretty_midi.Note(velocity=int(np.random.uniform(80, 100)), pitch=pitch, start=i * 0.4, end=(i + 1) * 0.4)
            instrument.notes.append(note)
        midi_data.instruments.append(instrument)

        temp_midi_dir = "temp_audio_files"
        os.makedirs(temp_midi_dir, exist_ok=True)
        temp_midi_path = os.path.join(temp_midi_dir, f"temp_generated_{uuid.uuid4().hex[:8]}.mid")
        try:
            midi_data.write(temp_midi_path)
            self.logger.info(f"Placeholder MIDI written to {temp_midi_path}")
        except Exception as e:
            self.logger.error(f"Failed to write placeholder MIDI: {e}")
            return None

        # --- MIDI to Audio Synthesis ---
        temp_wav_path = os.path.join(temp_midi_dir, f"temp_generated_{uuid.uuid4().hex[:8]}.wav")
        actual_duration_seconds = 0
        try:
            sample_rate = self.default_sample_rate
            audio_data_np = midi_data.synthesize(fs=sample_rate)
            sf.write(temp_wav_path, audio_data_np, sample_rate)
            actual_duration_seconds = len(audio_data_np) / sample_rate
            self.logger.info(f"Synthesized MIDI to WAV: {temp_wav_path}, duration: {actual_duration_seconds:.2f}s")
        except Exception as e:
            self.logger.error(f"Failed to synthesize MIDI to audio: {e}")
            if os.path.exists(temp_midi_path): os.remove(temp_midi_path)
            return None

        # --- Duration Handling (Placeholder) ---
        self.logger.warning(f"Duration handling to meet target {target_duration_seconds}s not fully implemented. Using generated length: {actual_duration_seconds:.2f}s.")
        # TODO: Implement looping/stitching or generate longer sequences to meet target_duration_seconds

        # --- Prepare Metadata ---
        content_id = uuid.uuid4().hex
        output_filename_base = f"{genre.lower().replace(' ', '_')}_{content_id[:8]}"
        # Construct GCS path base for _normalize_and_save_audio
        # e.g. "generated_audio/lofi/lofi_track_abc123" (without extension)
        gcs_path_base_for_saving = os.path.join(self.gcs_generated_audio_prefix, genre.lower(), output_filename_base)

        # The gcs_audio_path in metadata will be the final path after format conversion (e.g. .mp3)
        # This will be determined by _normalize_and_save_audio, but we need a placeholder for now.
        # For now, _prepare_metadata expects a gcs_audio_path. Let's give it a conceptual one.
        conceptual_final_gcs_path = f"gs://{self.gcs_bucket_name}/{gcs_path_base_for_saving}.{self.default_output_format}"

        metadata = self._prepare_metadata(
            content_id=content_id,
            title=f"{genre.capitalize()} Magenta Track - {content_id[:8]}",
            gcs_audio_path=conceptual_final_gcs_path, # This will be updated by _normalize_and_save_audio effectively
            duration_seconds=actual_duration_seconds,
            audio_format=self.default_output_format, # Target format
            sample_rate=self.default_sample_rate,
            bitrate=self.default_bitrate,
            model_used=model_name_for_metadata,
            genre=genre,
            mood_tags=mood,
            generation_seed=str(seed_midi_path) if seed_midi_path else "random_placeholder_notes"
        )

        # --- Normalize and Save (Stubbed) ---
        # _normalize_and_save_audio will handle actual GCS path construction and metadata update for gcs_path_audio
        result_paths = self._normalize_and_save_audio(
            audio_file_path=temp_wav_path,
            output_gcs_path_base=gcs_path_base_for_saving, # Pass the prefix and base filename
            metadata=metadata
        )

        # --- Cleanup ---
        try:
            if os.path.exists(temp_midi_path): os.remove(temp_midi_path)
            if os.path.exists(temp_wav_path): os.remove(temp_wav_path)
            if os.path.exists(temp_midi_dir) and not os.listdir(temp_midi_dir): # remove dir if empty
                 os.rmdir(temp_midi_dir)
        except Exception as e:
            self.logger.warning(f"Error during cleanup of temporary files: {e}")

        if result_paths:
            self.logger.success(f"Successfully processed Magenta track: {result_paths[0]}")
            return result_paths
        else:
            self.logger.error(f"Failed to normalize and save Magenta track for genre: {genre}")
            return None

    def generate_soundscape(self, scape_type: str, target_duration_seconds: int = 600,
                            base_frequency: float = 100.0, beat_frequency: float = 10.0,
                            mix_paths: Optional[List[str]] = None) -> Optional[Tuple[str, str]]:
        """
        Generates various types of soundscapes.

        Args:
            scape_type: "brown_noise", "binaural_beats", "mixed_soundscape", "asmr".
            target_duration_seconds: Desired length of the soundscape.
            base_frequency: For binaural beats, the base frequency in Hz.
            beat_frequency: For binaural beats, the difference in Hz for the beat.
            mix_paths: For "mixed_soundscape", list of GCS paths to base audio layers.

        Returns:
            A tuple (gcs_audio_path, gcs_metadata_path) if successful, else None.
        """
        self.logger.info(f"Request to generate soundscape: type='{scape_type}', duration={target_duration_seconds}s")

        if not np or not sf:
            self.logger.error("numpy or soundfile not available. Cannot generate soundscape.")
            return None

        audiogen_cfg = self.app_config.audiogenerator
        sample_rate = int(audiogen_cfg.get('default_audio_sample_rate', 44100))
        num_channels = 2  # Stereo for binaural, good default for others
        num_samples = int(target_duration_seconds * sample_rate)

        audio_data_np = None
        model_used = ""
        generation_params = {'type': scape_type}

        temp_files_to_clean = []

        if scape_type == "brown_noise":
            noise = np.random.normal(0, 1, num_samples) # White noise
            audio_data_np_mono = np.cumsum(noise)
            audio_data_np_mono = audio_data_np_mono / np.max(np.abs(audio_data_np_mono)) * 0.5 # Normalize
            if num_channels == 2:
                audio_data_np = np.array([audio_data_np_mono, audio_data_np_mono]).T # Stereo
            else:
                audio_data_np = audio_data_np_mono[:, np.newaxis] # Mono column vector
            model_used = "BrownNoiseGenerator"

        elif scape_type == "binaural_beats":
            if num_channels != 2:
                self.logger.warning("Binaural beats require stereo output. Forcing stereo.")
                # num_channels = 2 # Already default
            f_left = base_frequency
            f_right = base_frequency + beat_frequency
            t = np.linspace(0, target_duration_seconds, num_samples, endpoint=False)

            left_channel = 0.4 * np.sin(2 * np.pi * f_left * t) # Use 0.4 to leave headroom
            right_channel = 0.4 * np.sin(2 * np.pi * f_right * t)
            audio_data_np = np.vstack((left_channel, right_channel)).T
            model_used = "BinauralBeatGenerator"
            generation_params.update({'base_frequency_hz': base_frequency, 'beat_frequency_hz': beat_frequency})

        elif scape_type == "mixed_soundscape":
            if mix_paths and 2 <= len(mix_paths) <= 3:
                self.logger.info(f"Conceptual: Mixing of {mix_paths} would occur here using pydub or similar.")
                # For this subtask, generate placeholder brown noise instead of actual mixing
                noise = np.random.normal(0, 1, num_samples)
                audio_data_np_mono = np.cumsum(noise)
                audio_data_np_mono = audio_data_np_mono / np.max(np.abs(audio_data_np_mono)) * 0.5
                if num_channels == 2:
                    audio_data_np = np.array([audio_data_np_mono, audio_data_np_mono]).T
                else:
                    audio_data_np = audio_data_np_mono[:, np.newaxis]
                model_used = "SoundscapeMixer_Placeholder"
                generation_params.update({'source_paths': mix_paths})
                # TODO: Implement actual download and mixing of GCS paths.
                # This would involve:
                # 1. Downloading files from GCS to temporary local paths.
                #    temp_downloaded_paths = []
                #    for path in mix_paths:
                #        blob_name = path.replace(f"gs://{self.gcs_bucket_name}/", "")
                #        temp_local_path = f"temp_{os.path.basename(blob_name)}"
                #        self.gcs_manager.storage_client.bucket(self.gcs_bucket_name).blob(blob_name).download_to_filename(temp_local_path)
                #        temp_downloaded_paths.append(temp_local_path)
                #        temp_files_to_clean.append(temp_local_path)
                # 2. Loading with pydub:
                #    from pydub import AudioSegment
                #    segments = [AudioSegment.from_file(p) for p in temp_downloaded_paths]
                # 3. Adjusting to target_duration_seconds (loop/truncate) and mixing.
                #    mixed_sound = segments[0][:target_duration_seconds*1000]
                #    for seg in segments[1:]:
                #        mixed_sound = mixed_sound.overlay(seg[:target_duration_seconds*1000])
                # 4. Converting pydub AudioSegment to numpy array for sf.write or saving directly.
                #    samples = np.array(mixed_sound.get_array_of_samples())
                #    if mixed_sound.channels == 2:
                #        audio_data_np = samples.reshape((-1, 2))
                #    else: # Mono
                #        audio_data_np = samples.reshape((-1, 1))
                #    audio_data_np = audio_data_np / (2**(mixed_sound.sample_width*8-1)) # Normalize
            else:
                self.logger.error("For 'mixed_soundscape', 'mix_paths' must be a list of 2-3 GCS paths.")
                return None

        elif scape_type == "asmr": # Placeholder
            self.logger.info("ASMR generation is conceptual. Using placeholder brown noise.")
            noise = np.random.normal(0, 1, num_samples)
            audio_data_np_mono = np.cumsum(noise)
            audio_data_np_mono = audio_data_np_mono / np.max(np.abs(audio_data_np_mono)) * 0.5
            if num_channels == 2:
                audio_data_np = np.array([audio_data_np_mono, audio_data_np_mono]).T
            else:
                audio_data_np = audio_data_np_mono[:, np.newaxis]
            model_used = "ASMR_Placeholder"

        else:
            self.logger.error(f"Unknown soundscape type: {scape_type}")
            return None

        if audio_data_np is None:
            self.logger.error(f"Audio data not generated for soundscape type: {scape_type}")
            return None

        # Save generated audio to a temporary WAV file
        temp_audio_dir = "temp_audio_files"
        os.makedirs(temp_audio_dir, exist_ok=True)
        temp_wav_path = os.path.join(temp_audio_dir, f"temp_soundscape_{uuid.uuid4().hex[:8]}.wav")
        temp_files_to_clean.append(temp_wav_path)

        try:
            sf.write(temp_wav_path, audio_data_np, sample_rate)
            self.logger.info(f"Generated soundscape saved to temporary WAV: {temp_wav_path}")
        except Exception as e:
            self.logger.error(f"Failed to write temporary WAV file for soundscape: {e}")
            for f_path in temp_files_to_clean: # Clean up any partial files
                 if os.path.exists(f_path): os.remove(f_path)
            return None

        # Prepare Metadata
        content_id = uuid.uuid4().hex
        output_filename_base = f"{scape_type.lower().replace(' ', '_')}_{content_id[:8]}"
        gcs_path_base_for_saving = os.path.join(self.gcs_generated_audio_prefix, scape_type.lower(), output_filename_base)

        conceptual_final_gcs_path = f"gs://{self.gcs_bucket_name}/{gcs_path_base_for_saving}.{self.default_output_format}"

        metadata = self._prepare_metadata(
            content_id=content_id,
            title=f"{scape_type.replace('_', ' ').title()} Soundscape - {content_id[:8]}",
            gcs_audio_path=conceptual_final_gcs_path,
            duration_seconds=float(target_duration_seconds), # Ensure float
            audio_format=self.default_output_format,
            sample_rate=sample_rate,
            bitrate=self.default_bitrate,
            model_used=model_used,
            genre="soundscape", # Broad genre
            mood_tags=[scape_type.lower().replace('_', ' ')], # Use scape_type as a mood tag
            additional_info={"generation_params": generation_params}
        )

        # Normalize and Save (Stubbed)
        result_paths = self._normalize_and_save_audio(
            audio_file_path=temp_wav_path,
            output_gcs_path_base=gcs_path_base_for_saving,
            metadata=metadata
        )

        # Cleanup
        try:
            for f_path in temp_files_to_clean:
                 if os.path.exists(f_path): os.remove(f_path)
            if os.path.exists(temp_audio_dir) and not os.listdir(temp_audio_dir):
                 os.rmdir(temp_audio_dir)
        except Exception as e:
            self.logger.warning(f"Error during cleanup of temporary files for soundscape: {e}")

        if result_paths:
            self.logger.success(f"Successfully processed soundscape: {result_paths[0]}")
            return result_paths
        else:
            self.logger.error(f"Failed to normalize and save soundscape: {scape_type}")
            return None

    def generate_tts_segment(self, text_to_speak: str, voice_id: str,
                             output_filename_base: str, lang_code: Optional[str] = None,
                             speaking_rate: Optional[float] = None,
                             pitch: Optional[float] = None) -> Optional[Tuple[str, str]]:
        """
        Generates a speech segment using Google Cloud TTS.

        Args:
            text_to_speak: The text to synthesize.
            voice_id: Voice name/ID for Google Cloud TTS (e.g., "en-US-Wavenet-D").
            output_filename_base: Base for naming output files (e.g., "dj_intro_1").
            lang_code: Optional language code (e.g., "en-US").
            speaking_rate: Optional speaking rate (0.25 to 4.0).
            pitch: Optional pitch adjustment (-20.0 to 20.0).

        Returns:
            A tuple (gcs_audio_path, gcs_metadata_path) if successful, else None.
        """
        self.logger.info(f"Request to generate TTS segment: voice_id='{voice_id}', text='{text_to_speak[:50]}...'")

        if not self.tts_client:
            self.logger.error("TTS client not initialized or not available. Cannot generate TTS segment.")
            return None

        if not sf: # soundfile needed for duration calculation if output is WAV
            self.logger.error("soundfile library not available. Cannot process TTS audio duration.")
            return None

        temp_audio_dir = "temp_audio_files"
        os.makedirs(temp_audio_dir, exist_ok=True)

        # We'll request LINEAR16 (WAV) from TTS for easier processing and duration calculation
        # and then convert to target format in _normalize_and_save_audio
        temp_raw_audio_filename = f"temp_tts_{output_filename_base}_{uuid.uuid4().hex[:8]}.wav"
        temp_raw_audio_path = os.path.join(temp_audio_dir, temp_raw_audio_filename)

        tts_kwargs = {}
        if speaking_rate is not None:
            tts_kwargs['speaking_rate'] = speaking_rate
        if pitch is not None:
            tts_kwargs['pitch'] = pitch
        if AudioEncoding: # Check if AudioEncoding was imported
             tts_kwargs['audio_encoding'] = AudioEncoding.LINEAR16 # Request WAV output
        else:
            self.logger.warning("AudioEncoding type not available, TTS client will use its default encoding.")


        self.logger.debug(f"Calling TTS client with: voice='{voice_id}', lang='{lang_code}', output='{temp_raw_audio_path}', kwargs={tts_kwargs}")

        try:
            # synthesize_speech returns (output_filename, word_timings_list)
            # output_filename here is the same as temp_raw_audio_path if successful
            saved_audio_path, subtitle_data = self.tts_client.synthesize_speech(
                text=text_to_speak,
                voice_id=voice_id,
                output_filename=temp_raw_audio_path,
                language_code=lang_code,
                **tts_kwargs
            )
            if not saved_audio_path or not os.path.exists(saved_audio_path):
                self.logger.error(f"TTS synthesis failed or did not produce an output file at {temp_raw_audio_path}.")
                return None
        except Exception as e:
            self.logger.error(f"Exception during TTS synthesis: {e}", exc_info=True)
            return None

        # Get actual duration from the generated WAV file
        try:
            info = sf.info(temp_raw_audio_path)
            actual_duration_seconds = info.duration
        except Exception as e:
            self.logger.error(f"Failed to get duration from generated TTS file '{temp_raw_audio_path}': {e}")
            if os.path.exists(temp_raw_audio_path): os.remove(temp_raw_audio_path)
            return None

        self.logger.info(f"TTS audio generated: {temp_raw_audio_path}, duration: {actual_duration_seconds:.2f}s")

        # Prepare Metadata
        content_id = uuid.uuid4().hex
        # Use a sub-folder "tts" within the generated audio prefix
        gcs_path_base_for_saving = os.path.join(self.gcs_generated_audio_prefix, "tts", output_filename_base)

        target_audio_format = self.app_config.audiogenerator.get('default_output_format', 'mp3')
        conceptual_final_gcs_path = f"gs://{self.gcs_bucket_name}/{gcs_path_base_for_saving}.{target_audio_format}"

        generation_params_meta = {'voice_id': voice_id, 'lang_code': lang_code}
        if speaking_rate is not None: generation_params_meta['speaking_rate'] = speaking_rate
        if pitch is not None: generation_params_meta['pitch'] = pitch
        # Store word timings (subtitle_data) if available
        if subtitle_data: generation_params_meta['word_timings'] = subtitle_data


        metadata = self._prepare_metadata(
            content_id=content_id,
            title=f"TTS: {text_to_speak[:30]}..." if len(text_to_speak) > 30 else f"TTS: {text_to_speak}",
            gcs_audio_path=conceptual_final_gcs_path, # Placeholder, will be updated by _normalize_and_save_audio
            duration_seconds=actual_duration_seconds,
            audio_format=target_audio_format, # Target format after processing
            sample_rate=self.default_sample_rate, # This might differ from TTS output, _normalize_and_save_audio should handle resampling
            bitrate=self.default_bitrate,
            model_used=f"GoogleCloudTTS_{voice_id}",
            genre="speech",
            additional_info={
                "transcript": text_to_speak,
                "generation_params": generation_params_meta
            }
        )

        # Normalize and Save (Stubbed)
        result_paths = self._normalize_and_save_audio(
            audio_file_path=temp_raw_audio_path, # Pass the path to the local WAV file
            output_gcs_path_base=gcs_path_base_for_saving,
            metadata=metadata
        )

        # Cleanup
        try:
            if os.path.exists(temp_raw_audio_path): os.remove(temp_raw_audio_path)
            if os.path.exists(temp_audio_dir) and not os.listdir(temp_audio_dir): # remove dir if empty and it's the one we created
                 if temp_audio_dir == "temp_audio_files": # Basic check
                    os.rmdir(temp_audio_dir)
        except Exception as e:
            self.logger.warning(f"Error during cleanup of temporary TTS file: {e}")

        if result_paths:
            self.logger.success(f"Successfully processed TTS segment: {result_paths[0]}")
            return result_paths
        else:
            self.logger.error(f"Failed to normalize and save TTS segment for text: {text_to_speak[:50]}...")
            return None


if __name__ == '__main__':
    # This basic example won't fully run without a valid app.config.config.Config instance
    # and proper GCS setup for the GCSManager.
    # It's primarily for ensuring the class structure loads.

    # Create a dummy config for basic initialization test
    class DummyConfig:
        def __init__(self):
            self.playlist = {
                'gcs_music_library_bucket': 'test-bucket-name-audio',
                'gcs_credentials_path': None
            }
            self.audiogenerator = {
                'gcs_generated_audio_prefix': 'generated_audio_test/',
                'default_output_format': 'mp3',
                'default_audio_sample_rate': 44100,
                'default_audio_bitrate': '192k'
            }
            self.config_data = { # Replicate how app_config.config_data would look
                "playlist": self.playlist,
                "audiogenerator": self.audiogenerator
            }

    dummy_config = DummyConfig()

    logger.info("Attempting to initialize AudioGenerator with dummy config...")
    try:
        # Test with GCSManager provided (mocked)
        mock_gcs_manager = MagicMock(spec=GCSManager) # from unittest.mock
        mock_gcs_manager.bucket_name = dummy_config.playlist['gcs_music_library_bucket']

        generator_with_mock = AudioGenerator(app_config=dummy_config, gcs_manager=mock_gcs_manager)
        logger.info("AudioGenerator initialized with mocked GCSManager.")

        # Test GCSManager instantiation by AudioGenerator
        # This will try to init GCS client if bucket_name is present, which might fail if no ADC
        # For local testing without real ADC, this part might show warnings or errors from GCSManager
        # generator_internal_gcs = AudioGenerator(app_config=dummy_config)
        # logger.info("AudioGenerator initialized with internally created GCSManager (may show GCS client errors if no ADC).")

        # Test metadata preparation
        test_content_id = uuid.uuid4().hex
        test_title = "Test Generated Track"
        test_gcs_path = f"gs://{dummy_config.playlist['gcs_music_library_bucket']}/{dummy_config.audiogenerator['gcs_generated_audio_prefix']}{test_title.replace(' ', '_')}_{test_content_id}.mp3"

        metadata = generator_with_mock._prepare_metadata(
            content_id=test_content_id,
            title=test_title,
            gcs_audio_path=test_gcs_path,
            duration_seconds=123.45,
            audio_format="mp3",
            sample_rate=44100,
            bitrate="192k",
            model_used="TestModel_V1",
            genre="Electronic",
            mood_tags=["chill", "ambient"]
        )
        logger.info(f"Prepared metadata example: {json.dumps(metadata, indent=2)}")
        assert metadata["gcs_path_metadata"].endswith(".meta.json")

    except ImportError as e:
        logger.error(f"ImportError during test: {e}. Ensure PYTHONPATH is set correctly if running directly.")
    except Exception as e:
        logger.error(f"Error during AudioGenerator initialization test: {e}", exc_info=True)

```
