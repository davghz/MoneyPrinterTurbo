"""
This module provides the PlaylistScheduler class, responsible for managing
a queue of playlists, tracking playback state, and providing the next
playlist or item to be played.
"""
import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from app.services.playlist.models import (PlaylistItem, Playlist,
                                              PlaylistStatus)
except ImportError:
    logger.error(
        "Error importing playlist models. Ensure models are available for PlaylistScheduler."
    )
    # Dummy classes for basic loading/type checking if models are missing
    from dataclasses import dataclass, field
    from enum import Enum

    class PlaylistStatus(Enum):
        SCHEDULED = "scheduled"
        PLAYING = "playing"
        PAUSED = "paused"
        FINISHED = "finished"
        ERROR = "error"

    @dataclass
    class PlaylistItem:
        content_id: str = "dummy_item"
        duration_seconds: float = 0.0
        # Add other fields if they are directly accessed by scheduler logic

    @dataclass
    class Playlist:
        playlist_id: str
        items: List[PlaylistItem] = field(default_factory=list)
        current_status: PlaylistStatus = PlaylistStatus.SCHEDULED
        current_item_index: int = -1
        actual_start_time: Optional[float] = None
        # Add other fields if they are directly accessed by scheduler logic


class PlaylistScheduler:
    """
    Manages a queue of playlists for sequential playback.

    This class handles adding playlists to a schedule, retrieving the next
    playlist or item to play, and managing the state of the currently
    playing playlist and its items. It is designed to be thread-safe for
    basic operations.
    """

    def __init__(self, logger_instance=None):
        """
        Initializes the PlaylistScheduler.

        Args:
            logger_instance: An optional Loguru logger instance.
        """
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)
        self.playlist_queue: List[Playlist] = []
        self.history: List[Playlist] = [] # Stores finished or errored playlists
        self.current_playing_playlist: Optional[Playlist] = None
        self.lock = threading.Lock()
        self.logger.info("PlaylistScheduler initialized.")

    def add_playlist_to_schedule(self, playlist: Playlist, add_to_front: bool = False) -> None:
        """
        Adds a playlist to the playback schedule.

        If `playlist.scheduled_start_time` is not set, it defaults to now,
        or to be played immediately after the current queue.
        Playlists are generally processed in FIFO order unless `add_to_front` is used.

        Args:
            playlist: The Playlist object to add.
            add_to_front: If True, adds the playlist to the beginning of the queue
                          (to be played next). Otherwise, appends to the end.
        """
        with self.lock:
            if not playlist.items:
                self.logger.warning(f"Attempted to add empty playlist (ID: {playlist.playlist_id}). Skipping.")
                return

            if playlist.scheduled_start_time is None:
                # Basic back-to-back scheduling: if queue has items, schedule after last one.
                # This is a simple heuristic and doesn't account for actual end times yet.
                # For true timed scheduling, sorting would be needed.
                # For now, just setting to current time for simplicity if no other logic present.
                playlist.scheduled_start_time = time.time()

            if add_to_front:
                self.playlist_queue.insert(0, playlist)
                self.logger.info(f"Playlist '{playlist.name or playlist.playlist_id}' ({len(playlist.items)} items) added to front of schedule.")
            else:
                self.playlist_queue.append(playlist)
                self.logger.info(f"Playlist '{playlist.name or playlist.playlist_id}' ({len(playlist.items)} items) added to end of schedule.")

            # If complex time-based scheduling is needed in the future, sort here:
            # self.playlist_queue.sort(key=lambda p: p.scheduled_start_time or float('inf'))

    def get_next_playlist(self) -> Optional[Playlist]:
        """
        Retrieves the next playlist to be played from the schedule.

        If a playlist is currently active (playing or paused), it returns that.
        Otherwise, it attempts to pop the next playlist from the queue, updates its
        status to PLAYING, and sets its actual start time.

        Returns:
            The next Playlist object to be played, or None if the schedule is empty
            and nothing is currently playing.
        """
        with self.lock:
            if self.current_playing_playlist and \
               self.current_playing_playlist.current_status in [PlaylistStatus.PLAYING, PlaylistStatus.PAUSED]:
                self.logger.debug(f"Returning currently active playlist: {self.current_playing_playlist.playlist_id}")
                return self.current_playing_playlist

            if not self.playlist_queue:
                self.logger.info("Playlist schedule is empty. No next playlist.")
                self.current_playing_playlist = None # Ensure cleared
                return None

            next_playlist = self.playlist_queue.pop(0)
            self.current_playing_playlist = next_playlist
            self.current_playing_playlist.actual_start_time = time.time()
            self.current_playing_playlist.current_status = PlaylistStatus.PLAYING
            self.current_playing_playlist.current_item_index = -1 # Reset item index

            self.logger.info(
                f"Starting playlist '{next_playlist.name or next_playlist.playlist_id}' "
                f"({len(next_playlist.items)} items)."
            )
            return self.current_playing_playlist

    def get_current_playing_playlist(self) -> Optional[Playlist]:
        """
        Returns the currently playing (or paused) playlist, if any.

        Returns:
            The current Playlist object or None.
        """
        with self.lock:
            return self.current_playing_playlist

    def finish_current_playlist(self) -> None:
        """
        Marks the currently playing playlist as FINISHED and moves it to history.
        """
        with self.lock:
            if self.current_playing_playlist:
                playlist_id = self.current_playing_playlist.playlist_id
                self.logger.info(f"Finishing playlist '{self.current_playing_playlist.name or playlist_id}'.")
                self.current_playing_playlist.current_status = PlaylistStatus.FINISHED
                # Optionally record actual end time: self.current_playing_playlist.actual_end_time = time.time()
                self.history.append(self.current_playing_playlist)
                self.current_playing_playlist = None
            else:
                self.logger.warning("Request to finish playlist, but no playlist is currently active.")

    def set_current_playlist_error(self, error_message: str) -> None:
        """Marks the currently playing playlist as ERRORED and moves it to history."""
        with self.lock:
            if self.current_playing_playlist:
                playlist_id = self.current_playing_playlist.playlist_id
                self.logger.error(f"Error in playlist '{self.current_playing_playlist.name or playlist_id}': {error_message}")
                self.current_playing_playlist.current_status = PlaylistStatus.ERROR
                # Store error message if Playlist model supports it
                # if hasattr(self.current_playing_playlist, 'error_info'):
                #    self.current_playing_playlist.error_info = error_message
                self.history.append(self.current_playing_playlist)
                self.current_playing_playlist = None
            else:
                self.logger.warning("Request to set playlist error, but no playlist is currently active.")


    def skip_current_playlist(self) -> Optional[Playlist]:
        """
        Skips the currently playing playlist, marks it as ERRORED (or SKIPPED),
        and attempts to start the next one.

        Returns:
            The next Playlist to be played, or None if the queue is empty.
        """
        skipped_playlist_id = None
        with self.lock: # Lock for modifying current_playing_playlist
            if self.current_playing_playlist:
                skipped_playlist_id = self.current_playing_playlist.playlist_id
                self.logger.info(f"Skipping playlist '{self.current_playing_playlist.name or skipped_playlist_id}'.")
                self.current_playing_playlist.current_status = PlaylistStatus.ERROR # Or a new SKIPPED status
                self.history.append(self.current_playing_playlist)
                self.current_playing_playlist = None
            else:
                self.logger.info("Request to skip playlist, but no playlist is currently active.")

        # Getting next playlist handles its own locking
        return self.get_next_playlist()

    def advance_playlist_item(self) -> Optional[PlaylistItem]:
        """
        Advances to the next item in the currently playing playlist.

        If the end of the playlist is reached, it calls `finish_current_playlist()`
        and returns None. The caller is then responsible for calling `get_next_playlist()`
        to proceed to the next playlist in the schedule.

        Returns:
            The next PlaylistItem to be played, or None if the current playlist
            ended or no playlist is active.
        """
        with self.lock: # Lock for accessing/modifying current_playing_playlist and its index
            if not self.current_playing_playlist or \
               self.current_playing_playlist.current_status != PlaylistStatus.PLAYING:
                self.logger.debug("Advance item requested, but no playlist is actively playing.")
                return None

            self.current_playing_playlist.current_item_index += 1
            playlist_id = self.current_playing_playlist.playlist_id

            if self.current_playing_playlist.current_item_index < len(self.current_playing_playlist.items):
                next_item = self.current_playing_playlist.items[self.current_playing_playlist.current_item_index]
                self.logger.info(
                    f"Playlist '{self.current_playing_playlist.name or playlist_id}' advanced to item "
                    f"{self.current_playing_playlist.current_item_index + 1}/{len(self.current_playing_playlist.items)}: "
                    f"'{next_item.title or next_item.content_id}'"
                )
                return next_item
            else:
                self.logger.info(f"End of playlist '{self.current_playing_playlist.name or playlist_id}' reached.")
                # finish_current_playlist will be called by the entity managing playback loop upon seeing None
                # Releasing lock before calling another method of this class that also acquires lock
                # is generally safer to avoid potential deadlocks if not careful, though finish_current_playlist
                # is simple here. For this subtask, direct call is fine.
                # However, the instruction was "The caller of advance_playlist_item can then call get_next_playlist()
                # if this returns None." So, finish_current_playlist should be called here.

                # Temporarily release lock if finish_current_playlist acquires it.
                # Since finish_current_playlist is simple and acquires/releases, this is okay.
                # No, keep lock until state is consistent.
                # Call finish_current_playlist within this lock.
                current_playlist_ref = self.current_playing_playlist # Keep ref for logging
                # self.finish_current_playlist() # This will set self.current_playing_playlist to None

                # Modification: finish_current_playlist should be called by the component
                # that calls advance_playlist_item, after it receives None.
                # This method (advance_playlist_item) just signals that there are no more items.
                # The Playlist object itself should be marked FINISHED by the playback manager.
                # Let's stick to the instruction: "if end of playlist, call finish_current_playlist(), release lock, and return None"
                # This means finish_current_playlist must be safe to call while holding the lock.

                # The finish_current_playlist method handles logging and moving to history.
                # It also sets self.current_playing_playlist to None.
                # This needs to be done carefully if finish_current_playlist also acquires the same lock.
                # For simplicity, let's assume finish_current_playlist handles the lock or is called after releasing.
                # Re-evaluating: finish_current_playlist should be called *within* this lock context
                # to ensure atomicity of finishing one and preparing for next.

                # Corrected logic:
                # finish_current_playlist will be called by the playback loop when this returns None.
                # This method just indicates there are no more items in *this* playlist.
                # The playlist's status will be set to FINISHED by the caller.
                # No, the task says "call finish_current_playlist()".

                # Re-evaluating again based on "if end of playlist, call finish_current_playlist(), release lock, and return None"
                # This means this method is responsible for finishing.
                # The lock management needs care if finish_current_playlist is also locked.
                # It's simpler if finish_current_playlist does NOT acquire the lock, assuming caller holds it.
                # Or, finish_current_playlist acquires and releases its own lock.
                # For now, finish_current_playlist as written acquires its own lock.
                # This is fine.

                # No, the instruction was "call self.finish_current_playlist() (it will handle lock internally)."
                # This is wrong, a lock cannot be acquired re-entrantly by the same thread by default.
                # The best is to make finish_current_playlist a private helper that assumes lock is held, or release before calling.
                # Let's make it a private helper for now.
                self._finish_current_playlist_internal()
                return None # Signal end of this playlist

    def _finish_current_playlist_internal(self) -> None:
        """Internal version of finish_current_playlist, assumes lock is held."""
        if self.current_playing_playlist:
            playlist_id = self.current_playing_playlist.playlist_id
            self.logger.info(f"Finishing playlist '{self.current_playing_playlist.name or playlist_id}' (internal).")
            self.current_playing_playlist.current_status = PlaylistStatus.FINISHED
            self.history.append(self.current_playing_playlist)
            self.current_playing_playlist = None
        else: # Should not happen if called correctly
            self.logger.warning("Internal finish playlist called, but no playlist active.")


    def get_current_playlist_item(self) -> Optional[PlaylistItem]:
        """
        Retrieves the currently playing item from the active playlist.

        Returns:
            The current PlaylistItem, or None if no item is playing or
            no playlist is active.
        """
        with self.lock:
            if self.current_playing_playlist and \
               self.current_playing_playlist.current_status == PlaylistStatus.PLAYING and \
               0 <= self.current_playing_playlist.current_item_index < len(self.current_playing_playlist.items):
                return self.current_playing_playlist.items[self.current_playing_playlist.current_item_index]
            return None

