"""
This module defines the PlaylistManagerService, which acts as a high-level
service for managing the entire playlist lifecycle, including generation,
scheduling, and playback progression.
"""
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from app.services.playlist.gcs_content_manager import GCSContentManager
    from app.services.playlist.playlist_generator import PlaylistGenerator
    from app.services.playlist.scheduler import PlaylistScheduler
    from app.services.playlist.models import (Playlist, PlaylistItem,
                                              PlaylistStatus)
except ImportError as e:
    logger.error(
        f"Error importing playlist modules: {e}. PlaylistManagerService may not function correctly."
    )
    # Dummy classes for basic loading/type checking
    if "GCSContentManager" not in globals():
        class GCSContentManager: pass
    if "PlaylistGenerator" not in globals():
        class PlaylistGenerator:
            def generate_playlist(self, *args, **kwargs) -> Optional[Any]: return None
    if "PlaylistScheduler" not in globals():
        class PlaylistScheduler:
            def add_playlist_to_schedule(self, *args, **kwargs): pass
            def get_current_playing_playlist(self) -> Optional[Any]: return None
            def get_current_playlist_item(self) -> Optional[Any]: return None
            def advance_playlist_item(self) -> Optional[Any]: return None
            def get_next_playlist(self) -> Optional[Any]: return None
            playlist_queue: List[Any] = []
            history: List[Any] = []
    if "Playlist" not in globals():
        from dataclasses import dataclass, field
        @dataclass
        class Playlist:
            playlist_id: str = "dummy_playlist"
            items: List[Any] = field(default_factory=list)
            current_item_index: int = -1
    if "PlaylistItem" not in globals():
        from dataclasses import dataclass
        @dataclass
        class PlaylistItem:
            content_id: str = "dummy_item"


