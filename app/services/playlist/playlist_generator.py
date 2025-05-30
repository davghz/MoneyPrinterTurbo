"""
This module provides the PlaylistGenerator class, responsible for creating
playlists based on available content and specified criteria.
"""
import random
import time
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from app.services.playlist.gcs_content_manager import GCSContentManager
    from app.services.playlist.models import Playlist, PlaylistItem
except ImportError as e:
    logger.error(
        f"Error importing playlist modules: {e}. Ensure GCSContentManager and playlist models are available."
    )
    # Define dummy classes if imports fail for basic loading/type checking
    if "GCSContentManager" not in globals():
        class GCSContentManager:
            def __init__(self, bucket_name: str, credentials_path: Optional[str] = None, logger_instance=None):
                self.logger = logger_instance or logger
                self.logger.warning("Dummy GCSContentManager initialized.")
            def list_audio_tracks(self, prefix: Optional[str] = None, limit: Optional[int] = None) -> List[Any]:
                self.logger.warning("Dummy GCSContentManager: list_audio_tracks called, returning empty list.")
                return []
    if "PlaylistItem" not in globals():
        from dataclasses import dataclass, field
        @dataclass
        class PlaylistItem:
            content_id: str = "dummy_id"
            gcs_path: str = "gs://dummy/path"
            duration_seconds: float = 0.0
            content_type: str = "unknown"
    if "Playlist" not in globals():
        from dataclasses import dataclass, field
        @dataclass
        class Playlist:
            playlist_id: str
            items: List[PlaylistItem] = field(default_factory=list)
            total_duration_seconds: float = 0.0
            name: Optional[str] = None
            # Add other fields as per actual model for completeness if needed by generator
            def __post_init__(self): pass # Dummy
            def calculate_total_duration(self): pass # Dummy


