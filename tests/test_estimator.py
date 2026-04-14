"""Tests for estimator.py — audio duration parsing and processing time estimates."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from whisperx_app.estimator import (
    _lookup_gpu_rtf,
    estimate_processing_time,
    format_duration,
    get_audio_duration,
)


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------

def test_format_duration_seconds_only():
    assert format_duration(45) == "45s"


def test_format_duration_minutes_and_seconds():
    assert format_duration(125) == "2m 05s"


def test_format_duration_hours():
    assert format_duration(3661) == "1h 01m 01s"


def test_format_duration_zero():
    assert format_duration(0) == "0s"


def test_format_duration_negative_clamps_to_zero():
    assert format_duration(-10) == "0s"


# ---------------------------------------------------------------------------
# _lookup_gpu_rtf
# ---------------------------------------------------------------------------

def test_lookup_gpu_rtf_known_model():
    rtf = _lookup_gpu_rtf("NVIDIA GeForce RTX 3090")
    assert rtf == pytest.approx(0.18)


def test_lookup_gpu_rtf_a100():
    rtf = _lookup_gpu_rtf("NVIDIA A100-SXM4-80GB")
    assert rtf == pytest.approx(0.08)


def test_lookup_gpu_rtf_unknown_falls_back_to_generic():
    rtf = _lookup_gpu_rtf("NVIDIA Quadro K420")
    assert rtf == pytest.approx(0.35)


def test_lookup_gpu_rtf_none_returns_generic():
    rtf = _lookup_gpu_rtf(None)
    assert rtf == pytest.approx(0.35)


# ---------------------------------------------------------------------------
# estimate_processing_time
# ---------------------------------------------------------------------------

def test_estimate_cpu_large_v3():
    # 60s audio, CPU, large-v3, no diarize
    est = estimate_processing_time(60.0, "cpu", "large-v3", diarize=False)
    assert est == pytest.approx(60.0 * 3.5)


def test_estimate_cpu_with_diarization_overhead():
    est_no_dia = estimate_processing_time(60.0, "cpu", "large-v3", diarize=False)
    est_dia = estimate_processing_time(60.0, "cpu", "large-v3", diarize=True)
    assert est_dia > est_no_dia
    assert est_dia == pytest.approx(est_no_dia * 1.15)


def test_estimate_gpu_rtx3090():
    est = estimate_processing_time(300.0, "cuda", "large-v3", gpu_device_name="RTX 3090", diarize=False)
    assert est == pytest.approx(300.0 * 0.18)


def test_estimate_gpu_generic():
    est = estimate_processing_time(300.0, "cuda", "large-v3", diarize=False)
    assert est == pytest.approx(300.0 * 0.35)


def test_estimate_unknown_model_falls_back_to_large_v3():
    est = estimate_processing_time(60.0, "cpu", "unknown-model", diarize=False)
    assert est == pytest.approx(60.0 * 3.5)


# ---------------------------------------------------------------------------
# get_audio_duration
# ---------------------------------------------------------------------------

FFPROBE_STREAMS_OUTPUT = json.dumps({
    "streams": [{"codec_type": "audio", "duration": "123.456"}]
})

FFPROBE_FORMAT_OUTPUT = json.dumps({
    "format": {"duration": "99.0"}
})


def test_get_audio_duration_from_streams(tmp_path):
    dummy = tmp_path / "audio.mp3"
    dummy.write_bytes(b"")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=FFPROBE_STREAMS_OUTPUT
        )
        duration = get_audio_duration(dummy)
    assert duration == pytest.approx(123.456)


def test_get_audio_duration_fallback_to_format(tmp_path):
    dummy = tmp_path / "audio.mp3"
    dummy.write_bytes(b"")
    no_stream = json.dumps({"streams": [{"codec_type": "audio"}]})
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=no_stream),
            MagicMock(returncode=0, stdout=FFPROBE_FORMAT_OUTPUT),
        ]
        duration = get_audio_duration(dummy)
    assert duration == pytest.approx(99.0)


def test_get_audio_duration_returns_none_on_ffprobe_missing(tmp_path):
    dummy = tmp_path / "audio.mp3"
    dummy.write_bytes(b"")
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = get_audio_duration(dummy)
    assert result is None


def test_get_audio_duration_returns_none_on_error(tmp_path):
    dummy = tmp_path / "audio.mp3"
    dummy.write_bytes(b"")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = get_audio_duration(dummy)
    assert result is None