class PlaylistManagerService:
    """
    Manages the overall playlist lifecycle, including generation from GCS content,
    scheduling for playback, and advancing through tracks.
    """

    def __init__(
        self,
        gcs_content_manager: GCSContentManager,
        playlist_generator: PlaylistGenerator,
        playlist_scheduler: PlaylistScheduler,
        logger_instance=None,
    ):
        """
        Initializes the PlaylistManagerService.

        Args:
            gcs_content_manager: Instance of GCSContentManager for track discovery.
            playlist_generator: Instance of PlaylistGenerator for creating playlists.
            playlist_scheduler: Instance of PlaylistScheduler for managing playback queue.
            logger_instance: Optional Loguru logger instance.
        """
        self.gcs_content_manager = gcs_content_manager
        self.playlist_generator = playlist_generator
        self.playlist_scheduler = playlist_scheduler
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)
        self.logger.info("PlaylistManagerService initialized.")

    def create_and_schedule_playlist(
        self,
        criteria: Optional[Dict[str, Any]] = None,
        target_duration_seconds: Optional[int] = None,
        target_item_count: Optional[int] = None,
        add_to_front: bool = False,
        playlist_name: Optional[str] = None,
    ) -> Optional[Playlist]:
        """
        Generates a new playlist based on criteria and schedules it for playback.

        Args:
            criteria: Criteria for the PlaylistGenerator.
            target_duration_seconds: Approximate desired total duration.
            target_item_count: Approximate desired number of items.
            add_to_front: Whether to add the new playlist to the front of the schedule.
            playlist_name: Optional name for the generated playlist. If not provided,
                           a default name will be generated.

        Returns:
            The generated and scheduled Playlist object, or None if generation failed
            or resulted in an empty playlist.
        """
        self.logger.info(
            f"Request to create and schedule playlist. Criteria: {criteria}, "
            f"Target Duration: {target_duration_seconds}s, Target Items: {target_item_count}, "
            f"Add to Front: {add_to_front}, Playlist Name: {playlist_name}"
        )

        playlist_name_prefix = playlist_name or "AutoPlaylist"

        try:
            generated_playlist = self.playlist_generator.generate_playlist(
                criteria=criteria,
                target_duration_seconds=target_duration_seconds,
                target_item_count=target_item_count,
                playlist_name_prefix=playlist_name_prefix
            )
        except Exception as e:
            self.logger.error(f"Error during playlist generation: {e}", exc_info=True)
            return None

        if generated_playlist and generated_playlist.items:
            if playlist_name and not generated_playlist.name: # If a specific name was requested
                generated_playlist.name = playlist_name

            self.playlist_scheduler.add_playlist_to_schedule(generated_playlist, add_to_front)
            self.logger.success(
                f"Playlist '{generated_playlist.name or generated_playlist.playlist_id}' generated with "
                f"{len(generated_playlist.items)} items and successfully scheduled."
            )
            return generated_playlist
        else:
            self.logger.warning(
                "Playlist generation failed or resulted in an empty playlist. Nothing scheduled."
            )
            return None

    def get_current_track_and_upcoming(self, upcoming_count: int = 5) -> Dict[str, Optional[Any]]:
        """
        Retrieves the currently playing track and a list of upcoming tracks
        primarily from the current playlist.

        Args:
            upcoming_count: The maximum number of upcoming tracks to retrieve.

        Returns:
            A dictionary containing information about the current track and
            a list of upcoming PlaylistItem objects from the current playlist.
        """
        current_playlist = self.playlist_scheduler.get_current_playing_playlist()
        current_item = self.playlist_scheduler.get_current_playlist_item()

        upcoming_tracks_in_current: List[PlaylistItem] = []

        if current_playlist and current_item is not None and current_playlist.items:
            current_idx = current_playlist.current_item_index
            if 0 <= current_idx < len(current_playlist.items):
                start_index_for_upcoming = current_idx + 1
                end_index_for_upcoming = start_index_for_upcoming + upcoming_count
                upcoming_tracks_in_current = current_playlist.items[start_index_for_upcoming:end_index_for_upcoming]

        # Future: Peek into self.playlist_scheduler.playlist_queue for more upcoming tracks
        # if len(upcoming_tracks_in_current) < upcoming_count.
        # This would require a peek method in PlaylistScheduler.
        # For now, upcoming_tracks_from_next_playlists is omitted.

        status_info = {
            "current_playlist_id": current_playlist.playlist_id if current_playlist else None,
            "current_track": current_item,
            "current_track_index_in_playlist": current_playlist.current_item_index if current_playlist else -1,
            "upcoming_tracks_in_current_playlist": upcoming_tracks_in_current,
        }
        self.logger.debug(f"Current track and upcoming: {status_info}")
        return status_info

    def advance_to_next_track(self) -> Optional[PlaylistItem]:
        """
        Advances to the next track in the schedule.

        This involves advancing within the current playlist or moving to the
        next playlist if the current one has finished.

        Returns:
            The next PlaylistItem to be played, or None if the entire schedule is empty.
        """
        self.logger.debug("Attempting to advance to the next track.")

        next_item = self.playlist_scheduler.advance_playlist_item()

        if next_item:
            self.logger.info(f"Advanced to next track in current playlist: {next_item.title or next_item.content_id}")
            return next_item
        else:
            # Current playlist finished (or was never started/active)
            self.logger.info("Current playlist finished or no item was playing. Attempting to load next playlist.")
            next_playlist = self.playlist_scheduler.get_next_playlist()
            if next_playlist:
                # New playlist loaded, now get its first item
                first_item_of_new_playlist = self.playlist_scheduler.advance_playlist_item()
                if first_item_of_new_playlist:
                    self.logger.info(
                        f"Started new playlist '{next_playlist.name or next_playlist.playlist_id}'. "
                        f"First track: {first_item_of_new_playlist.title or first_item_of_new_playlist.content_id}"
                    )
                else: # Should not happen if playlist has items and add_playlist_to_schedule checks for empty
                    self.logger.warning(f"New playlist '{next_playlist.name or next_playlist.playlist_id}' started but has no playable items.")
                return first_item_of_new_playlist
            else:
                self.logger.info("Schedule is now empty. No more tracks to play.")
                return None

    def get_current_scheduler_status(self) -> Dict[str, Any]:
        """
        Provides a summary of the playlist scheduler's current state.

        Returns:
            A dictionary containing scheduler status details.
        """
        current_p = self.playlist_scheduler.get_current_playing_playlist()
        current_item = self.playlist_scheduler.get_current_playlist_item()

        status = {
            "current_playlist_id": current_p.playlist_id if current_p else None,
            "current_playlist_name": current_p.name if current_p else None,
            "current_playlist_status": current_p.current_status.value if current_p else None,
            "current_track_index": current_p.current_item_index if current_p else -1,
            "current_track_id": current_item.content_id if current_item else None,
            "current_track_title": current_item.title if current_item else None,
            "queued_playlists_count": len(self.playlist_scheduler.playlist_queue),
            "history_playlists_count": len(self.playlist_scheduler.history),
        }
        self.logger.debug(f"Scheduler status: {status}")
        return status

