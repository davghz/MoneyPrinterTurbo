# Playlist Transition Strategy

This document outlines the conceptual strategy for handling audio transitions between `PlaylistItem` entries within a playlist. The actual execution of these transitions is the responsibility of the playback or streaming engine (e.g., an FFmpeg-based component or a future dedicated audio streaming service like "HarmoniStream AI"). The playlist models provide the *intent* for how tracks should transition into one another.

## Relevant `PlaylistItem` Attributes

Each `PlaylistItem` in `app/services/playlist/models.py` has the following attributes relevant to transitions:

*   **`transition_type_in: str`**
    *   Specifies the type of transition to be applied at the *beginning* of this playlist item.
    *   The transition effectively occurs between the *end* of the previous item and the *start* of this item.
    *   Default value: `"crossfade"`

*   **`transition_duration_in_ms: int`**
    *   Specifies the duration (in milliseconds) for the `transition_type_in`.
    *   Default value: `3000` (3 seconds)

## Defined Transition Types

The following values are conceptually defined for `transition_type_in`:

1.  **`"none"`**:
    *   No specific audio transition effect is applied.
    *   The previous track is expected to play to its natural end (or defined out-point).
    *   The current track starts immediately after the previous track concludes.
    *   `transition_duration_in_ms` is typically ignored for this type but could represent a forced silence gap if the playback engine supports it.

2.  **`"crossfade"`**:
    *   The end of the previous track overlaps with the beginning of the current track.
    *   During this overlap, the previous track fades out while the current track fades in simultaneously.
    *   The total duration of this overlap and fading process is defined by `transition_duration_in_ms`.
    *   For example, if `transition_duration_in_ms` is 3000ms:
        *   The last 3000ms of the previous track will be fading out.
        *   The first 3000ms of the current track will be fading in.
        *   The total time where both tracks might be audible (overlapping) is 3000ms.
    *   The fade curves should ideally be smooth (e.g., logarithmic/equal power for audio to avoid perceived loudness dips, though linear is simpler to implement).

3.  **`"fadein"`**:
    *   The current track starts from silence and gradually increases to its normal volume over the period specified by `transition_duration_in_ms`.
    *   This type implies that the previous track has already finished or faded out completely before this track begins its fade-in. There's typically no overlap.
    *   If the previous track had a `transition_type_in` like `"fadeout"` (conceptual, as we define transitions *into* an item), this would create a fade-out -> silence -> fade-in sequence.

4.  **`"fadeout_in"` (Conceptual / More Explicit Alternative)**:
    *   This is a more explicit way to define a sequence where the previous track is intended to fade out completely, potentially followed by a brief moment of silence (or not), and then the current track fades in.
    *   The `transition_duration_in_ms` could be interpreted as applying to both the fade-out of the previous item and the fade-in of the current item, or it could be split/defined more granularly with additional fields if needed (e.g., `transition_duration_out_ms` on the *previous* item).
    *   **For the current simplicity, we will primarily focus on `"none"`, `"crossfade"`, and `"fadein"`.** The effect of a "fadeout" on the *previous* track is implicitly determined by the `transition_type_in` of the *current* track. For instance, a `crossfade` inherently includes a fade-out of the previous track.

## How Transitions are Determined

*   The transition *out* of `Track A` and *into* `Track B` is determined by `Track B.transition_type_in` and `Track B.transition_duration_in_ms`.
*   The very first track in a playlist might have its `transition_type_in` applied as a fade-in from silence, or it might start abruptly if `"none"`, depending on the playback engine's interpretation.

## Responsibility of the Playback Engine

It is crucial to understand that the `Playlist` and `PlaylistItem` models only define the *desired* transition behavior. The actual audio processing, mixing, fading, and timing adjustments are the responsibility of the playback/streaming engine.

This engine (e.g., an FFmpeg pipeline, or a future dedicated audio service) will need to:
1.  Read the `PlaylistItem` attributes.
2.  Adjust the start/end times of audio segments for overlap if `crossfade` is specified.
3.  Apply volume fades (e.g., using FFmpeg's `afade` filter) according to the `transition_type_in` and `transition_duration_in_ms`.
4.  Concatenate or mix the audio segments to produce the final continuous audio stream.

## Example Scenarios

Let's consider `Track A` followed by `Track B`.

1.  **Track B: `transition_type_in="none"`**
    *   Track A plays to its full duration.
    *   Track B starts immediately after Track A ends.
    *   No overlap, no fade.

2.  **Track B: `transition_type_in="crossfade"`, `transition_duration_in_ms=3000`**
    *   The playback engine will start fading out Track A 3000ms before its actual end.
    *   Simultaneously, Track B will start playing and fade in over its first 3000ms.
    *   The effective start time of Track B from the perspective of the overall playlist timeline is 3000ms *before* Track A would have naturally ended.
    *   Total duration of the two tracks in sequence is reduced by `transition_duration_in_ms` due to the overlap.

3.  **Track B: `transition_type_in="fadein"`, `transition_duration_in_ms=2000`**
    *   Track A plays to its full duration (potentially with its own fade-out if the *next* track, Track C, specified a crossfade with Track B).
    *   Track B starts after Track A, fading in from silence to full volume over 2000ms.
    *   No overlap between Track A and Track B.

## Default Behavior

As defined in `PlaylistItem`:
*   Default `transition_type_in` is `"crossfade"`.
*   Default `transition_duration_in_ms` is `3000`.

This means if these fields are not explicitly set when a `PlaylistItem` is created, a 3-second crossfade will be the intended transition into that item from the previous one. For the very first item in a playlist, a playback engine might interpret a "crossfade" default as a "fadein" over the specified duration.

## Future Considerations

*   More complex transition types (e.g., beat-matched transitions, specific EQ fades).
*   Separate `transition_type_out` and `transition_duration_out_ms` fields on `PlaylistItem` for more explicit control over how a track ends, independent of the next track's fade-in.
*   Playback engine capabilities to dynamically adjust transition points based on audio analysis (e.g., silence detection, beat matching).
