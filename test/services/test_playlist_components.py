import unittest
from unittest.mock import patch, MagicMock, PropertyMock, call
import os
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from loguru import logger

# Disable logger for tests
logger.remove()
logger.add(sys.stderr, level="CRITICAL") # Show only critical errors from tested code

# Objects to be tested
from app.services.playlist.models import PlaylistItem, Playlist, PlaylistStatus
from app.services.playlist.gcs_content_manager import GCSContentManager, METADATA_SUFFIX, SUPPORTED_AUDIO_EXTENSIONS as DEFAULT_AUDIO_EXTENSIONS
from app.services.playlist.playlist_generator import PlaylistGenerator
from app.services.playlist.scheduler import PlaylistScheduler
from app.services.playlist.playlist_manager_service import PlaylistManagerService


# Mock google.cloud.storage before it's imported by GCSContentManager
mock_storage_client_instance = MagicMock()
mock_bucket_instance = MagicMock()
mock_blob_instance = MagicMock()

google_cloud_storage_mock = MagicMock()
google_cloud_storage_mock.Client.return_value = mock_storage_client_instance
google_cloud_storage_mock.Client.from_service_account_json.return_value = mock_storage_client_instance
mock_storage_client_instance.bucket.return_value = mock_bucket_instance
mock_bucket_instance.blob.return_value = mock_blob_instance

# Mock google.auth.exceptions for GCSContentManager
google_auth_exceptions_mock = MagicMock()
google_auth_exceptions_mock.DefaultCredentialsError = type('DefaultCredentialsError', (Exception,), {})


# Apply mocks using a dictionary for patching
patch_dict = {
    'google.cloud.storage': google_cloud_storage_mock,
    'google.auth.exceptions': google_auth_exceptions_mock,
}

# Mock app.config.config for all tests that need it
# This mock will be started and stopped in test class setUp and tearDown
mock_app_config = MagicMock()
mock_app_config.playlist = {
    "gcs_music_library_bucket": "test-bucket",
    "gcs_credentials_path": None,
    "default_playlist_target_item_count": 5,
    "default_playlist_name_prefix": "TestAuto",
    "default_transition_type": "crossfade",
    "default_transition_duration_ms": 2000,
    "supported_audio_extensions": [".mp3", ".wav"],
}
mock_app_config.streaming = { # For FFmpegManager path
    "ffmpeg_path": "ffmpeg"
}