# Example Usage
if __name__ == "__main__":
    import sys
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # --- Mock GCSContentManager and PlaylistGenerator for local testing ---
    class MockGCSContentManager:
        def list_audio_tracks(self, prefix: Optional[str] = None, limit: Optional[int] = None) -> List[PlaylistItem]:
            logger.info(f"MockGCS: list_audio_tracks called (prefix={prefix}, limit={limit})")
            return [
                PlaylistItem(content_id=f"track{i}", gcs_path=f"gs://mock/track{i}.mp3", duration_seconds=float(180 + i*10), content_type="song", title=f"Song {i}")
                for i in range(1, (limit or 5) + 1) # Create up to 'limit' or 5 tracks
            ]

    class MockPlaylistGenerator:
        def __init__(self, gcs_manager, logger_instance=None):
            self.gcs_manager = gcs_manager
            self.logger = logger_instance or logger

        def generate_playlist(self, criteria: Optional[Dict[str, Any]] = None,
                              target_duration_seconds: Optional[int] = None,
                              target_item_count: Optional[int] = None,
                              playlist_name_prefix: str = "MockPlaylist") -> Playlist:
            self.logger.info(f"MockGen: generate_playlist called with items={target_item_count or 3}")
            items = self.gcs_manager.list_audio_tracks(limit=target_item_count or 3)
            playlist_id = f"mock_pl_{uuid.uuid4().hex[:8]}"
            name = f"{playlist_name_prefix} - {time.strftime('%H%M%S')}"
            return Playlist(playlist_id=playlist_id, items=items, name=name)

    # --- End Mocks ---

    mock_gcs = MockGCSContentManager(bucket_name="test-bucket")
    mock_generator = MockPlaylistGenerator(gcs_content_manager=mock_gcs)
    scheduler = PlaylistScheduler()

    manager = PlaylistManagerService(
        gcs_content_manager=mock_gcs,
        playlist_generator=mock_generator,
        playlist_scheduler=scheduler,
        logger_instance=logger
    )

    logger.info("\n--- Creating and scheduling first playlist (3 items) ---")
    playlist1 = manager.create_and_schedule_playlist(target_item_count=3, playlist_name="Pop Party")
    if playlist1:
         logger.info(f"Scheduled playlist: {playlist1.name} with {len(playlist1.items)} tracks.")

    logger.info("\n--- Creating and scheduling second playlist (2 items, to front) ---")
    playlist2 = manager.create_and_schedule_playlist(target_item_count=2, add_to_front=True, playlist_name="Chill Vibes")
    if playlist2:
        logger.info(f"Scheduled playlist: {playlist2.name} with {len(playlist2.items)} tracks at front.")

    logger.info(f"\n--- Current Scheduler Status ---")
    logger.info(manager.get_current_scheduler_status())

    logger.info("\n--- Simulating Playback ---")
    track_count = 0
    max_tracks_to_play = 7 # Play a few tracks across playlists

    while track_count < max_tracks_to_play:
        current_info = manager.get_current_track_and_upcoming(upcoming_count=2)
        current_track = current_info.get("current_track")

        if not current_track: # Might be the first call, or end of all playlists
            logger.info("No current track, advancing to potentially start first/next playlist...")

        next_track_to_play = manager.advance_to_next_track()

        if next_track_to_play:
            logger.info(
                f"Now Playing: {next_track_to_play.title or next_track_to_play.content_id} "
                f"(from Playlist: {manager.playlist_scheduler.get_current_playing_playlist().name if manager.playlist_scheduler.get_current_playing_playlist() else 'N/A'})"
            )
            track_count += 1
            # Simulate playback time
            # time.sleep(0.1)

            # Log upcoming tracks after advancing
            updated_info = manager.get_current_track_and_upcoming(upcoming_count=2)
            upcoming = updated_info.get("upcoming_tracks_in_current_playlist", [])
            if upcoming:
                logger.info(f"  Upcoming in current playlist: {[t.title or t.content_id for t in upcoming]}")
            else:
                logger.info("  No more tracks upcoming in the current playlist.")
        else:
            logger.info("Playback finished - No more tracks in schedule.")
            break

    logger.info("\n--- Final Scheduler Status ---")
    logger.info(manager.get_current_scheduler_status())

    logger.info("\n--- Playlist History ---")
    for p_hist in scheduler.history:
         logger.info(f"  Played: {p_hist.name or p_hist.playlist_id} - Status: {p_hist.current_status.value} - Items: {len(p_hist.items)}")

    logger.info("\n--- Example finished ---")

```
