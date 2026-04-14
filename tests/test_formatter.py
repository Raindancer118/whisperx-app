"""Tests for formatter.py and diarizer.py — output formatting and segment merging."""

import json
from pathlib import Path

import pytest

from whisperx_app.diarizer import merge_consecutive_segments, resolve_speaker_name
from whisperx_app.formatter import _format_timestamp, format_result


# ---------------------------------------------------------------------------
# _format_timestamp
# ---------------------------------------------------------------------------

def test_format_timestamp_zero():
    assert _format_timestamp(0) == "00:00:00"


def test_format_timestamp_minutes():
    assert _format_timestamp(125) == "00:02:05"


def test_format_timestamp_hours():
    assert _format_timestamp(3661) == "01:01:01"


def test_format_timestamp_negative_clamps():
    assert _format_timestamp(-5) == "00:00:00"


# ---------------------------------------------------------------------------
# resolve_speaker_name
# ---------------------------------------------------------------------------

def test_resolve_known_speaker():
    assert resolve_speaker_name("SPEAKER_00", {"SPEAKER_00": "Tom"}) == "Tom"


def test_resolve_unknown_speaker_returns_label():
    assert resolve_speaker_name("SPEAKER_02", {"SPEAKER_00": "Tom"}) == "SPEAKER_02"


def test_resolve_empty_map():
    assert resolve_speaker_name("SPEAKER_00", {}) == "SPEAKER_00"


# ---------------------------------------------------------------------------
# merge_consecutive_segments
# ---------------------------------------------------------------------------

def test_merge_empty_segments():
    assert merge_consecutive_segments([]) == []


def test_merge_single_segment():
    segs = [{"start": 0.0, "end": 3.0, "text": "Hallo.", "speaker": "SPEAKER_00"}]
    result = merge_consecutive_segments(segs)
    assert len(result) == 1
    assert result[0]["text"] == "Hallo."


def test_merge_consecutive_same_speaker_small_gap():
    segs = [
        {"start": 0.0, "end": 3.0, "text": "Hallo,", "speaker": "SPEAKER_00"},
        {"start": 3.5, "end": 6.0, "text": "wie geht es?", "speaker": "SPEAKER_00"},
    ]
    merged = merge_consecutive_segments(segs, gap_threshold=1.5)
    assert len(merged) == 1
    assert "Hallo," in merged[0]["text"]
    assert "wie geht es?" in merged[0]["text"]
    assert merged[0]["end"] == 6.0


def test_no_merge_different_speaker():
    segs = [
        {"start": 0.0, "end": 3.0, "text": "Hallo.", "speaker": "SPEAKER_00"},
        {"start": 3.2, "end": 6.0, "text": "Hi!", "speaker": "SPEAKER_01"},
    ]
    merged = merge_consecutive_segments(segs)
    assert len(merged) == 2


def test_no_merge_large_gap_same_speaker():
    segs = [
        {"start": 0.0, "end": 3.0, "text": "Erster Teil.", "speaker": "SPEAKER_00"},
        {"start": 10.0, "end": 13.0, "text": "Zweiter Teil.", "speaker": "SPEAKER_00"},
    ]
    merged = merge_consecutive_segments(segs, gap_threshold=1.5)
    assert len(merged) == 2


# ---------------------------------------------------------------------------
# format_result — TXT
# ---------------------------------------------------------------------------

def test_format_txt_with_speaker(sample_segments):
    result = {"segments": sample_segments, "language": "de"}
    output = format_result(result, "txt")
    assert "SPEAKER_00" in output
    assert "Hallo" in output
    assert "[00:00:04]" in output


def test_format_txt_with_name_map(sample_segments):
    result = {"segments": sample_segments}
    output = format_result(result, "txt", speaker_names={"SPEAKER_00": "Tom", "SPEAKER_01": "Anna"})
    assert "Tom:" in output
    assert "Anna:" in output
    assert "SPEAKER_00" not in output


def test_format_txt_no_speaker():
    result = {"segments": [{"start": 0.0, "end": 5.0, "text": "Kein Sprecher."}]}
    output = format_result(result, "txt")
    assert "Kein Sprecher." in output
    assert "[00:00:00]" in output


# ---------------------------------------------------------------------------
# format_result — JSON
# ---------------------------------------------------------------------------

def test_format_json_is_valid(sample_whisperx_result):
    output = format_result(sample_whisperx_result, "json")
    parsed = json.loads(output)
    assert "segments" in parsed
    assert "metadata" in parsed


def test_format_json_metadata_fields(sample_whisperx_result):
    output = format_result(
        sample_whisperx_result, "json",
        source_file=Path("audio.mp3"),
        model_name="large-v3",
    )
    parsed = json.loads(output)
    assert parsed["metadata"]["model"] == "large-v3"
    assert parsed["metadata"]["source_file"] == "audio.mp3"
    assert "generated_at" in parsed["metadata"]
    assert "whisperx_app_version" in parsed["metadata"]


# ---------------------------------------------------------------------------
# format_result — Markdown
# ---------------------------------------------------------------------------

def test_format_markdown_has_header(sample_segments):
    result = {"segments": sample_segments}
    output = format_result(result, "md", source_file=Path("interview.mp3"), model_name="large-v3")
    assert "# Transkription: interview.mp3" in output
    assert "large-v3" in output


def test_format_markdown_bold_speaker(sample_segments):
    result = {"segments": sample_segments}
    output = format_result(result, "md", speaker_names={"SPEAKER_00": "Tom", "SPEAKER_01": "Anna"})
    assert "**Tom**" in output
    assert "**Anna**" in output


def test_format_markdown_no_speaker_in_raw_label(sample_segments):
    result = {"segments": sample_segments}
    output = format_result(result, "md")
    # Raw labels should still be bold
    assert "**SPEAKER_00**" in output or "**SPEAKER_01**" in output


def test_format_markdown_has_footer(sample_segments):
    result = {"segments": sample_segments}
    output = format_result(result, "md")
    assert "WhisperX-App" in output


def test_format_markdown_merges_segments():
    segs = [
        {"start": 0.0, "end": 3.0, "text": " Teil eins.", "speaker": "SPEAKER_00"},
        {"start": 3.2, "end": 6.0, "text": " Teil zwei.", "speaker": "SPEAKER_00"},
    ]
    result = {"segments": segs}
    output = format_result(result, "md")
    # Both parts should appear in a single speaker block
    assert "Teil eins." in output
    assert "Teil zwei." in output
    # Should appear only once as a speaker header
    assert output.count("**SPEAKER_00**") == 1


# ---------------------------------------------------------------------------
# format_result — Invalid format
# ---------------------------------------------------------------------------

def test_format_result_raises_on_unknown_format(sample_segments):
    result = {"segments": sample_segments}
    with pytest.raises(ValueError, match="Unbekanntes Format"):
        format_result(result, "xml")