@patch.dict('sys.modules', patch_dict)
class TestGCSContentManager(unittest.TestCase):
    def setUp(self):
        # Reset mocks for each test
        mock_storage_client_instance.reset_mock()
        mock_bucket_instance.reset_mock()
        mock_blob_instance.reset_mock()

        # Apply the app_config mock specifically where it's imported
        self.gcs_content_manager_config_patch = patch('app.services.playlist.gcs_content_manager.app_config', mock_app_config)
        self.mocked_gcs_app_config = self.gcs_content_manager_config_patch.start()

        self.bucket_name = "test-bucket"
        self.manager = GCSContentManager(bucket_name=self.bucket_name, credentials_path=None)
        self.manager.storage_client = mock_storage_client_instance # Ensure it uses the mocked client

    def tearDown(self):
        self.gcs_content_manager_config_patch.stop()
        patch.stopall()


    def test_initialize_client_adc(self):
        with patch.dict('sys.modules', patch_dict): # Ensure mocks are active during import path
            GCSContentManager(bucket_name="adc-bucket") # Relies on from_service_account_json NOT being called
        google_cloud_storage_mock.Client.assert_called_once() # ADC path
        google_cloud_storage_mock.Client.from_service_account_json.assert_not_called()

    def test_initialize_client_with_credentials(self):
        with patch.dict('sys.modules', patch_dict):
            GCSContentManager(bucket_name="cred-bucket", credentials_path="dummy_path.json")
        google_cloud_storage_mock.Client.from_service_account_json.assert_called_with("dummy_path.json")

    def test_get_track_metadata_success(self):
        mock_blob_instance.exists.return_value = True
        metadata_content = {"title": "Test Song", "duration_seconds": 180.0, "content_type": "song"}
        mock_blob_instance.download_as_text.return_value = json.dumps(metadata_content)

        metadata = self.manager.get_track_metadata("audio/test_song.mp3")
        self.assertEqual(metadata, metadata_content)
        mock_bucket_instance.blob.assert_called_with("audio/test_song.mp3" + METADATA_SUFFIX)

    def test_get_track_metadata_not_found(self):
        mock_blob_instance.exists.return_value = False
        metadata = self.manager.get_track_metadata("audio/non_existent.mp3")
        self.assertIsNone(metadata)

    def test_get_track_metadata_invalid_json(self):
        mock_blob_instance.exists.return_value = True
        mock_blob_instance.download_as_text.return_value = "this is not json"
        metadata = self.manager.get_track_metadata("audio/bad_meta.mp3")
        self.assertIsNone(metadata)

    def test_list_audio_tracks_success(self):
        blob1_name = "song1.mp3"
        blob2_name = "song2.wav"
        blob3_name = "image.jpg" # Should be skipped
        blob4_name = "song4_no_meta.mp3"

        mock_blob1 = MagicMock(name=blob1_name); mock_blob1.name = blob1_name
        mock_blob2 = MagicMock(name=blob2_name); mock_blob2.name = blob2_name
        mock_blob3 = MagicMock(name=blob3_name); mock_blob3.name = blob3_name
        mock_blob4 = MagicMock(name=blob4_name); mock_blob4.name = blob4_name

        mock_storage_client_instance.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3, mock_blob4]

        meta1 = {"title": "Song 1", "duration_seconds": 180, "content_type": "song"}
        meta2 = {"title": "Song 2", "duration_seconds": 240, "content_type": "song", "artist": "Artist Foo"}

        def get_metadata_side_effect(gcs_object_path):
            if gcs_object_path == blob1_name: return meta1
            if gcs_object_path == blob2_name: return meta2
            if gcs_object_path == blob4_name: return None # No metadata for blob4
            return None

        with patch.object(self.manager, 'get_track_metadata', side_effect=get_metadata_side_effect) as mock_get_meta:
            tracks = self.manager.list_audio_tracks()

        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].title, "Song 1")
        self.assertEqual(tracks[0].gcs_path, f"gs://{self.bucket_name}/{blob1_name}")
        self.assertEqual(tracks[0].transition_type_in, mock_app_config.playlist["default_transition_type"])
        self.assertEqual(tracks[1].artist, "Artist Foo")
        self.assertEqual(tracks[1].transition_duration_in_ms, mock_app_config.playlist["default_transition_duration_ms"])


    def test_generate_signed_url_success(self):
        mock_blob_instance.exists.return_value = True
        expected_url = "https://signed.url/for/blob"
        mock_blob_instance.generate_signed_url.return_value = expected_url

        url = self.manager.generate_signed_url("audio/song.mp3", expiration_minutes=30)
        self.assertEqual(url, expected_url)
        mock_blob_instance.generate_signed_url.assert_called_once()

    def test_generate_signed_url_blob_not_found(self):
        mock_blob_instance.exists.return_value = False
        url = self.manager.generate_signed_url("audio/non_existent.mp3")
        self.assertIsNone(url)