class PlaylistGenerator:
    """
    Generates playlists by selecting tracks from a GCSContentManager.

    The current implementation uses basic filtering and random selection based
    on item count. Future enhancements can include more sophisticated selection
    logic based on criteria, duration targets, and AI rules.
    """

    def __init__(self, gcs_content_manager: GCSContentManager, logger_instance=None):
        """
        Initializes the PlaylistGenerator.

        Args:
            gcs_content_manager: An instance of GCSContentManager to fetch track information.
            logger_instance: An optional Loguru logger instance.
        """
        self.gcs_content_manager = gcs_content_manager
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)

        # Import app_config here for defaults
        from app.config import config as app_global_config
        self.default_target_item_count = app_global_config.playlist.get("default_playlist_target_item_count", 10)
        self.default_playlist_name_prefix = app_global_config.playlist.get("default_playlist_name_prefix", "AutoPlaylist")

        self.logger.info(
            f"PlaylistGenerator initialized. Defaults: "
            f"item_count={self.default_target_item_count}, "
            f"name_prefix='{self.default_playlist_name_prefix}'"
        )


    def _filter_tracks_by_criteria(
        self, tracks: List[PlaylistItem], criteria: Dict[str, Any]
    ) -> List[PlaylistItem]:
        """
        Filters a list of tracks based on provided criteria.
        (Simple initial implementation)

        Args:
            tracks: The list of PlaylistItem objects to filter.
            criteria: A dictionary of criteria (e.g., {'genre': 'electronic'}).

        Returns:
            A new list of PlaylistItem objects that match the criteria.
        """
        if not criteria:
            return tracks

        filtered_tracks = tracks
        self.logger.debug(f"Filtering {len(tracks)} tracks with criteria: {criteria}")

        if "genre" in criteria:
            genre_criteria = criteria["genre"].lower()
            filtered_tracks = [
                track for track in filtered_tracks if track.genre and track.genre.lower() == genre_criteria
            ]
            self.logger.debug(f"{len(filtered_tracks)} tracks after genre filter: {genre_criteria}")

        if "content_type" in criteria:
            content_type_criteria = criteria["content_type"].lower()
            filtered_tracks = [
                track for track in filtered_tracks if track.content_type and track.content_type.lower() == content_type_criteria
            ]
            self.logger.debug(f"{len(filtered_tracks)} tracks after content_type filter: {content_type_criteria}")

        if "mood_tags" in criteria:
            mood_criteria = [tag.lower() for tag in criteria["mood_tags"]]
            if mood_criteria: # Only filter if mood_tags are specified
                filtered_tracks = [
                    track for track in filtered_tracks if track.mood_tags and
                    any(tag.lower() in mood_criteria for tag in track.mood_tags)
                ]
                self.logger.debug(f"{len(filtered_tracks)} tracks after mood_tags filter: {mood_criteria}")

        # Note: More complex criteria (e.g. artist, album, duration ranges) can be added here.
        if criteria and not ({"genre", "content_type", "mood_tags"} & criteria.keys()):
             self.logger.warning(f"Some provided criteria are not yet implemented for filtering: {criteria}")

        return filtered_tracks

    def generate_playlist(
        self,
        criteria: Optional[Dict[str, Any]] = None,
        target_duration_seconds: Optional[int] = None,
        target_item_count: Optional[int] = None,
        playlist_name_prefix: Optional[str] = None # Changed to Optional to use configured default
    ) -> Playlist:
        """
        Generates a new playlist.

        Args:
            criteria: Filtering criteria for track selection (e.g., genre, mood).
            target_duration_seconds: Approximate desired total duration of the playlist.
                                     (Currently informational, selection is primarily count-based).
            target_item_count: Desired number of items in the playlist.
                               Defaults to `self.default_target_item_count` from config.
            playlist_name_prefix: Prefix for the generated playlist name.
                                  Defaults to `self.default_playlist_name_prefix` from config.

        Returns:
            A Playlist object. Returns an empty playlist if no suitable tracks are found.
        """
        used_target_item_count = target_item_count if target_item_count is not None else self.default_target_item_count
        used_playlist_name_prefix = playlist_name_prefix if playlist_name_prefix is not None else self.default_playlist_name_prefix

        self.logger.info(
            f"Generating playlist with criteria: {criteria}, "
            f"target_duration: {target_duration_seconds}s (informational), "
            f"target_items: {used_target_item_count} (using default if not specified), "
            f"name_prefix: '{used_playlist_name_prefix}'"
        )

        available_tracks = self.gcs_content_manager.list_audio_tracks()
        if not available_tracks:
            self.logger.warning("No tracks available from GCSContentManager. Returning empty playlist.")
            return Playlist(playlist_id=uuid.uuid4().hex, name=f"{used_playlist_name_prefix} (Empty) - {time.strftime('%Y%m%d-%H%M%S')}")

        self.logger.info(f"Fetched {len(available_tracks)} total tracks from GCS.")

        # Filter tracks based on criteria
        if criteria:
            filtered_tracks = self._filter_tracks_by_criteria(available_tracks, criteria)
        else:
            filtered_tracks = available_tracks

        if not filtered_tracks:
            self.logger.warning(f"No tracks matched the criteria {criteria}. Returning empty playlist.")
            return Playlist(playlist_id=uuid.uuid4().hex, name=f"{used_playlist_name_prefix} (No Matches) - {time.strftime('%Y%m%d-%H%M%S')}")

        self.logger.info(f"{len(filtered_tracks)} tracks remaining after filtering.")

        if len(filtered_tracks) < used_target_item_count:
            self.logger.warning(
                f"Number of available filtered tracks ({len(filtered_tracks)}) is less than "
                f"target_item_count ({used_target_item_count}). Using all available filtered tracks."
            )
            selected_items = filtered_tracks
        else:
            selected_items = random.sample(filtered_tracks, used_target_item_count)

        self.logger.info(f"Selected {len(selected_items)} items for the playlist.")
        if target_duration_seconds: # Log if provided, even if not strictly used for selection
            current_total_duration = sum(item.duration_seconds for item in selected_items)
            self.logger.info(
                f"Desired target duration was {target_duration_seconds}s. "
                f"Selected items current total duration: {current_total_duration:.2f}s. "
                "(Note: Current selection is primarily item-count based)."
            )
            # Future: Implement duration-based selection strategy more strictly here.

        # Create Playlist Object
        playlist_id = uuid.uuid4().hex
        playlist_name = f"{used_playlist_name_prefix} - {time.strftime('%Y%m%d-%H%M%S')}"

        new_playlist = Playlist(
            playlist_id=playlist_id,
            name=playlist_name,
            items=selected_items,
            # __post_init__ will calculate total_duration_seconds
        )

        self.logger.success(
            f"Generated playlist '{new_playlist.name}' (ID: {new_playlist.playlist_id}) "
            f"with {len(new_playlist.items)} items, total duration: {new_playlist.total_duration_seconds:.2f}s."
        )
        return new_playlist

    # --- Placeholder for Future Enhancements ---
    def _apply_ai_selection_rules(self, tracks: List[PlaylistItem], playlist_so_far: Playlist) -> List[PlaylistItem]:
        """
        (Future Enhancement) Applies AI-driven rules for more intelligent track selection.
        e.g., based on mood progression, artist separation, etc.
        """
        self.logger.info("AI selection rules placeholder: not yet implemented.")
        return tracks # No change for now

    def _insert_dj_segments(self, playlist: Playlist) -> Playlist:
        """
        (Future Enhancement) Inserts DJ banter, station IDs, or ads into the playlist.
        """
        self.logger.info("DJ segment insertion placeholder: not yet implemented.")
        return playlist # No change for now


