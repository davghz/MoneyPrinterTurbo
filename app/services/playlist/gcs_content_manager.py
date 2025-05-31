"""
Manages audio content stored in Google Cloud Storage (GCS), serving as a key component
of the playlist handling engine.

This module is responsible for interacting with a GCS bucket to discover audio tracks,
retrieve associated metadata (from `.meta.json` files), and construct `PlaylistItem`
objects. It can also generate GCS signed URLs for direct media access if needed.
"""
import json
import os
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from google.cloud import storage
    from google.auth import exceptions as google_auth_exceptions
    GOOGLE_CLOUD_LIBS_AVAILABLE = True
except ImportError:
    logger.critical(
        "google-cloud-storage or google-auth not found. GCSContentManager will not function. "
        "Please install with: pip install google-cloud-storage google-auth"
    )
    GOOGLE_CLOUD_LIBS_AVAILABLE = False

try:
    from app.services.playlist.models import PlaylistItem # Assuming this path from previous tasks
except ImportError:
    logger.warning("PlaylistItem model not found. Using a dummy for GCSContentManager.")
    from dataclasses import dataclass, field
    @dataclass
    class PlaylistItem:
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


# Define common audio extensions - This will now be loaded from config
# SUPPORTED_AUDIO_EXTENSIONS = (".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus") # Commented out
METADATA_SUFFIX = ".meta.json"

from app.config import config as app_config # Import global app config