class TestPlaylistGenerator(unittest.TestCase):
    def setUp(self):
        self.mock_gcs_manager = MagicMock(spec=GCSContentManager)

        # Apply the app_config mock specifically where it's imported by PlaylistGenerator
        self.playlist_generator_config_patch = patch('app.services.playlist.playlist_generator.app_global_config', mock_app_config)
        self.mocked_playlist_app_config = self.playlist_generator_config_patch.start()

        self.generator = PlaylistGenerator(gcs_content_manager=self.mock_gcs_manager)

    def tearDown(self):
        self.playlist_generator_config_patch.stop()

    def test_generate_playlist_basic_count(self):
        sample_items = [PlaylistItem(content_id=f"id{i}", gcs_path=f"gs://b/s{i}.mp3", duration_seconds=180+i, content_type="song") for i in range(5)]
        self.mock_gcs_manager.list_audio_tracks.return_value = sample_items

        playlist = self.generator.generate_playlist(target_item_count=3)
        self.assertEqual(len(playlist.items), 3)
        self.assertTrue(playlist.playlist_id is not None)
        self.assertTrue(playlist.name.startswith(mock_app_config.playlist["default_playlist_name_prefix"]))
        self.assertAlmostEqual(playlist.total_duration_seconds, sum(item.duration_seconds for item in playlist.items))

    def test_generate_playlist_with_criteria(self):
        tracks = [
            PlaylistItem(content_id="s1", gcs_path="gs://b/s1.mp3", duration_seconds=180, content_type="song", genre="Pop"),
            PlaylistItem(content_id="s2", gcs_path="gs://b/s2.mp3", duration_seconds=200, content_type="song", genre="Rock"),
            PlaylistItem(content_id="s3", gcs_path="gs://b/s3.mp3", duration_seconds=220, content_type="song", genre="Pop"),
        ]
        self.mock_gcs_manager.list_audio_tracks.return_value = tracks
        playlist = self.generator.generate_playlist(criteria={"genre": "Pop"}, target_item_count=5) # Request more than available matching
        self.assertEqual(len(playlist.items), 2)
        for item in playlist.items:
            self.assertEqual(item.genre, "Pop")

    def test_generate_playlist_no_tracks_available(self):
        self.mock_gcs_manager.list_audio_tracks.return_value = []
        playlist = self.generator.generate_playlist()
        self.assertEqual(len(playlist.items), 0)


class TestPlaylistScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = PlaylistScheduler()
        self.item1 = PlaylistItem(content_id="s1", gcs_path="gs://b/s1.mp3", duration_seconds=10, content_type="song")
        self.item2 = PlaylistItem(content_id="s2", gcs_path="gs://b/s2.mp3", duration_seconds=12, content_type="song")
        self.playlist_a = Playlist(playlist_id="pl_a", items=[self.item1, self.item2], name="A")

    def test_add_playlist_to_schedule(self):
        self.scheduler.add_playlist_to_schedule(self.playlist_a)
        self.assertEqual(len(self.scheduler.playlist_queue), 1)
        self.assertEqual(self.scheduler.playlist_queue[0].playlist_id, "pl_a")

        playlist_b = Playlist(playlist_id="pl_b", items=[self.item1], name="B")
        self.scheduler.add_playlist_to_schedule(playlist_b, add_to_front=True)
        self.assertEqual(len(self.scheduler.playlist_queue), 2)
        self.assertEqual(self.scheduler.playlist_queue[0].playlist_id, "pl_b")

    def test_get_next_playlist(self):
        self.scheduler.add_playlist_to_schedule(self.playlist_a)
        next_pl = self.scheduler.get_next_playlist()
        self.assertIsNotNone(next_pl)
        self.assertEqual(next_pl.playlist_id, "pl_a")
        self.assertEqual(next_pl.current_status, PlaylistStatus.PLAYING)
        self.assertIsNotNone(next_pl.actual_start_time)
        self.assertEqual(self.scheduler.current_playing_playlist, next_pl)
        self.assertEqual(len(self.scheduler.playlist_queue), 0)

    def test_finish_current_playlist(self):
        self.scheduler.add_playlist_to_schedule(self.playlist_a)
        self.scheduler.get_next_playlist() # Start playlist_a
        self.scheduler.finish_current_playlist()
        self.assertIsNone(self.scheduler.current_playing_playlist)
        self.assertEqual(len(self.scheduler.history), 1)
        self.assertEqual(self.scheduler.history[0].playlist_id, "pl_a")
        self.assertEqual(self.scheduler.history[0].current_status, PlaylistStatus.FINISHED)

    def test_advance_playlist_item(self):
        self.scheduler.add_playlist_to_schedule(self.playlist_a)
        self.scheduler.get_next_playlist()

        item = self.scheduler.advance_playlist_item() # item1
        self.assertEqual(item, self.item1)
        self.assertEqual(self.scheduler.current_playing_playlist.current_item_index, 0)

        item = self.scheduler.advance_playlist_item() # item2
        self.assertEqual(item, self.item2)
        self.assertEqual(self.scheduler.current_playing_playlist.current_item_index, 1)

        item = self.scheduler.advance_playlist_item() # End of playlist
        self.assertIsNone(item)
        self.assertIsNone(self.scheduler.current_playing_playlist) # Playlist should be finished and cleared
        self.assertEqual(len(self.scheduler.history), 1)
        self.assertEqual(self.scheduler.history[0].current_status, PlaylistStatus.FINISHED)