# Example Usage
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG") # Use sys for example

    # Dummy items and playlists for testing
    item1 = PlaylistItem(content_id="s1", gcs_path="gs://b/s1.mp3", duration_seconds=10, content_type="song", title="Song 1")
    item2 = PlaylistItem(content_id="s2", gcs_path="gs://b/s2.mp3", duration_seconds=12, content_type="song", title="Song 2")
    item_ad = PlaylistItem(content_id="ad1", gcs_path="gs://b/ad1.mp3", duration_seconds=5, content_type="ad")

    playlist_a = Playlist(playlist_id="pl_a", items=[item1, item2], name="Pop Mix")
    playlist_b = Playlist(playlist_id="pl_b", items=[item_ad], name="Ads")

    scheduler = PlaylistScheduler()

    logger.info("--- Adding playlists ---")
    scheduler.add_playlist_to_schedule(playlist_a)
    scheduler.add_playlist_to_schedule(playlist_b, add_to_front=True) # Ad plays first

    logger.info(f"Queue size: {len(scheduler.playlist_queue)}")

    logger.info("\n--- Starting Playback Simulation ---")

    active_playlist = scheduler.get_next_playlist()
    while active_playlist:
        logger.info(f"Now playing playlist: {active_playlist.name or active_playlist.playlist_id} (Status: {active_playlist.current_status.value})")
        next_item = scheduler.advance_playlist_item()
        while next_item:
            logger.info(f"  Playing item: {next_item.title or next_item.content_id} (Duration: {next_item.duration_seconds}s)")
            # Simulate item playback
            # time.sleep(1) # Simulate time passing
            current_item_from_getter = scheduler.get_current_playlist_item()
            if current_item_from_getter:
                 logger.debug(f"  Verified current item via getter: {current_item_from_getter.title or current_item_from_getter.content_id}")
            else:
                 logger.error("  Could not verify current item via getter while supposedly playing!")
            next_item = scheduler.advance_playlist_item()

        # Playlist finished, mark it (advance_playlist_item now calls internal finish)
        logger.info(f"Finished playlist: {active_playlist.name or active_playlist.playlist_id}")
        active_playlist = scheduler.get_next_playlist() # Try to get the next one

    logger.info("\n--- Playback Simulation Ended ---")
    logger.info(f"History count: {len(scheduler.history)}")
    for p_hist in scheduler.history:
        logger.info(f"  History: {p_hist.name or p_hist.playlist_id} - Status: {p_hist.current_status.value}")

    # Test skipping
    logger.info("\n--- Testing Skip ---")
    scheduler.add_playlist_to_schedule(playlist_a) # Add Pop Mix again
    scheduler.add_playlist_to_schedule(Playlist(playlist_id="pl_c", items=[item1], name="Short Playlist C"))

    active_playlist = scheduler.get_next_playlist() # Should be Pop Mix
    if active_playlist:
        logger.info(f"Got playlist: {active_playlist.name}")
        next_item = scheduler.advance_playlist_item() # Play first item of Pop Mix
        logger.info(f"Playing first item: {next_item.title if next_item else 'None'}")

        logger.info("Skipping current playlist (Pop Mix)...")
        next_playlist_after_skip = scheduler.skip_current_playlist()

        if next_playlist_after_skip:
            logger.info(f"Next playlist after skip: {next_playlist_after_skip.name or next_playlist_after_skip.playlist_id}")
            item_after_skip = scheduler.advance_playlist_item()
            logger.info(f"  First item of new playlist: {item_after_skip.title if item_after_skip else 'None'}")
            scheduler.finish_current_playlist() # Finish "Short Playlist C"
        else:
            logger.info("No more playlists after skipping.")

    logger.info(f"History count after skip test: {len(scheduler.history)}")
    for p_hist in scheduler.history:
        logger.info(f"  History: {p_hist.name or p_hist.playlist_id} - Status: {p_hist.current_status.value}")

```