class GCSContentManager:
    """
    Manages audio content stored in a Google Cloud Storage bucket.

    Provides methods to list tracks, retrieve metadata, and potentially
    generate access URLs. Assumes metadata for each audio track is stored
    in a corresponding JSON file (e.g., 'track.mp3.meta.json').
    """

    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None,
        logger_instance=None,
    ):
        """
        Initializes the GCSContentManager.

        Args:
            bucket_name: The name of the GCS bucket to manage.
            credentials_path: Optional path to a Google Cloud service account JSON file.
                              If not provided, Application Default Credentials (ADC) will be used.
            logger_instance: An optional Loguru logger instance. If None, a default
                             logger will be used.
        """
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)
        self.storage_client: Optional[storage.Client] = None

        if GOOGLE_CLOUD_LIBS_AVAILABLE:
            self._initialize_client()
        else:
            self.logger.error("GCSContentManager cannot operate: google-cloud-storage library not available.")

    def _initialize_client(self) -> None:
        """Initializes the Google Cloud Storage client."""
        try:
            if self.credentials_path:
                self.logger.info(f"Initializing GCS client with service account: {self.credentials_path}")
                self.storage_client = storage.Client.from_service_account_json(self.credentials_path)
            else:
                self.logger.info("Initializing GCS client using Application Default Credentials (ADC).")
                self.storage_client = storage.Client()
            self.logger.info(f"GCS client initialized successfully for bucket '{self.bucket_name}'.")
        except FileNotFoundError:
            self.logger.error(f"Service account file not found at: {self.credentials_path}")
            self.storage_client = None
        except google_auth_exceptions.DefaultCredentialsError as e:
            self.logger.error(f"GCS ADC authentication failed: {e}. Ensure ADC are configured or provide credentials_path.")
            self.storage_client = None
        except Exception as e:
            self.logger.error(f"Failed to initialize GCS client: {e}", exc_info=True)
            self.storage_client = None

    def get_track_metadata(self, gcs_object_path: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves and parses the JSON metadata file for a given GCS audio object.
        Assumes metadata file is named 'object_path.meta.json'.

        Args:
            gcs_object_path: The path of the audio object within the bucket
                             (e.g., "path/to/your/track.mp3").

        Returns:
            A dictionary containing the parsed metadata if the corresponding
            `.meta.json` file is found and valid. Returns None if the metadata
            file does not exist, cannot be downloaded, or contains invalid JSON.
        """
        if not self.storage_client:
            self.logger.error("GCS client not initialized. Cannot fetch metadata.")
            return None

        metadata_blob_name = gcs_object_path + METADATA_SUFFIX
        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(metadata_blob_name)
            if not blob.exists():
                self.logger.warning(f"Metadata file not found for '{gcs_object_path}' at '{metadata_blob_name}'.")
                return None

            metadata_str = blob.download_as_text()
            metadata = json.loads(metadata_str)
            self.logger.debug(f"Successfully downloaded and parsed metadata for '{gcs_object_path}'.")
            return metadata
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in metadata file '{metadata_blob_name}': {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to download or parse metadata for '{gcs_object_path}': {e}", exc_info=True)
            return None

    def list_audio_tracks(
        self, prefix: Optional[str] = None, limit: Optional[int] = None
    ) -> List[PlaylistItem]:
        """
        Lists audio tracks from the GCS bucket and attempts to pair them with metadata.

        Args:
            prefix: Optional path prefix to filter objects within the GCS bucket
                    (e.g., "artists/some_artist/").
            limit: Optional maximum number of audio tracks to retrieve.

        Returns:
            A list of `PlaylistItem` objects. Each item is constructed from GCS blob
            information and its corresponding `.meta.json` file. Tracks are skipped
            if metadata is missing, essential fields like `duration_seconds` are
            absent or invalid, or if they don't match supported audio extensions
            defined in the application configuration. Transition parameters for items
            are taken from metadata if present, otherwise defaults from app config
            are used.
        """
        if not self.storage_client:
            self.logger.error("GCS client not initialized. Cannot list audio tracks.")
            return []

        playlist_items: List[PlaylistItem] = []
        self.logger.info(f"Listing audio tracks in bucket '{self.bucket_name}' with prefix '{prefix or ''}'.")

        try:
            blobs = self.storage_client.list_blobs(self.bucket_name, prefix=prefix, max_results=limit)

            # Load supported extensions from config, with a fallback
            supported_extensions = tuple(app_config.playlist.get("supported_audio_extensions", [".mp3", ".wav", ".aac"]))
            self.logger.debug(f"Using supported audio extensions: {supported_extensions}")

            for blob in blobs:
                if not blob.name.lower().endswith(supported_extensions): # Use lower() for case-insensitive match
                    self.logger.debug(f"Skipping non-audio file or unsupported extension: {blob.name}")
                    continue

                if blob.name.endswith(METADATA_SUFFIX): # Skip metadata files themselves
                    continue

                self.logger.debug(f"Processing potential audio track: {blob.name}")
                metadata = self.get_track_metadata(blob.name)

                if not metadata:
                    self.logger.warning(f"No metadata found for audio track: {blob.name}. Skipping.")
                    continue

                # Validate essential metadata fields (especially duration)
                duration = metadata.get("duration_seconds")
                if duration is None:
                    self.logger.warning(f"Metadata for '{blob.name}' is missing 'duration_seconds'. Skipping.")
                    continue
                try:
                    duration_float = float(duration)
                except ValueError:
                    self.logger.warning(f"Invalid 'duration_seconds' format ('{duration}') for '{blob.name}'. Skipping.")
                    continue

                gcs_full_path = f"gs://{self.bucket_name}/{blob.name}"

                # Construct PlaylistItem using metadata. get() for optional fields.
                item = PlaylistItem(
                    content_id=metadata.get("content_id", os.path.splitext(os.path.basename(blob.name))[0]),
                    gcs_path=gcs_full_path,
                    duration_seconds=duration_float,
                    content_type=metadata.get("content_type", "unknown"),
                    title=metadata.get("title"),
                    artist=metadata.get("artist"),
                    album=metadata.get("album"),
                    genre=metadata.get("genre"),
                    mood_tags=metadata.get("mood_tags", field(default_factory=list)), # Ensure list if missing
                    generation_params=metadata.get("generation_params", field(default_factory=dict)), # Ensure dict if missing
                    transition_type_in=metadata.get(
                        "transition_type_in",
                        app_config.playlist.get("default_transition_type", "crossfade")
                    ),
                    transition_duration_in_ms=int(metadata.get(
                        "transition_duration_in_ms",
                        app_config.playlist.get("default_transition_duration_ms", 3000)
                    ))
                )
                playlist_items.append(item)

                if limit is not None and len(playlist_items) >= limit:
                    self.logger.info(f"Reached item limit of {limit}.")
                    break

            self.logger.info(f"Found {len(playlist_items)} audio tracks with metadata.")
            return playlist_items

        except google_auth_exceptions.GoogleAuthError as e:
            self.logger.error(f"GCS authentication/permission error while listing blobs: {e}", exc_info=True)
            return []
        except Exception as e:
            self.logger.error(f"Error listing audio tracks from GCS: {e}", exc_info=True)
            return []

    def generate_signed_url(
        self, blob_name: str, expiration_minutes: int = 60
    ) -> Optional[str]:
        """
        Generates a v4 pre-signed URL for a GCS blob.
        Requires service account with "Service Account Token Creator" role or user credentials.

        Args:
            blob_name: The full path (name) of the blob within the GCS bucket
                       (e.g., "path/to/your/track.mp3").
            expiration_minutes: The duration in minutes for which the generated URL
                                will be valid.

        Returns:
            A v4 pre-signed URL string for GET access to the blob, or None if
            URL generation fails (e.g., blob not found, insufficient permissions for
            the credentials used by the GCS client - typically requires "Service
            Account Token Creator" role if using a service account).
        """
        if not self.storage_client:
            self.logger.error("GCS client not initialized. Cannot generate signed URL.")
            return None
        if not GOOGLE_CLOUD_LIBS_AVAILABLE: # Should be caught by __init__ but double check
            self.logger.error("Google Cloud libraries not available for signed URL generation.")
            return None

        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(blob_name)

            if not blob.exists():
                self.logger.warning(f"Cannot generate signed URL. Blob '{blob_name}' does not exist in bucket '{self.bucket_name}'.")
                return None

            url = blob.generate_signed_url(
                version="v4",
                expiration=time.time() + (expiration_minutes * 60), # Expiration in seconds from now
                method="GET",
            )
            self.logger.info(f"Generated signed URL for '{blob_name}' expiring in {expiration_minutes} minutes.")
            return url
        except google_auth_exceptions.DefaultCredentialsError as e:
             self.logger.error(f"Failed to generate signed URL for '{blob_name}'. ADC missing permissions (e.g., Service Account Token Creator role) or not set up for signing: {e}", exc_info=True)
             return None
        except Exception as e:
            self.logger.error(f"Failed to generate signed URL for '{blob_name}': {e}", exc_info=True)
            return None

    def upload_file(self, local_file_path: str, destination_blob_name: str) -> bool:
        """
        Uploads a local file to the GCS bucket.

        Args:
            local_file_path: Path to the local file to upload.
            destination_blob_name: The name of the blob in GCS (e.g., "path/to/your/file.mp3").

        Returns:
            True if upload was successful, False otherwise.
        """
        if not self.storage_client:
            self.logger.error("GCS client not initialized. Cannot upload file.")
            return False
        if not os.path.exists(local_file_path):
            self.logger.error(f"Local file not found: {local_file_path}")
            return False

        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)

            self.logger.info(f"Uploading local file '{local_file_path}' to 'gs://{self.bucket_name}/{destination_blob_name}'...")
            blob.upload_from_filename(local_file_path)
            self.logger.success(f"Successfully uploaded '{local_file_path}' to 'gs://{self.bucket_name}/{destination_blob_name}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload file '{local_file_path}' to GCS: {e}", exc_info=True)
            return False

    def upload_string_as_blob(self, data_string: str, destination_blob_name: str, content_type: str = 'text/plain') -> bool:
        """
        Uploads a string as a blob to the GCS bucket.

        Args:
            data_string: The string data to upload.
            destination_blob_name: The name of the blob in GCS (e.g., "path/to/your/metadata.json").
            content_type: The content type of the blob (e.g., 'application/json', 'text/plain').

        Returns:
            True if upload was successful, False otherwise.
        """
        if not self.storage_client:
            self.logger.error("GCS client not initialized. Cannot upload string data.")
            return False

        try:
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)

            self.logger.info(f"Uploading string data to 'gs://{self.bucket_name}/{destination_blob_name}' with content type '{content_type}'...")
            blob.upload_from_string(data_string, content_type=content_type)
            self.logger.success(f"Successfully uploaded string data to 'gs://{self.bucket_name}/{destination_blob_name}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload string data to GCS: {e}", exc_info=True)
            return False


# Example Usage
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # --- IMPORTANT ---
    # For this example to run, you need:
    # 1. A GCS bucket.
    # 2. Credentials:
    #    - Either set GOOGLE_APPLICATION_CREDENTIALS environment variable to your service account JSON file.
    #    - Or, provide the path directly to `credentials_path` when creating GCSContentManager.
    #    - The service account needs at least "Storage Object Viewer" role on the bucket.
    #      For `generate_signed_url`, it also needs "Service Account Token Creator" role on itself.
    # 3. Upload some sample audio files (e.g., test.mp3) and corresponding metadata files
    #    (e.g., test.mp3.meta.json) to your bucket.

    # Example metadata file content (e.g., "audio/song1.mp3.meta.json"):
    # {
    #   "content_id": "song001_unique",
    #   "duration_seconds": 180.5,
    #   "content_type": "song",
    #   "title": "My Awesome Song",
    #   "artist": "The Cool Band",
    #   "album": "Greatest Hits",
    #   "genre": "Rock",
    #   "mood_tags": ["upbeat", "energetic"],
    #   "transition_type_in": "fadein",
    #   "transition_duration_in_ms": 1500
    # }

    # --- Configuration ---
    TEST_BUCKET_NAME = os.environ.get("GCS_TEST_BUCKET_NAME") # Set this env var
    TEST_CREDENTIALS_PATH = None # Or set path to your SA key json: "/path/to/your/sa-key.json"

    if not TEST_BUCKET_NAME:
        logger.warning("GCS_TEST_BUCKET_NAME environment variable not set. Skipping GCSContentManager example.")
        sys.exit(0)

    import sys # Ensure sys is imported for exit

    gcs_manager = GCSContentManager(
        bucket_name=TEST_BUCKET_NAME,
        credentials_path=TEST_CREDENTIALS_PATH, # Can be None if using ADC
        logger_instance=logger
    )

    if not gcs_manager.storage_client:
        logger.error("Failed to initialize GCS client in example. Exiting.")
        sys.exit(1)

    logger.info(f"\n--- Listing audio tracks from bucket '{TEST_BUCKET_NAME}' (no prefix, limit 5) ---")
    tracks = gcs_manager.list_audio_tracks(limit=5)
    if tracks:
        for track in tracks:
            logger.info(f"Found track: {track.title} ({track.content_id}) - {track.duration_seconds}s at {track.gcs_path}")
            if track.gcs_path:
                blob_name_for_url = track.gcs_path.replace(f"gs://{TEST_BUCKET_NAME}/", "")
                signed_url = gcs_manager.generate_signed_url(blob_name_for_url, expiration_minutes=5)
                if signed_url:
                    logger.info(f"  Signed URL (5 min): {signed_url}")
                else:
                    logger.warning(f"  Could not generate signed URL for {blob_name_for_url}")
    else:
        logger.info("No audio tracks found or GCS client not initialized.")

    logger.info("\n--- Listing audio tracks with prefix 'audio/' ---")
    # Assuming you have files like 'audio/song1.mp3' and 'audio/song1.mp3.meta.json'
    tracks_with_prefix = gcs_manager.list_audio_tracks(prefix="audio/", limit=2)
    if tracks_with_prefix:
        for track in tracks_with_prefix:
            logger.info(f"Found track with prefix: {track.title} ({track.content_id}) - {track.duration_seconds}s")
    else:
        logger.info("No audio tracks found with prefix 'audio/'.")

    logger.info("\n--- Example finished ---")
```
