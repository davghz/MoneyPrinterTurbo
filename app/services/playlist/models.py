"""
This module defines data models for managing playlists and their items,
primarily for audio content scheduling and playback.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass
class PlaylistItem:
    """
    Represents a single item of content within a playlist.

    Attributes:
        content_id: A unique identifier for this piece of content.
        gcs_path: Full path to the audio file in Google Cloud Storage
                  (e.g., "gs://bucket-name/path/to/audio.mp3").
        duration_seconds: Duration of the audio content in seconds.
        content_type: Type of content (e.g., "song", "dj_banter",
                        "advertisement", "station_id").
        title: Optional title of the content.
        artist: Optional artist of the content.
        album: Optional album of the content.
        genre: Optional genre tag for the content.
        mood_tags: Optional list of mood descriptors (e.g., ["energetic", "upbeat"]).
        generation_params: Optional dictionary of parameters used to generate this
                           content, if AI-generated.
        transition_type_in: Transition type for the start of this item
                              (e.g., "none", "crossfade", "fadein").
        transition_duration_in_ms: Transition duration in milliseconds for the
                                     start of this item.
    """
    content_id: str
    gcs_path: str
    duration_seconds: float
    content_type: str
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    mood_tags: Optional[List[str]] = field(default_factory=list)
    generation_params: Optional[Dict[str, Any]] = field(default_factory=dict)
    transition_type_in: str = "crossfade"
    transition_duration_in_ms: int = 3000


class PlaylistStatus(Enum):
    """
    Represents the possible playback statuses of a playlist.
    """
    SCHEDULED = "scheduled"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class Playlist:
    """
    Represents a playlist, which is an ordered collection of PlaylistItem objects.

    Attributes:
        playlist_id: A unique identifier for this playlist.
        items: The ordered sequence of PlaylistItem objects in this playlist.
        creation_timestamp: Unix timestamp of when the playlist was created.
        scheduled_start_time: Optional Unix timestamp for when the playlist is
                              scheduled to start.
        actual_start_time: Optional Unix timestamp of when playback actually started.
        total_duration_seconds: Calculated total duration of all items in the playlist.
                                This is automatically calculated if items are provided at init.
        current_status: The current playback status of the playlist.
        current_item_index: Index of the currently playing item in the `items` list.
                            -1 indicates not yet started or finished.
        name: Optional user-friendly name for the playlist.
        description: Optional description of the playlist.
    """
    playlist_id: str
    items: List[PlaylistItem] = field(default_factory=list)
    creation_timestamp: float = field(default_factory=time.time)
    scheduled_start_time: Optional[float] = None
    actual_start_time: Optional[float] = None
    total_duration_seconds: float = 0.0
    current_status: PlaylistStatus = PlaylistStatus.SCHEDULED
    current_item_index: int = -1
    name: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """
        Calculates the total duration of the playlist after initialization
        if items are present.
        """
        if not self.total_duration_seconds and self.items: # Only calculate if not already set
            self.calculate_total_duration()

    def calculate_total_duration(self) -> None:
        """
        Calculates and updates the total duration of the playlist based on its items.
        """
        self.total_duration_seconds = sum(item.duration_seconds for item in self.items)

    def add_item(self, item: PlaylistItem, position: Optional[int] = None) -> None:
        """
        Adds an item to the playlist at the specified position.

        Args:
            item: The PlaylistItem to add.
            position: Optional index at which to insert the item. If None,
                      appends to the end.
        """
        if position is None:
            self.items.append(item)
        else:
            self.items.insert(position, item)
        self.calculate_total_duration() # Recalculate duration

    def remove_item(self, content_id: str) -> bool:
        """
        Removes an item from the playlist by its content_id.

        Args:
            content_id: The unique ID of the content item to remove.

        Returns:
            True if an item was removed, False otherwise.
        """
        initial_len = len(self.items)
        self.items = [item for item in self.items if item.content_id != content_id]
        if len(self.items) < initial_len:
            self.calculate_total_duration() # Recalculate duration
            return True
        return False

    def get_item(self, content_id: str) -> Optional[PlaylistItem]:
        """
        Retrieves a playlist item by its content_id.

        Args:
            content_id: The ID of the content to retrieve.

        Returns:
            The PlaylistItem if found, else None.
        """
        for item in self.items:
            if item.content_id == content_id:
                return item
        return None

    def reorder_item(self, content_id: str, new_position: int) -> bool:
        """
        Moves an item within the playlist to a new position.

        Args:
            content_id: The ID of the content item to move.
            new_position: The new zero-based index for the item.

        Returns:
            True if the item was successfully moved, False otherwise.
        """
        item_to_move = None
        current_position = -1
        for i, item in enumerate(self.items):
            if item.content_id == content_id:
                item_to_move = item
                current_position = i
                break

        if item_to_move is None:
            return False # Item not found

        if current_position == new_position:
            return True # No change needed

        self.items.pop(current_position)
        self.items.insert(new_position, item_to_move)
        # Total duration does not change with reordering
        return True

# Example Usage (for illustration, not part of the module's public API directly)
if __name__ == "__main__":
    item1 = PlaylistItem(content_id="song001", gcs_path="gs://bucket/song1.mp3", duration_seconds=185.5, content_type="song", title="My Awesome Song", artist="The Greats")
    item2 = PlaylistItem(content_id="ad001", gcs_path="gs://bucket/ad1.mp3", duration_seconds=30.0, content_type="advertisement", title="Buy Our Stuff!")
    item3 = PlaylistItem(content_id="dj001", gcs_path="gs://bucket/dj_intro.mp3", duration_seconds=15.0, content_type="dj_banter", mood_tags=["upbeat", "intro"])

    # Create a playlist
    my_playlist = Playlist(
        playlist_id="pl_morning_show_001",
        name="Morning Commute Power Mix",
        description="An energetic mix to start your day!",
        items=[item1, item2] # Initial items
    )
    my_playlist.add_item(item3) # Add another item

    print(f"Playlist Name: {my_playlist.name}")
    print(f"Playlist ID: {my_playlist.playlist_id}")
    print(f"Total Duration: {my_playlist.total_duration_seconds} seconds")
    print(f"Status: {my_playlist.current_status.value}")

    for i, item in enumerate(my_playlist.items):
        print(f"  Item {i+1}: {item.title or item.content_type} ({item.duration_seconds}s) - {item.gcs_path}")

    # Example of __post_init__
    # If total_duration_seconds was not calculated by add_item, __post_init__ would do it.
    # Or if items were passed directly at instantiation and total_duration_seconds=0.0 (default)

    # Reorder
    my_playlist.reorder_item("ad001", 0) # Move ad to the beginning
    print("\nAfter reordering ad to be first:")
    for i, item in enumerate(my_playlist.items):
        print(f"  Item {i+1}: {item.title or item.content_type} ({item.duration_seconds}s)")

    # Remove
    my_playlist.remove_item("song001")
    print("\nAfter removing song001:")
    for i, item in enumerate(my_playlist.items):
        print(f"  Item {i+1}: {item.title or item.content_type} ({item.duration_seconds}s)")
    print(f"New Total Duration: {my_playlist.total_duration_seconds} seconds")
```
