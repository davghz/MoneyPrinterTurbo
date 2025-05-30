# Google Cloud Media CDN Live Stream Setup Guide

This guide outlines the presumed manual steps to set up a Live Stream input endpoint using Google Cloud Media CDN. This setup is necessary to obtain the RTMP ingest URL and stream key required by this application to stream video content.

**Note:** This guide is based on general knowledge of Google Cloud services and common live streaming workflows. Specific names for services or UI elements in the Google Cloud Console might vary. Always refer to the [official Google Cloud Media CDN documentation](https://cloud.google.com/media-cdn/docs/live-stream) for the most accurate and up-to-date instructions.

## Prerequisites

1.  A Google Cloud Platform (GCP) project.
2.  Billing enabled for your GCP project.
3.  The necessary IAM permissions to create and manage Media CDN and/or Live Streaming resources. This might include roles like "Media CDN Admin" or "Live Stream API Admin".

## Steps to Create a Live Stream Input Endpoint

It's assumed that Media CDN's live streaming capability involves creating an "Input Endpoint" (sometimes called a "Channel" or "Live Stream" resource in other services) which provides the RTMP/SRT details needed for ingest.

1.  **Navigate to the Live Streaming or Media CDN Service:**
    *   Open the [Google Cloud Console](https://console.cloud.google.com/).
    *   In the navigation menu, look for a service related to "Live Stream", "Media Streaming", or "Media CDN". It might be under "Networking", "Media Services", or its own top-level category.
    *   If a dedicated "Live Stream" API service exists (e.g., "Cloud Video Live Stream API"), that would be the primary place to configure inputs. Media CDN would then typically pull from this live input or an intermediate storage bucket.

2.  **Enable APIs (if not already enabled):**
    *   If you haven't used these services before in your project, you might need to enable the "Live Stream API" (if it exists as a distinct service) and the "Media CDN API".

3.  **Create an Input Endpoint (or Channel/Live Stream):**
    *   Look for an option like "Create Input Endpoint", "Create Channel", or "Create Live Stream".
    *   **Configuration Settings:**
        *   **Name/ID:** Give your input endpoint a descriptive name.
        *   **Region:** Select the Google Cloud region closest to your stream source (where FFmpeg will be running) for optimal ingest performance (e.g., `us-east1`, `europe-west1`).
        *   **Input Protocol:** Choose the ingest protocol. **RTMP** is the most common and widely supported. **SRT** might also be an option for more resilient streaming over lossy networks.
            *   If RTMP is chosen, it might be `RTMP (push)`.
        *   **Source Type:** Select "RTMP_PUSH" or "SRT_PUSH".
        *   **Authentication / Stream Key:**
            *   The system should automatically generate a **Stream Key** (also known as stream name). This key is crucial for authenticating the incoming stream from FFmpeg.
            *   There might be options for IP whitelisting for added security, where you can specify IP ranges allowed to push streams to this endpoint.
        *   **Input Resolution/Bitrate Settings (Optional):** Some platforms allow you to specify expected input parameters, but often the input endpoint is flexible, and transcoding/renditions are configured separately in the CDN or processing steps.
        *   **Latency:** You might find options for "Standard" or "Low Latency".

4.  **Review and Create:**
    *   After configuring all necessary settings, review them and create the input endpoint.

5.  **Obtain Ingest URL and Stream Key:**
    *   Once the input endpoint is created and active/running, its details page should display:
        *   **Ingest URL:** This is the RTMP or SRT server address your FFmpeg will stream to.
            *   For RTMP, it will look something like: `rtmp://<server-address>:<port>/<application-name>/`
            *   (e.g., `rtmp://x.rtmp.l.google.com/live/`)
        *   **Stream Key:** A unique string (e.g., `abcd-1234-efgh-5678`).
    *   **The final RTMP URL for FFmpeg will be a combination of the Ingest URL and the Stream Key**:
        `rtmp://<server-address>:<port>/<application-name>/<stream_key>`
        For example: `rtmp://x.rtmp.l.google.com/live/abcd-1234-efgh-5678`

6.  **Configure Media CDN Service (if separate):**
    *   If Media CDN is configured separately from the live input endpoint:
        *   You would typically create a Media CDN "Service".
        *   Configure an "Origin" for this service, pointing it to the live stream input (or an intermediate source like a Cloud Storage bucket if the live stream writes segments there).
        *   This step provides you with the public-facing CDN URLs for viewers.

## Application Configuration

The application (specifically `FFmpegManager`) will need the following information, which you obtain from the steps above:

*   **`rtmp_url`**: Set this to the "Ingest URL" provided by Google Cloud (e.g., `rtmp://x.rtmp.l.google.com/live/`).
*   **`stream_key`**: Set this to the "Stream Key" provided by Google Cloud.

These values will be configured in the application's `config.toml` or via environment variables, as used by the `StreamConfig` dataclass.

## Programmatic Management (Future Consideration)

Google Cloud typically provides APIs for managing its services. If a "Live Stream API" or a relevant Media CDN API is available, you could potentially automate the creation and management of these input endpoints.

*   **Potential API:** "Google Cloud Video Live Stream API" (look for client libraries like `google-cloud-video-live-stream` for Python).
*   **Resources to manage:** "InputEndpoints", "Channels", "StreamKeys".

Automating this would involve:
1.  Setting up authentication for the API (usually a Service Account with appropriate IAM roles like "Live Stream Admin").
2.  Using the client library to make API calls to create, list, get, or delete input endpoints.

This is a more advanced setup and is not covered by the initial manual configuration described here.
