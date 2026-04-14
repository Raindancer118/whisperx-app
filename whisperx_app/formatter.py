"""Output formatters for WhisperX transcription results.

Supported formats:
  - txt:  Plain text with timestamps and speaker labels
  - json: WhisperX result dict + metadata (pretty-printed)
  - md:   Markdown with bold speaker names, grouped by speaker turn
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from whisperx_app.diarizer import merge_consecutive_segments, resolve_speaker_name
from whisperx_app import __version__


def format_result(
    result: dict[str, Any],
    fmt: str,
    source_file: Optional[Path] = None,
    model_name: str = "large-v3",
    speaker_names: Optional[dict[str, str]] = None,
) -> str:
    """Format a WhisperX result dict into the requested output format.

    Args:
        result: WhisperX transcription result (dict with 'segments' key)
        fmt: One of "txt", "json", "md"
        source_file: Original audio file path (used in headers/metadata)
        model_name: Model identifier for metadata
        speaker_names: Optional mapping {"SPEAKER_00": "Tom", ...}

    Returns:
        Formatted string ready for display or file writing
    """
    names = speaker_names or {}
    segments = result.get("segments", [])

    if fmt == "txt":
        return _format_txt(segments, names)
    elif fmt == "json":
        return _format_json(result, source_file, model_name)
    elif fmt == "md":
        return _format_markdown(segments, names, source_file, model_name)
    else:
        raise ValueError(f"Unbekanntes Format: {fmt!r}. Erlaubt: txt, json, md")


# ---------------------------------------------------------------------------
# TXT
# ---------------------------------------------------------------------------

def _format_txt(segments: list[dict[str, Any]], name_map: dict[str, str]) -> str:
    lines: list[str] = []
    for seg in segments:
        ts = _format_timestamp(seg.get("start", 0))
        speaker = resolve_speaker_name(seg.get("speaker", ""), name_map)
        text = seg.get("text", "").strip()
        if speaker:
            lines.append(f"[{ts}] {speaker}: {text}")
        else:
            lines.append(f"[{ts}] {text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _format_json(
    result: dict[str, Any],
    source_file: Optional[Path],
    model_name: str,
) -> str:
    output = dict(result)
    output["metadata"] = {
        "source_file": str(source_file) if source_file else None,
        "model": model_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "whisperx_app_version": __version__,
    }
    return json.dumps(output, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _format_markdown(
    segments: list[dict[str, Any]],
    name_map: dict[str, str],
    source_file: Optional[Path],
    model_name: str,
) -> str:
    merged = merge_consecutive_segments(segments)
    lines: list[str] = []

    # Header
    filename = source_file.name if source_file else "Transkription"
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines.append(f"# Transkription: {filename}")
    lines.append("")
    lines.append(f"**Erstellt:** {date_str} · **Modell:** {model_name}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for seg in merged:
        speaker_label = seg.get("speaker", "")
        speaker_display = resolve_speaker_name(speaker_label, name_map) if speaker_label else None
        ts = _format_timestamp(seg.get("start", 0))
        text = seg.get("text", "").strip()

        if speaker_display:
            lines.append(f"**{speaker_display}** — {ts}")
        else:
            lines.append(f"*{ts}*")
        lines.append(text)
        lines.append("")

    lines.append("---")
    lines.append(f"*Generiert mit WhisperX-App {__version__}*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_timestamp(seconds: float) -> str:
    """Convert float seconds to HH:MM:SS string."""
    total = max(0, int(seconds))
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