# Example Usage
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG") # Use sys for example, not defined otherwise

    # This example requires a running GCS emulator or real GCS bucket configured.
    # For real GCS, ensure GOOGLE_APPLICATION_CREDENTIALS is set.

    # --- Mock GCSContentManager for local testing without real GCS ---
    class MockGCSContentManager:
        def __init__(self, bucket_name: str, credentials_path: Optional[str] = None, logger_instance=None):
            self.logger = logger_instance or logger
            self.bucket_name = bucket_name
            self.logger.info(f"MockGCSContentManager initialized for bucket '{bucket_name}'.")

        def list_audio_tracks(self, prefix: Optional[str] = None, limit: Optional[int] = None) -> List[PlaylistItem]:
            self.logger.info(f"Mock list_audio_tracks called with prefix: {prefix}, limit: {limit}")
            sample_items = [
                PlaylistItem(content_id="song001", gcs_path="gs://mock/song1.mp3", duration_seconds=180, content_type="song", title="Song A", artist="Artist X", genre="Pop", mood_tags=["upbeat"]),
                PlaylistItem(content_id="song002", gcs_path="gs://mock/song2.mp3", duration_seconds=240, content_type="song", title="Song B", artist="Artist Y", genre="Rock", mood_tags=["energetic"]),
                PlaylistItem(content_id="song003", gcs_path="gs://mock/song3.mp3", duration_seconds=200, content_type="song", title="Song C", artist="Artist Z", genre="Pop", mood_tags=["chill"]),
                PlaylistItem(content_id="ad001", gcs_path="gs://mock/ad1.mp3", duration_seconds=30, content_type="advertisement", title="Ad 1"),
                PlaylistItem(content_id="dj001", gcs_path="gs://mock/dj1.mp3", duration_seconds=15, content_type="dj_banter", title="DJ Intro"),
                PlaylistItem(content_id="song004", gcs_path="gs://mock/song4.mp3", duration_seconds=210, content_type="song", title="Song D", artist="Artist X", genre="Electronic", mood_tags=["driving", "upbeat"]),
                PlaylistItem(content_id="song005", gcs_path="gs://mock/song5.mp3", duration_seconds=190, content_type="song", title="Song E", artist="Artist Y", genre="Rock", mood_tags=["powerful"]),
            ]
            if limit:
                return random.sample(sample_items, min(limit, len(sample_items)))
            return sample_items
    # --- End Mock GCSContentManager ---

    # Use MockGCSContentManager for the example
    mock_gcs_manager = MockGCSContentManager(bucket_name="test-bucket")
    generator = PlaylistGenerator(gcs_content_manager=mock_gcs_manager)

    logger.info("\n--- Generating default playlist (10 items) ---")
    playlist1 = generator.generate_playlist()
    for item in playlist1.items:
        logger.debug(f"  Playlist1 Item: {item.title or item.content_id} ({item.content_type})")

    logger.info(f"\n--- Generating 'Pop' genre playlist (3 items) ---")
    pop_criteria = {"genre": "Pop"}
    playlist2 = generator.generate_playlist(criteria=pop_criteria, target_item_count=3, playlist_name_prefix="Pop Hits")
    for item in playlist2.items:
        logger.debug(f"  Playlist2 Item: {item.title or item.content_id} ({item.content_type}, Genre: {item.genre})")

    logger.info(f"\n--- Generating 'advertisement' content type playlist (2 items) ---")
    ad_criteria = {"content_type": "advertisement"}
    playlist3 = generator.generate_playlist(criteria=ad_criteria, target_item_count=2)
    for item in playlist3.items:
        logger.debug(f"  Playlist3 Item: {item.title or item.content_id} ({item.content_type})")

    logger.info(f"\n--- Generating 'upbeat' mood playlist (4 items) ---")
    upbeat_criteria = {"mood_tags": ["upbeat"]}
    playlist4 = generator.generate_playlist(criteria=upbeat_criteria, target_item_count=4)
    for item in playlist4.items:
        logger.debug(f"  Playlist4 Item: {item.title or item.content_id} (Moods: {item.mood_tags})")

    logger.info(f"\n--- Generating playlist with target duration (informational) ---")
    playlist5 = generator.generate_playlist(target_duration_seconds=300, target_item_count=2) # Count will be prioritized

    logger.info("\n--- Example finished ---")
```