@patch('app.services.playlist.playlist_manager_service.PlaylistScheduler', autospec=True)
@patch('app.services.playlist.playlist_manager_service.PlaylistGenerator', autospec=True)
@patch('app.services.playlist.playlist_manager_service.GCSContentManager', autospec=True)
class TestPlaylistManagerService(unittest.TestCase):
    def setUp(self):
        # Mocks are passed as arguments by @patch decorators
        pass

    def test_create_and_schedule_playlist(self, MockGCSManager, MockPlaylistGen, MockPlaylistSched):
        mock_gcs_instance = MockGCSManager.return_value
        mock_gen_instance = MockPlaylistGen.return_value
        mock_sched_instance = MockPlaylistSched.return_value

        manager = PlaylistManagerService(mock_gcs_instance, mock_gen_instance, mock_sched_instance)

        sample_playlist = Playlist(playlist_id="pl123", items=[PlaylistItem(content_id="c1", gcs_path="gs://p/s.mp3", duration_seconds=10, content_type="song")])
        mock_gen_instance.generate_playlist.return_value = sample_playlist

        crit = {"genre": "pop"}
        returned_playlist = manager.create_and_schedule_playlist(criteria=crit, target_item_count=5, add_to_front=True, playlist_name="My Pop Mix")

        mock_gen_instance.generate_playlist.assert_called_once_with(criteria=crit, target_duration_seconds=None, target_item_count=5, playlist_name_prefix="My Pop Mix")
        mock_sched_instance.add_playlist_to_schedule.assert_called_once_with(sample_playlist, True)
        self.assertEqual(returned_playlist, sample_playlist)
        self.assertEqual(returned_playlist.name, "My Pop Mix") # Check if name was set if generator didn't set it

    def test_advance_to_next_track_within_playlist(self, MockGCSManager, MockPlaylistGen, MockPlaylistSched):
        mock_sched_instance = MockPlaylistSched.return_value
        manager = PlaylistManagerService(None, None, mock_sched_instance) # Other managers not directly used here

        item = PlaylistItem(content_id="c1", gcs_path="gs://p/s.mp3", duration_seconds=10, content_type="song")
        mock_sched_instance.advance_playlist_item.return_value = item

        next_track = manager.advance_to_next_track()
        self.assertEqual(next_track, item)
        mock_sched_instance.advance_playlist_item.assert_called_once()
        mock_sched_instance.get_next_playlist.assert_not_called()

    def test_advance_to_next_track_to_new_playlist(self, MockGCSManager, MockPlaylistGen, MockPlaylistSched):
        mock_sched_instance = MockPlaylistSched.return_value
        manager = PlaylistManagerService(None, None, mock_sched_instance)

        mock_sched_instance.advance_playlist_item.side_effect = [None, PlaylistItem(content_id="c2", gcs_path="gs://p/s2.mp3", duration_seconds=20, content_type="song")]
        mock_sched_instance.get_next_playlist.return_value = Playlist(playlist_id="pl_next", items=[]) # Simulate a new playlist is loaded

        next_track = manager.advance_to_next_track()

        self.assertIsNotNone(next_track)
        self.assertEqual(next_track.content_id, "c2")
        self.assertEqual(mock_sched_instance.advance_playlist_item.call_count, 2)
        mock_sched_instance.get_next_playlist.assert_called_once()


if __name__ == '__main__':
    unittest.main()
```
