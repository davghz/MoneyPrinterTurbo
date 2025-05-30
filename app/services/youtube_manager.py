"""
Manages interactions with the YouTube Data API v3, focusing on live streaming capabilities.

Handles authentication (Service Account, API Key, OAuth 2.0) and provides methods
to query live stream status.
"""
import os
from typing import Optional, Dict, Any, List

from loguru import logger

try:
    import google.oauth2.credentials
    import google.oauth2.service_account
    import google_auth_oauthlib.flow
    from googleapiclient.discovery import build as build_google_api_service
    from googleapiclient.errors import HttpError
    GOOGLE_API_LIBS_AVAILABLE = True
except ImportError:
    logger.error(
        "Google API client libraries not found. YouTubeManager will not function. "
        "Please install: google-api-python-client google-auth-oauthlib google-auth-httplib2"
    )
    GOOGLE_API_LIBS_AVAILABLE = False

# Define scopes - adjust as needed
YOUTUBE_READONLY_SCOPE = ["https://www.googleapis.com/auth/youtube.readonly"]
YOUTUBE_FULL_SCOPE = ["https://www.googleapis.com/auth/youtube"]


class YouTubeManager:
    """
    Manages interactions with the YouTube Data API v3.

    Handles authentication and provides methods to query live stream status.
    Authentication priority:
    1. Service Account (via GOOGLE_APPLICATION_CREDENTIALS or configured path).
    2. OAuth 2.0 (if client_secrets_file and credentials_file are provided).
    3. API Key (for limited, read-only access).
    """

    def __init__(
        self,
        client_secrets_file: Optional[str] = None,
        credentials_file: Optional[str] = None,
        api_key: Optional[str] = None,
        service_account_json_path: Optional[str] = None,
        logger_instance=None,
    ):
        """
        Initializes the YouTubeManager.

        Args:
            client_secrets_file (Optional[str]): Path to client_secret.json for OAuth 2.0.
            credentials_file (Optional[str]): Path to store/load OAuth 2.0 user credentials.
            api_key (Optional[str]): YouTube Data API v3 key.
            service_account_json_path (Optional[str]): Explicit path to a service account JSON key file.
            logger_instance (Optional): A Loguru logger instance. If None, a default one is used.
        """
        self.logger = logger_instance or logger.bind(name=self.__class__.__name__)
        if not GOOGLE_API_LIBS_AVAILABLE:
            self.youtube_service = None
            self.logger.critical("YouTubeManager cannot operate: Google API client libraries are not installed.")
            return

        self.client_secrets_file = client_secrets_file
        self.credentials_file = credentials_file
        self.api_key = api_key
        self.service_account_json_path = service_account_json_path # Store this
        self.youtube_service = self._get_authenticated_service()

    def _get_authenticated_service(self) -> Optional[Any]:
        """
        Authenticates and builds the YouTube Data API v3 service object.
        Priority:
        1. Explicit Service Account path from constructor.
        2. GOOGLE_APPLICATION_CREDENTIALS environment variable (Service Account).
        3. OAuth 2.0 credentials from constructor paths.
        4. API Key from constructor.

        Returns:
            An authenticated YouTube API service object, or None if authentication fails.
        """
        credentials = None

        # Priority 1: Explicit Service Account path from constructor
        if self.service_account_json_path:
            try:
                credentials = google.oauth2.service_account.Credentials.from_service_account_file(
                    self.service_account_json_path, scopes=YOUTUBE_FULL_SCOPE
                )
                self.logger.info(f"Authenticated using explicit Service Account JSON path: {self.service_account_json_path}")
            except FileNotFoundError:
                self.logger.error(f"Service Account JSON file not found at explicit path: {self.service_account_json_path}. Trying other methods.")
            except Exception as e:
                self.logger.warning(f"Failed to load Service Account credentials from explicit path {self.service_account_json_path}: {e}. Trying other methods.")

        # Priority 2: GOOGLE_APPLICATION_CREDENTIALS environment variable (Service Account)
        if not credentials:
            env_service_account_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if env_service_account_path:
                try:
                    credentials = google.oauth2.service_account.Credentials.from_service_account_file(
                        env_service_account_path, scopes=YOUTUBE_FULL_SCOPE
                    )
                    self.logger.info(f"Authenticated using Service Account from GOOGLE_APPLICATION_CREDENTIALS: {env_service_account_path}")
                except FileNotFoundError:
                    self.logger.error(f"Service Account JSON file not found at GOOGLE_APPLICATION_CREDENTIALS path: {env_service_account_path}. Trying other methods.")
                except Exception as e:
                    self.logger.warning(f"Failed to load Service Account credentials from GOOGLE_APPLICATION_CREDENTIALS ({env_service_account_path}): {e}. Trying other methods.")

        # Priority 3: OAuth 2.0 credentials from constructor paths
        if not credentials and self.client_secrets_file: # client_secrets_file is mandatory for OAuth flow
            try:
                if self.credentials_file and os.path.exists(self.credentials_file):
                    credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(
                        self.credentials_file, YOUTUBE_FULL_SCOPE
                    )
                    self.logger.debug(f"Loaded OAuth 2.0 credentials from: {self.credentials_file}")

                if not credentials or not credentials.valid:
                    if credentials and credentials.expired and credentials.refresh_token:
                        self.logger.info("OAuth 2.0 credentials expired, attempting refresh.")
                        try:
                            import google.auth.transport.requests
                            request_obj = google.auth.transport.requests.Request()
                            credentials.refresh(request_obj)
                            self.logger.info("OAuth 2.0 credentials refreshed successfully.")
                        except google.auth.exceptions.RefreshError as e_refresh:
                            self.logger.error(f"Failed to refresh OAuth 2.0 token: {e_refresh}. Re-running interactive flow if possible.")
                            credentials = None # Force re-flow if refresh fails
                        except Exception as e_generic_refresh:
                            self.logger.error(f"Unexpected error during OAuth 2.0 token refresh: {e_generic_refresh}. Re-running interactive flow if possible.")
                            credentials = None

                    if not credentials: # If still no valid credentials, try the interactive flow
                        self.logger.info(f"Performing OAuth 2.0 interactive flow using client secrets: {self.client_secrets_file}.")
                        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                            self.client_secrets_file, YOUTUBE_FULL_SCOPE
                        )
                        # This is interactive. For servers, pre-authorize and store credentials_file.
                        # Consider adding a timeout or specific instructions for headless environments.
                        credentials = flow.run_local_server(port=0)

                    if self.credentials_file: # Save/update credentials if a path is provided
                        with open(self.credentials_file, "w") as f:
                            f.write(credentials.to_json())
                        self.logger.info(f"OAuth 2.0 credentials stored/updated at: {self.credentials_file}")
                if credentials:
                     self.logger.info(f"Authenticated using OAuth 2.0 credentials.")

            except FileNotFoundError:
                self.logger.error(f"OAuth client_secret.json not found at: {self.client_secrets_file}")
            except Exception as e:
                self.logger.error(f"OAuth 2.0 authentication failed: {e}", exc_info=True)

        # Build service with credentials if obtained
        if credentials:
            try:
                return build_google_api_service("youtube", "v3", credentials=credentials)
            except Exception as e: # Catch errors during service build
                self.logger.error(f"Failed to build YouTube service with obtained credentials: {e}", exc_info=True)
                # Fall through to try API key if building with credentials failed

        # Priority 4: API Key from constructor
        if self.api_key:
            try:
                self.logger.info("Attempting authentication using API Key.")
                return build_google_api_service("youtube", "v3", developerKey=self.api_key)
            except Exception as e:
                self.logger.error(f"Failed to build YouTube service with API Key: {e}", exc_info=True)
                return None

        if not credentials and not self.api_key: # If no credentials and no API key was provided or all attempts failed
            self.logger.error("No valid authentication method provided or all authentication attempts failed.")
        elif not credentials and self.api_key: # If API key was provided but service build failed above
             self.logger.error("API key was provided but failed to build service. No other auth methods succeeded.")
        return None

    def get_live_stream_status(self, stream_id: str) -> Dict[str, Any]:
        """
        Retrieves the status of a specific YouTube live stream.

        Args:
            stream_id: The ID of the YouTube liveStream resource.

        Returns:
            A dictionary with status information, e.g.,
            {'raw_status': 'active', 'health': 'good', 'is_live': True}.
            Returns a default error status if the API call fails or stream not found.
        """
        if not self.youtube_service:
            self.logger.error("YouTube service not authenticated. Cannot get stream status.")
            return {"raw_status": "error", "health": "unknown", "is_live": False, "error": "Not authenticated"}

        try:
            request = self.youtube_service.liveStreams().list(
                part="id,snippet,status,cdn",
                id=stream_id
            )
            response = request.execute()

            if not response.get("items"):
                self.logger.warning(f"Live stream with ID '{stream_id}' not found.")
                return {"raw_status": "not_found", "health": "unknown", "is_live": False, "error": "Stream not found"}

            stream_item = response["items"][0]
            stream_status = stream_item.get("status", {}).get("streamStatus")
            health_status = stream_item.get("status", {}).get("healthStatus", {}).get("status") # Health status is nested

            is_live = stream_status == "active"

            status_info = {
                "raw_status": stream_status,
                "health": health_status,
                "is_live": is_live,
                "title": stream_item.get("snippet", {}).get("title"),
                "ingestion_address": stream_item.get("cdn",{}).get("ingestionInfo",{}).get("ingestionAddress"),
                "frame_rate": stream_item.get("cdn",{}).get("frameRate"),
                "resolution": stream_item.get("cdn",{}).get("resolution"),
            }
            self.logger.info(f"Status for stream '{stream_id}': {status_info}")
            return status_info

        except HttpError as e:
            self.logger.error(f"YouTube API HttpError getting status for stream '{stream_id}': {e.resp.status} {e._get_reason()}")
            return {"raw_status": "error", "health": "unknown", "is_live": False, "error": f"API Error: {e._get_reason()}"}
        except Exception as e:
            self.logger.error(f"Unexpected error getting status for stream '{stream_id}': {e}", exc_info=True)
            return {"raw_status": "error", "health": "unknown", "is_live": False, "error": str(e)}

    def verify_stream_key(self, stream_key: str, expected_rtmp_url: Optional[str] = None) -> bool:
        """
        Verifies a stream key by checking against the authenticated user's live streams.
        This requires OAuth 2.0 or Service Account authentication with appropriate scopes.
        API Key authentication is not sufficient for this operation.

        Args:
            stream_key: The stream key (stream name) to verify.
            expected_rtmp_url (Optional[str]): If provided, also verifies the RTMP ingestion address.

        Returns:
            True if a matching stream is found, False otherwise.

        Raises:
            NotImplementedError: If authenticated with only an API Key.
        """
        if not self.youtube_service:
            self.logger.error("YouTube service not authenticated.")
            return False

        if self.api_key and not (hasattr(self.youtube_service, '_http') and hasattr(self.youtube_service._http, 'credentials')): # Heuristic to check if not API key auth
             self.logger.warning("Verifying stream key requires OAuth 2.0 or Service Account. API Key auth is insufficient.")
             raise NotImplementedError("Stream key verification is not supported with API Key authentication.")

        try:
            request = self.youtube_service.liveStreams().list(
                part="id,snippet,cdn,status",
                mine=True # Requires OAuth2 or Service Account with youtube scope
            )
            response = request.execute()

            for item in response.get("items", []):
                stream_name = item.get("cdn", {}).get("ingestionInfo", {}).get("streamName")
                if stream_name == stream_key:
                    self.logger.info(f"Found matching stream key for ID: {item.get('id')}, Title: {item.get('snippet',{}).get('title')}")
                    if expected_rtmp_url:
                        ingestion_address = item.get("cdn", {}).get("ingestionInfo", {}).get("ingestionAddress")
                        if ingestion_address == expected_rtmp_url:
                            self.logger.info(f"RTMP URL matches: {ingestion_address}")
                            return True
                        else:
                            self.logger.warning(f"Stream key '{stream_key}' found, but RTMP URL mismatch. Expected '{expected_rtmp_url}', got '{ingestion_address}'")
                            return False
                    return True

            self.logger.warning(f"No live stream found matching stream key: {stream_key}")
            return False

        except HttpError as e:
            self.logger.error(f"YouTube API HttpError during stream key verification: {e.resp.status} {e._get_reason()}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during stream key verification: {e}", exc_info=True)
            return False

