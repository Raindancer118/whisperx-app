"""Speaker diarization utilities for WhisperX-App.

This module provides helpers for post-processing diarization results,
including segment merging and speaker name resolution.
"""

from __future__ import annotations

from typing import Any

# Maximum time gap (in seconds) between consecutive segments from the same
# speaker before they are considered separate paragraphs in Markdown output.
SPEAKER_MERGE_GAP_SECONDS = 1.5


def merge_consecutive_segments(
    segments: list[dict[str, Any]],
    gap_threshold: float = SPEAKER_MERGE_GAP_SECONDS,
) -> list[dict[str, Any]]:
    """Merge consecutive segments from the same speaker if the gap is small.

    This reduces fragmentation in the output — short pauses within a single
    speaker's turn are joined into one block rather than creating separate entries.

    Args:
        segments: List of WhisperX segment dicts (must have 'speaker', 'start', 'end', 'text')
        gap_threshold: Max gap in seconds to merge (default 1.5s)

    Returns:
        New list of merged segment dicts
    """
    if not segments:
        return []

    merged: list[dict[str, Any]] = []
    current = dict(segments[0])

    for seg in segments[1:]:
        same_speaker = seg.get("speaker") == current.get("speaker")
        small_gap = (seg["start"] - current["end"]) <= gap_threshold

        if same_speaker and small_gap:
            current["end"] = seg["end"]
            current["text"] = current["text"].rstrip() + " " + seg["text"].lstrip()
        else:
            merged.append(current)
            current = dict(seg)

    merged.append(current)
    return merged


def resolve_speaker_name(speaker_label: str, name_map: dict[str, str]) -> str:
    """Translate a raw speaker label (e.g. 'SPEAKER_00') to a display name.

    Falls back to the original label if no mapping is defined.
    """
    return name_map.get(speaker_label, speaker_label)
