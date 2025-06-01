import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import tempfile
import json
import os
import shutil # For cleaning up test_temp_configs_audiogen if created
import numpy as np # For asserting array shapes, etc.

# Add project root to sys.path
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from app.audiogenerator.audio_generator import AudioGenerator
from app.services.playlist.gcs_content_manager import GCSManager
from app.services.tts.google_cloud_tts import GoogleCloudTTS
from app.config.config import Config as AppConfigModule # Import the module
from app.services.streaming_interface import StreamConfig # Though not directly used, good for context

# Mock Magenta/TF imports at the module level for tests if they are problematic during test discovery
# This prevents actual TF loading during test collection, which can be slow or fail in CI
mock_magenta_available = True
mock_tf_available = True

# It's often better to patch these within the test methods or setUp if they are specific
# to certain tests, but for a broad disable during testing:
# sys.modules['magenta.models.music_vae'] = MagicMock()
# sys.modules['magenta.models.melody_rnn'] = MagicMock()
# sys.modules['magenta.models.shared'] = MagicMock()
# sys.modules['magenta.music'] = MagicMock()
# sys.modules['magenta.protobuf'] = MagicMock()
# sys.modules['tensorflow.compat.v1'] = MagicMock()


class TestAudioGenerator(unittest.TestCase):

    def _create_temp_config_file(self, config_data: dict) -> str:
        """Helper to create a temporary JSON config file (not used by AudioGenerator directly, but useful for testing config loading if it were JSON). AudioGenerator uses the TOML config module."""
        # This helper is less relevant now as AudioGenerator takes a Config object (module)
        # However, if we were testing a JSON config loader, it would be useful.
        # For now, we mock the app_config object directly.
        pass

    def _get_mock_app_config(self, audiogen_custom_config=None, playlist_custom_config=None, google_tts_custom_config=None):
        """Creates a mock app_config object with default and overridable sections."""
        mock_config = MagicMock(spec=AppConfigModule) # Use the imported module as spec

        # Default playlist config
        mock_config.playlist = {
            'gcs_music_library_bucket': 'test-music-bucket',
            'gcs_credentials_path': None,
            # Add other playlist defaults if AudioGenerator starts using them
        }
        if playlist_custom_config:
            mock_config.playlist.update(playlist_custom_config)

        # Default audiogenerator config
        mock_config.audiogenerator = {
            'gcs_generated_audio_prefix': 'generated_audio_test/',
            'magenta_checkpoint_musicvae': None, #'/path/to/music_vae_checkpoint',
            'magenta_checkpoint_melodyrnn': None, #'/path/to/melody_rnn_bundle.mag',
            'default_output_format': 'mp3',
            'default_audio_sample_rate': 44100,
            'default_audio_bitrate': '192k',
            'normalization_target_peak_dbfs': -1.0,
            'default_magenta_target_duration_seconds': 180,
            'default_magenta_temperature': 1.0,
            'default_soundscape_duration_seconds': 300, # Shorter for tests
            'default_binaural_base_freq': 100.0,
            'default_binaural_beat_freq': 10.0,
            'default_mixed_soundscape_base_layers': [],
            'default_asmr_track_gcs_path': None,
            'default_tts_voice_id': "en-US-News-K", # A standard, non-wavenet voice
            'default_tts_lang_code': "en-US",
            'default_tts_speaking_rate': 1.0,
            'default_tts_pitch': 0.0,
        }
        if audiogen_custom_config:
            mock_config.audiogenerator.update(audiogen_custom_config)

        # Default google_tts config (used by GoogleCloudTTS instance)
        mock_config.google_tts = {
            'service_account_key_path': None,
            'default_language_code': 'en-US',
            'default_voice_name': 'en-US-Standard-C', # Matches audiogen default
            'default_audio_encoding': 'MP3' # GoogleCloudTTS default, LINEAR16 is requested by AudioGenerator
        }
        if google_tts_custom_config:
            mock_config.google_tts.update(google_tts_custom_config)

        return mock_config

    @patch('app.audiogenerator.audio_generator.logger', MagicMock()) # Mock logger for all tests
    def setUp(self):
        self.mock_gcs_manager_class = patch('app.audiogenerator.audio_generator.GCSManager').start()
        self.mock_gcs_manager_instance = self.mock_gcs_manager_class.return_value
        # Mock GCS client on the instance for download_to_filename calls
        self.mock_gcs_storage_client = MagicMock()
        self.mock_gcs_manager_instance.storage_client = self.mock_gcs_storage_client

        # Mock GoogleCloudTTS more thoroughly
        self.mock_google_cloud_tts_class = patch('app.audiogenerator.audio_generator.GoogleCloudTTS').start()
        self.mock_tts_client_instance = self.mock_google_cloud_tts_class.return_value
        self.mock_tts_client_instance.synthesize_speech.return_value = ('mock_tts_output.wav', []) # path, subtitles

        # Mock Magenta models and related functions
        # These are patched where AudioGenerator tries to import them or use them.
        # The global mock_magenta_available etc. flags can also be used by AudioGenerator.
        # For direct patching:
        self.patch_music_vae = patch('app.audiogenerator.audio_generator.MusicVAE', MagicMock())
        self.patch_melody_rnn = patch('app.audiogenerator.audio_generator.MelodyRnnSequenceGenerator', MagicMock())
        self.patch_bundle_utils = patch('app.audiogenerator.audio_generator.sequence_generator_bundle', MagicMock())
        self.patch_note_sequence_utils = patch('app.audiogenerator.audio_generator.note_sequence_to_pretty_midi', MagicMock(return_value=MagicMock()))
        self.patch_midi_file_to_ns = patch('app.audiogenerator.audio_generator.midi_file_to_note_sequence', MagicMock())

        self.mock_music_vae_class = self.patch_music_vae.start()
        self.mock_melody_rnn_class = self.patch_melody_rnn.start()
        self.mock_bundle_utils = self.patch_bundle_utils.start()
        self.mock_note_sequence_to_pm = self.patch_note_sequence_utils.start()
        self.mock_midi_file_to_ns_func = self.patch_midi_file_to_ns.start()

        # Mock pretty_midi
        self.mock_pretty_midi_class = patch('app.audiogenerator.audio_generator.pretty_midi.PrettyMIDI', MagicMock()).start()
        self.mock_pretty_midi_instance = self.mock_pretty_midi_class.return_value
        self.mock_pretty_midi_instance.synthesize.return_value = np.random.randn(44100 * 2) # 2s audio
        self.mock_pretty_midi_instance.instruments = [MagicMock(notes=[1])] # Ensure it's not empty

        # Mock soundfile
        self.mock_sf_write = patch('app.audiogenerator.audio_generator.sf.write', MagicMock()).start()
        self.mock_sf_info = patch('app.audiogenerator.audio_generator.sf.info', MagicMock(return_value=MagicMock(duration=5.0, samplerate=44100, channels=2))).start()

        # Mock pydub
        self.mock_audio_segment_class = patch('app.audiogenerator.audio_generator.AudioSegment').start()
        self.mock_audio_segment_instance = self.mock_audio_segment_class.from_file.return_value
        self.mock_audio_segment_instance.max_dBFS = -6.0
        self.mock_audio_segment_instance.duration_seconds = 5.0
        self.mock_audio_segment_instance.frame_rate = 44100
        self.mock_audio_segment_instance.channels = 2
        self.mock_audio_segment_instance.frame_width = 2 # 16-bit
        # Make pydub methods return self for chaining where appropriate
        self.mock_audio_segment_instance.apply_gain.return_value = self.mock_audio_segment_instance
        self.mock_audio_segment_instance.set_frame_rate.return_value = self.mock_audio_segment_instance
        self.mock_audio_segment_instance.set_channels.return_value = self.mock_audio_segment_instance
        self.mock_audio_segment_instance.export.return_value = None # or mock a file object if needed
        self.mock_audio_segment_instance.get_array_of_samples.return_value = np.zeros(100, dtype=np.int16)


        # Mock os and file operations
        self.mock_os_path_exists = patch('os.path.exists', MagicMock(return_value=True)).start()
        self.mock_os_remove = patch('os.remove', MagicMock()).start()
        self.mock_os_makedirs = patch('os.makedirs', MagicMock()).start()
        self.mock_os_listdir = patch('os.listdir', MagicMock(return_value=[])).start() # For empty dir check
        self.mock_os_rmdir = patch('os.rmdir', MagicMock()).start()

        # Using tempfile for unique names, but mock NamedTemporaryFile if specific control is needed
        # For now, assume NamedTemporaryFile works as intended in tests.

        self.addCleanup(patch.stopall)

        # Default app_config for most tests
        self.app_config = self._get_mock_app_config()

        # Create a dummy temp file for tests that need a file path
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        self.temp_file.close()
        self.addCleanup(lambda: os.remove(self.temp_file.name) if os.path.exists(self.temp_file.name) else None)
        self.mock_sf_write.return_value = None # sf.write has no return


    def test_initialization_with_gcs_manager(self):
        """Test AudioGenerator initializes with a provided GCSManager."""
        mock_gcs = MagicMock(spec=GCSManager)
        generator = AudioGenerator(app_config=self.app_config, gcs_manager=mock_gcs)
        self.assertIsNotNone(generator.gcs_manager)
        self.assertEqual(generator.gcs_manager, mock_gcs)
        self.assertTrue(generator.logger is not None) # from global patch
        self.mock_google_cloud_tts_class.assert_called_once() # TTS client init attempted

    def test_initialization_creates_gcs_manager(self):
        """Test AudioGenerator creates GCSManager if not provided."""
        generator = AudioGenerator(app_config=self.app_config, gcs_manager=None)
        self.mock_gcs_manager_class.assert_called_once_with(
            bucket_name=self.app_config.playlist['gcs_music_library_bucket'],
            credentials_path=self.app_config.playlist['gcs_credentials_path'],
            logger_instance=generator.logger
        )
        self.assertTrue(generator.logger is not None)

    def test_initialization_loads_config_values(self):
        """Test that relevant config values are read during init."""
        audiogen_cfg = {
            'gcs_generated_audio_prefix': 'custom_prefix/',
            'default_output_format': 'wav',
            'default_audio_sample_rate': 22050,
            'default_audio_bitrate': '128k',
            'magenta_checkpoint_musicvae': '/custom/vae',
            'magenta_checkpoint_melodyrnn': '/custom/rnn',
        }
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)
        generator = AudioGenerator(app_config=app_cfg)

        self.assertEqual(generator.gcs_generated_audio_prefix, 'custom_prefix/')
        self.assertEqual(generator.default_output_format, 'wav')
        self.assertEqual(generator.default_sample_rate, 22050)
        self.assertEqual(generator.default_bitrate, '128k')
        self.assertEqual(generator.magenta_checkpoint_musicvae, '/custom/vae')
        self.assertEqual(generator.magenta_checkpoint_melodyrnn, '/custom/rnn')


    @patch.object(AudioGenerator, '_load_magenta_models') # Mock the method itself
    def test_init_calls_load_magenta_models(self, mock_load_models):
        """Test that __init__ calls _load_magenta_models."""
        AudioGenerator(app_config=self.app_config)
        mock_load_models.assert_called_once()

    # --- Test _load_magenta_models ---
    def test_load_magenta_models_success(self):
        audiogen_cfg = {
            'magenta_checkpoint_musicvae': '/fake/vae_checkpoint',
            'magenta_checkpoint_melodyrnn': '/fake/rnn_bundle.mag'
        }
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)

        # Mock the actual loading functions from Magenta
        # MusicVAE.load_checkpoint
        mock_vae_loader = self.mock_music_vae_class.load_checkpoint
        mock_vae_instance = MagicMock(name="MusicVAEInstance")
        mock_vae_loader.return_value = mock_vae_instance

        # sequence_generator_bundle.read_bundle_file
        mock_bundle_reader = self.mock_bundle_utils.read_bundle_file
        mock_bundle_object = MagicMock(name="BundleObject")
        mock_bundle_object.generator_description.id = 'basic_rnn' # Example ID
        mock_bundle_reader.return_value = mock_bundle_object

        # MelodyRnnSequenceGenerator.get_generator_map
        mock_rnn_generator_map = self.mock_melody_rnn_class.get_generator_map
        mock_rnn_generator_constructor = MagicMock(name="MelodyRNNConstructor")
        mock_rnn_instance = MagicMock(name="MelodyRNNInstance")
        mock_rnn_generator_constructor.return_value = mock_rnn_instance
        mock_rnn_generator_map.return_value = {'basic_rnn': mock_rnn_generator_constructor}

        generator = AudioGenerator(app_config=app_cfg) # _load_magenta_models is called in __init__

        mock_vae_loader.assert_called_once_with('/fake/vae_checkpoint')
        self.assertEqual(generator.music_vae_model, mock_vae_instance)

        mock_bundle_reader.assert_called_once_with('/fake/rnn_bundle.mag')
        mock_rnn_generator_map.assert_called_once()
        mock_rnn_generator_constructor.assert_called_once_with(checkpoint=None, bundle=mock_bundle_object)
        mock_rnn_instance.initialize.assert_called_once()
        self.assertEqual(generator.melody_rnn_model, mock_rnn_instance)

    def test_load_magenta_models_no_paths_configured(self):
        app_cfg = self._get_mock_app_config(audiogen_custom_config={
            'magenta_checkpoint_musicvae': None,
            'magenta_checkpoint_melodyrnn': None
        })
        generator = AudioGenerator(app_config=app_cfg)
        self.assertIsNone(generator.music_vae_model)
        self.assertIsNone(generator.melody_rnn_model)
        self.mock_music_vae_class.load_checkpoint.assert_not_called()
        self.mock_bundle_utils.read_bundle_file.assert_not_called()

    @patch('app.audiogenerator.audio_generator.MusicVAE.load_checkpoint')
    def test_load_magenta_models_vae_load_fails(self, mock_vae_loader_direct):
        mock_vae_loader_direct.side_effect = Exception("VAE Load Failed")
        audiogen_cfg = {'magenta_checkpoint_musicvae': '/fake/vae_checkpoint'}
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)

        generator = AudioGenerator(app_config=app_cfg)
        self.assertIsNone(generator.music_vae_model)

    @patch('app.audiogenerator.audio_generator.sequence_generator_bundle.read_bundle_file')
    def test_load_magenta_models_rnn_load_fails(self, mock_bundle_reader_direct):
        mock_bundle_reader_direct.side_effect = Exception("RNN Load Failed")
        audiogen_cfg = {'magenta_checkpoint_melodyrnn': '/fake/rnn_bundle.mag'}
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)

        generator = AudioGenerator(app_config=app_cfg)
        self.assertIsNone(generator.melody_rnn_model)

    # --- Test generate_magenta_track ---
    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_magenta_track_musicvae_success(self, mock_normalize_save):
        # Setup config to load MusicVAE
        audiogen_cfg = {'magenta_checkpoint_musicvae': '/fake/vae_checkpoint'}
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)

        generator = AudioGenerator(app_config=app_cfg) # This will call the mocked _load_magenta_models

        # Ensure a mock MusicVAE model is set up by _load_magenta_models (or set it directly for isolated test)
        mock_vae_model_instance = MagicMock(name="ActualMusicVAEInstance")
        mock_generated_ns = MagicMock(name="NoteSequenceProto")
        mock_generated_ns.notes = [MagicMock()] # Ensure it has notes
        mock_generated_ns.total_time = 10.0
        mock_vae_model_instance.sample.return_value = [mock_generated_ns]
        generator.music_vae_model = mock_vae_model_instance # Directly assign the mock model that was "loaded"

        # Mock the conversion from NoteSequence to PrettyMIDI
        mock_pm = MagicMock(name="PrettyMIDIInstance")
        mock_pm.instruments = [MagicMock(notes=[1])] # Ensure it's not empty
        self.mock_note_sequence_to_pm.return_value = mock_pm

        mock_normalize_save.return_value = ("gs://bucket/fake_audio.mp3", "gs://bucket/fake_audio.meta.json")

        result = generator.generate_magenta_track(genre="lofi", target_duration_seconds=20)

        self.assertIsNotNone(result)
        mock_vae_model_instance.sample.assert_called_once()
        self.mock_note_sequence_to_pm.assert_called_once_with(mock_generated_ns)
        self.mock_pretty_midi_instance.synthesize.assert_called_once()
        self.mock_sf_write.assert_called_once() # Called for the temp WAV
        mock_normalize_save.assert_called_once()
        # Further assertions can be made on the metadata passed to mock_normalize_save

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_magenta_track_melodyrnn_success(self, mock_normalize_save):
        audiogen_cfg = {'magenta_checkpoint_melodyrnn': '/fake/rnn_bundle.mag'}
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)
        generator = AudioGenerator(app_config=app_cfg)

        mock_rnn_model_instance = MagicMock(name="ActualMelodyRNNInstance")
        mock_generated_ns = MagicMock(name="NoteSequenceProto")
        mock_generated_ns.notes = [MagicMock()]
        mock_generated_ns.total_time = 12.0
        mock_rnn_model_instance.generate.return_value = mock_generated_ns
        generator.melody_rnn_model = mock_rnn_model_instance

        mock_pm = MagicMock(name="PrettyMIDIInstance")
        mock_pm.instruments = [MagicMock(notes=[1])]
        self.mock_note_sequence_to_pm.return_value = mock_pm

        mock_normalize_save.return_value = ("gs://bucket/fake_audio_rnn.mp3", "gs://bucket/fake_audio_rnn.meta.json")

        result = generator.generate_magenta_track(genre="edm", target_duration_seconds=25)

        self.assertIsNotNone(result)
        mock_rnn_model_instance.generate.assert_called_once()
        self.mock_note_sequence_to_pm.assert_called_once_with(mock_generated_ns)
        mock_normalize_save.assert_called_once()

    def test_generate_magenta_track_no_model_loaded(self):
        # Ensure models are None (default if no paths in config)
        app_cfg = self._get_mock_app_config(audiogen_custom_config={
            'magenta_checkpoint_musicvae': None, 'magenta_checkpoint_melodyrnn': None
        })
        generator = AudioGenerator(app_config=app_cfg)
        generator.music_vae_model = None # Explicitly ensure
        generator.melody_rnn_model = None

        result = generator.generate_magenta_track(genre="lofi")
        self.assertIsNone(result)

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_magenta_track_model_fails_to_generate_notes(self, mock_normalize_save):
        app_cfg = self._get_mock_app_config(audiogen_custom_config={'magenta_checkpoint_musicvae': '/fake/vae'})
        generator = AudioGenerator(app_config=app_cfg)

        mock_vae_model_instance = MagicMock(name="ActualMusicVAEInstance")
        mock_generated_ns_empty = MagicMock(name="EmptyNoteSequenceProto")
        mock_generated_ns_empty.notes = [] # No notes
        mock_generated_ns_empty.total_time = 0.0
        mock_vae_model_instance.sample.return_value = [mock_generated_ns_empty]
        generator.music_vae_model = mock_vae_model_instance

        result = generator.generate_magenta_track(genre="lofi")
        self.assertIsNone(result)
        mock_normalize_save.assert_not_called()

    # --- Test generate_soundscape ---
    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_soundscape_brown_noise(self, mock_normalize_save):
        generator = AudioGenerator(app_config=self.app_config)
        mock_normalize_save.return_value = ("gs://bucket/brown.mp3", "gs://bucket/brown.meta.json")

        result = generator.generate_soundscape(scape_type="brown_noise", target_duration_seconds=10)

        self.assertIsNotNone(result)
        self.mock_sf_write.assert_called_once() # Asserts that some audio data was written
        args, _ = self.mock_sf_write.call_args
        written_data = args[1] # data is the second argument to sf.write
        self.assertEqual(written_data.shape, (44100 * 10, 2)) # (samples, channels)
        mock_normalize_save.assert_called_once()
        # Check metadata passed to _normalize_and_save_audio
        _, kwargs = mock_normalize_save.call_args
        metadata = kwargs['metadata']
        self.assertEqual(metadata['model_used'], "BrownNoiseGenerator")
        self.assertEqual(metadata['genre'], "soundscape")

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_soundscape_binaural_beats(self, mock_normalize_save):
        generator = AudioGenerator(app_config=self.app_config)
        mock_normalize_save.return_value = ("gs://bucket/binaural.mp3", "gs://bucket/binaural.meta.json")

        result = generator.generate_soundscape(
            scape_type="binaural_beats",
            target_duration_seconds=10,
            base_frequency=100.0,
            beat_frequency=10.0
        )
        self.assertIsNotNone(result)
        self.mock_sf_write.assert_called_once()
        args, _ = self.mock_sf_write.call_args
        written_data = args[1]
        self.assertEqual(written_data.shape, (44100 * 10, 2))
        mock_normalize_save.assert_called_once()
        _, kwargs = mock_normalize_save.call_args
        metadata = kwargs['metadata']
        self.assertEqual(metadata['model_used'], "BinauralBeatGenerator")
        self.assertEqual(metadata['additional_info']['generation_params']['base_frequency_hz'], 100.0)

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    @patch('tempfile.NamedTemporaryFile')
    def test_generate_soundscape_mixed_success(self, mock_tempfile_constructor, mock_normalize_save):
        # Mock NamedTemporaryFile to control its name and avoid actual file creation by it
        mock_temp_file_instance = MagicMock()
        mock_temp_file_instance.name = "temp_downloaded_layer.mp3"
        mock_tempfile_constructor.return_value = mock_temp_file_instance

        audiogen_cfg = {
            'default_mixed_soundscape_base_layers': [
                f"gs://{self.app_config.playlist['gcs_music_library_bucket']}/sounds/rain.mp3",
                f"gs://{self.app_config.playlist['gcs_music_library_bucket']}/sounds/wind.mp3"
            ]
        }
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)
        generator = AudioGenerator(app_config=app_cfg)

        # Mock GCS download
        self.mock_gcs_storage_client.bucket.return_value.blob.return_value.download_to_filename.return_value = None

        # Mock pydub AudioSegment loading and processing
        mock_segment = MagicMock(spec=self.mock_audio_segment_class) # Use the class from setUp for spec
        mock_segment.set_channels.return_value = mock_segment
        mock_segment.set_frame_rate.return_value = mock_segment
        mock_segment.__len__.return_value = 300 * 1000 # 300s
        mock_segment.__getitem__.return_value = mock_segment # For slicing
        mock_segment.__mul__.return_value = mock_segment # For looping
        mock_segment.overlay.return_value = mock_segment
        mock_segment.get_array_of_samples.return_value = np.zeros(100, dtype=np.int16)
        mock_segment.channels = 2
        mock_segment.sample_width = 2 # 16-bit
        self.mock_audio_segment_class.from_file.return_value = mock_segment

        mock_normalize_save.return_value = ("gs://bucket/mixed.mp3", "gs://bucket/mixed.meta.json")

        result = generator.generate_soundscape(scape_type="mixed_soundscape", target_duration_seconds=10)

        self.assertIsNotNone(result)
        self.assertEqual(self.mock_gcs_storage_client.bucket.return_value.blob.return_value.download_to_filename.call_count, 2)
        self.assertEqual(self.mock_audio_segment_class.from_file.call_count, 2)
        mock_normalize_save.assert_called_once()
        _, kwargs = mock_normalize_save.call_args
        metadata = kwargs['metadata']
        self.assertEqual(metadata['model_used'], "SoundscapeMixer_Active")

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_soundscape_asmr_preconfigured_success(self, mock_normalize_save):
        asmr_path = f"gs://{self.app_config.playlist['gcs_music_library_bucket']}/asmr/track.mp3"
        audiogen_cfg = {'default_asmr_track_gcs_path': asmr_path}
        app_cfg = self._get_mock_app_config(audiogen_custom_config=audiogen_cfg)
        generator = AudioGenerator(app_config=app_cfg)

        self.mock_gcs_storage_client.bucket.return_value.blob.return_value.download_to_filename.return_value = None
        # Mock AudioSegment.from_file for duration calculation if ASMR track is downloaded
        mock_asmr_segment = MagicMock(duration_seconds=300.0) # Mock the pydub segment
        self.mock_audio_segment_class.from_file.return_value = mock_asmr_segment


        mock_normalize_save.return_value = ("gs://bucket/asmr.mp3", "gs://bucket/asmr.meta.json")

        result = generator.generate_soundscape(scape_type="asmr", target_duration_seconds=10) # Duration might be overridden by file

        self.assertIsNotNone(result)
        self.mock_gcs_storage_client.bucket.return_value.blob.return_value.download_to_filename.assert_called_once()
        # _normalize_and_save_audio is called with the path of the downloaded file
        mock_normalize_save.assert_called_once()
        saved_metadata = mock_normalize_save.call_args[0][2] # metadata is the 3rd arg
        self.assertEqual(saved_metadata['model_used'], "ASMR_PreconfiguredTrack")
        self.assertEqual(saved_metadata['duration_seconds'], 300.0) # Duration from mocked segment

    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_soundscape_asmr_fallback_to_noise(self, mock_normalize_save):
        app_cfg = self._get_mock_app_config(audiogen_custom_config={'default_asmr_track_gcs_path': None})
        generator = AudioGenerator(app_config=app_cfg)
        mock_normalize_save.return_value = ("gs://bucket/asmr_noise.mp3", "gs://bucket/asmr_noise.meta.json")

        result = generator.generate_soundscape(scape_type="asmr", target_duration_seconds=10)

        self.assertIsNotNone(result)
        self.mock_gcs_storage_client.bucket.return_value.blob.return_value.download_to_filename.assert_not_called()
        self.mock_sf_write.assert_called_once() # Should write brown noise
        mock_normalize_save.assert_called_once()
        _, kwargs = mock_normalize_save.call_args
        metadata = kwargs['metadata']
        self.assertEqual(metadata['model_used'], "ASMR_Placeholder_GentleNoise")

    # --- Test generate_tts_segment ---
    @patch.object(AudioGenerator, '_normalize_and_save_audio')
    def test_generate_tts_segment_success(self, mock_normalize_save):
        app_cfg = self._get_mock_app_config() # Use default config
        generator = AudioGenerator(app_config=app_cfg)

        # Ensure tts_client is mocked and available on the generator instance
        # (it's set up in self.setUp, but if a test needs a specific state, re-mock or ensure here)
        if generator.tts_client is None: # Should be mocked by setUp
            generator.tts_client = self.mock_tts_client_instance

        self.mock_tts_client_instance.synthesize_speech.return_value = (self.temp_file.name, [{"word": "hello", "start_time": 0.1, "end_time": 0.5}])
        self.mock_sf_info.return_value = MagicMock(duration=1.23, samplerate=24000, channels=1) # Google TTS often outputs 24kHz mono
        mock_normalize_save.return_value = ("gs://bucket/tts_output.mp3", "gs://bucket/tts_output.meta.json")

        text = "Hello world, this is a test."
        voice_id = "en-US-News-K" # Matches default in mock_config if not overridden
        output_base = "test_tts"

        result = generator.generate_tts_segment(
            text_to_speak=text,
            voice_id=voice_id,
            output_filename_base=output_base
        )

        self.assertIsNotNone(result)
        self.mock_tts_client_instance.synthesize_speech.assert_called_once()
        # Check specific args of synthesize_speech if needed, e.g., output_filename, text, voice_id
        call_args = self.mock_tts_client_instance.synthesize_speech.call_args
        self.assertEqual(call_args.kwargs['text'], text)
        self.assertEqual(call_args.kwargs['voice_id'], voice_id)
        # self.assertTrue(call_args.kwargs['output_filename'].startswith("temp_tts_test_tts_")) # temp name is complex

        self.mock_sf_info.assert_called_once_with(self.temp_file.name) # or the path passed to synthesize_speech

        mock_normalize_save.assert_called_once()
        _, kwargs = mock_normalize_save.call_args
        metadata = kwargs['metadata']
        self.assertEqual(metadata['model_used'], f"GoogleCloudTTS_{voice_id}")
        self.assertIn("transcript", metadata["additional_info"])
        self.assertEqual(metadata["additional_info"]["transcript"], text)
        self.assertIn("word_timings", metadata["additional_info"]["generation_params"])

    def test_generate_tts_segment_client_unavailable(self):
        app_cfg = self._get_mock_app_config()
        generator = AudioGenerator(app_config=app_cfg)
        generator.tts_client = None # Force TTS client to be unavailable

        result = generator.generate_tts_segment("test", "voice", "base")
        self.assertIsNone(result)

    # --- Test _normalize_and_save_audio ---
    def test_normalize_and_save_audio_success_wav_to_mp3(self):
        generator = AudioGenerator(app_config=self.app_config)

        # Configure GCSManager mocks for successful uploads
        self.mock_gcs_manager_instance.upload_file.return_value = True
        self.mock_gcs_manager_instance.upload_string_as_blob.return_value = True

        # Prepare metadata (some fields will be updated by the method)
        initial_metadata = {
            "content_id": "test_content_123",
            "title": "Test Track",
            "audio_properties": {"format": "mp3"}, # Target format
            "gcs_path_metadata": f"gs://{self.app_config.playlist['gcs_music_library_bucket']}/generated_audio_test/test_track.meta.json"
            # gcs_path_audio will be set by the method
        }

        # Call the method
        gcs_base = "generated_audio_test/test_track"
        result_audio_path, result_metadata_path = generator._normalize_and_save_audio(
            local_audio_file_path=self.temp_file.name, # Mocked to be WAV-like by pydub mocks
            output_gcs_path_base=gcs_base,
            metadata=initial_metadata.copy() # Pass a copy
        )

        self.assertIsNotNone(result_audio_path)
        self.assertIsNotNone(result_metadata_path)
        self.assertTrue(result_audio_path.endswith(".mp3"))
        self.assertTrue(result_metadata_path.endswith(".meta.json"))

        # Verify pydub calls
        self.mock_audio_segment_class.from_file.assert_called_once_with(self.temp_file.name)
        self.mock_audio_segment_instance.apply_gain.assert_called_once()
        self.mock_audio_segment_instance.export.assert_called_once()
        export_args, export_kwargs = self.mock_audio_segment_instance.export.call_args
        self.assertTrue(export_args[0].endswith("_norm.mp3")) # Temp converted path
        self.assertEqual(export_kwargs['format'], "mp3")
        self.assertEqual(export_kwargs['bitrate'], self.app_config.audiogenerator['default_audio_bitrate'])

        # Verify GCS calls
        self.mock_gcs_manager_instance.upload_file.assert_called_once()
        # Example: check destination_blob_name for audio
        self.assertEqual(self.mock_gcs_manager_instance.upload_file.call_args[1]['destination_blob_name'], gcs_base + ".mp3")

        self.mock_gcs_manager_instance.upload_string_as_blob.assert_called_once()
        # Example: check destination_blob_name for metadata
        self.assertEqual(self.mock_gcs_manager_instance.upload_string_as_blob.call_args[1]['destination_blob_name'], gcs_base + ".meta.json")

        # Verify metadata was updated (example checks)
        final_metadata_str = self.mock_gcs_manager_instance.upload_string_as_blob.call_args[1]['data_string']
        final_metadata = json.loads(final_metadata_str)
        self.assertIn('normalization_details', final_metadata)
        self.assertEqual(final_metadata['audio_properties']['format'], 'mp3')
        self.assertTrue(final_metadata['gcs_path_audio'].endswith('.mp3'))

        # Verify cleanup of temporary files
        # self.temp_file.name is the original local_audio_file_path
        # export_args[0] is the temp_converted_audio_path
        expected_removals = {self.temp_file.name, export_args[0]}
        actual_removals = {call_arg[0][0] for call_arg in self.mock_os_remove.call_args_list}
        self.assertTrue(expected_removals.issubset(actual_removals))


    def test_normalize_and_save_audio_pydub_unavailable_fallback(self):
        # Simulate pydub not being available
        with patch('app.audiogenerator.audio_generator.AudioSegment', None), \
             patch('app.audiogenerator.audio_generator.CouldntDecodeError', None):

            generator = AudioGenerator(app_config=self.app_config)
            self.mock_gcs_manager_instance.upload_file.return_value = True
            self.mock_gcs_manager_instance.upload_string_as_blob.return_value = True

            initial_metadata = {"audio_properties": {}} # minimal
            gcs_base = "generated_audio_test/fallback_track"

            # Create a dummy file with a specific extension for the fallback test
            dummy_fallback_input_path = "dummy_original.wav"
            with open(dummy_fallback_input_path, "w") as f: f.write("dummydata")
            self.addCleanup(lambda: os.remove(dummy_fallback_input_path) if os.path.exists(dummy_fallback_input_path) else None)

            result_audio_path, result_metadata_path = generator._normalize_and_save_audio(
                local_audio_file_path=dummy_fallback_input_path,
                output_gcs_path_base=gcs_base,
                metadata=initial_metadata.copy()
            )
            self.assertIsNotNone(result_audio_path)
            self.assertTrue(result_audio_path.endswith(".wav")) # Should use original extension
            self.mock_gcs_manager_instance.upload_file.assert_called_once_with(dummy_fallback_input_path, gcs_base + ".wav")


    def test_normalize_and_save_audio_upload_audio_fails(self):
        generator = AudioGenerator(app_config=self.app_config)
        self.mock_gcs_manager_instance.upload_file.return_value = False # Simulate GCS audio upload failure

        result = generator._normalize_and_save_audio(self.temp_file.name, "base", {})
        self.assertIsNone(result)
        self.mock_gcs_manager_instance.upload_string_as_blob.assert_not_called() # Metadata upload should not be attempted
        # Assert cleanup of temp_converted_audio_path happened
        self.assertTrue(any(call_arg[0][0].endswith("_norm.mp3") for call_arg in self.mock_os_remove.call_args_list))


    def test_normalize_and_save_audio_upload_metadata_fails(self):
        generator = AudioGenerator(app_config=self.app_config)
        self.mock_gcs_manager_instance.upload_file.return_value = True
        self.mock_gcs_manager_instance.upload_string_as_blob.return_value = False # Simulate GCS metadata upload failure

        result = generator._normalize_and_save_audio(self.temp_file.name, "base", {"audio_properties": {}})
        self.assertIsNone(result)
        # Consider if audio should be deleted if metadata fails - current code does not, logs an error.
        # This test confirms metadata upload was attempted.
        self.mock_gcs_manager_instance.upload_string_as_blob.assert_called_once()


if __name__ == "__main__":
    unittest.main()

```