# Example usage:
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    # To test, you might need to:
    # 1. Set GOOGLE_APPLICATION_CREDENTIALS environment variable to your service account JSON path.
    # OR
    # 2. Provide an API_KEY (limited functionality).
    # OR
    # 3. Have client_secret.json and a pre-authorized credentials.json for OAuth.

    # Test with API Key (replace with your actual API key)
    # api_key_test = "YOUR_API_KEY"
    # if api_key_test == "YOUR_API_KEY":
    #     logger.warning("API Key not set for __main__ test. Skipping API key test.")
    # else:
    #     logger.info("Testing with API Key...")
    #     yt_manager_api = YouTubeManager(api_key=api_key_test)
    #     if yt_manager_api.youtube_service:
    #         # Example: Search for public videos (API key is usually fine for this)
    #         try:
    #             search_request = yt_manager_api.youtube_service.search().list(
    #                 part="snippet", q="Google", type="video", maxResults=2
    #             )
    #             search_response = search_request.execute()
    #             logger.info(f"API Key Test - Search results: {search_response.get('items')}")
    #         except HttpError as e:
    #             logger.error(f"API Key Test - Search failed: {e}")
    #     else:
    #         logger.error("API Key Test - Failed to initialize YouTube service.")


    # Test with Service Account (ensure GOOGLE_APPLICATION_CREDENTIALS is set)
    logger.info("\nTesting with Service Account (if GOOGLE_APPLICATION_CREDENTIALS is set)...")
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if sa_path and os.path.exists(sa_path):
        yt_manager_sa = YouTubeManager() # Relies on env var
        if yt_manager_sa.youtube_service:
            # Replace with a known liveStream ID from your account for testing get_live_stream_status
            test_stream_id = "YOUR_ACTUAL_LIVESTREAM_ID" # IMPORTANT: Replace this
            if test_stream_id == "YOUR_ACTUAL_LIVESTREAM_ID":
                 logger.warning("Service Account Test - Test liveStream ID not set. Skipping get_live_stream_status.")
            else:
                status = yt_manager_sa.get_live_stream_status(test_stream_id)
                logger.info(f"Service Account Test - Stream status for '{test_stream_id}': {status}")

            # Test verify_stream_key (replace with a key from your account)
            # test_stream_key_to_verify = "YOUR_STREAM_KEY"
            # if test_stream_key_to_verify == "YOUR_STREAM_KEY":
            #    logger.warning("Service Account Test - Test stream key not set. Skipping verify_stream_key.")
            # else:
            #    key_valid = yt_manager_sa.verify_stream_key(test_stream_key_to_verify)
            #    logger.info(f"Service Account Test - Stream key '{test_stream_key_to_verify}' valid: {key_valid}")
        else:
            logger.error("Service Account Test - Failed to initialize YouTube service.")
    else:
        logger.warning("Service Account Test - GOOGLE_APPLICATION_CREDENTIALS not set or path invalid. Skipping.")

    # OAuth 2.0 flow test (requires client_secret.json and interactive auth first time)
    # logger.info("\nTesting with OAuth 2.0 (if client_secrets.json exists)...")
    # client_secrets_path = "client_secret.json" # Path to your client_secret.json
    # credentials_store_path = "youtube_credentials.json"
    # if os.path.exists(client_secrets_path):
    #     yt_manager_oauth = YouTubeManager(client_secrets_file=client_secrets_path, credentials_file=credentials_store_path)
    #     if yt_manager_oauth.youtube_service:
    #         logger.info("OAuth Test - Successfully initialized YouTube service.")
    #         # Example: List user's broadcasts (if scopes allow)
    #         try:
    #             broadcast_request = yt_manager_oauth.youtube_service.liveBroadcasts().list(
    #                 part="id,snippet", mine=True, maxResults=1
    #             )
    #             broadcast_response = broadcast_request.execute()
    #             logger.info(f"OAuth Test - User's broadcasts: {broadcast_response.get('items')}")
    #         except HttpError as e:
    #             logger.error(f"OAuth Test - Failed to list broadcasts: {e}")
    #     else:
    #         logger.error("OAuth Test - Failed to initialize YouTube service.")
    # else:
    #     logger.warning(f"OAuth Test - {client_secrets_path} not found. Skipping OAuth 2.0 test.")

    logger.info("YouTubeManager tests finished.")
```
