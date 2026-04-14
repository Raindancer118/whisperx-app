"""Shared pytest fixtures for WhisperX-App tests."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect config to a temporary directory for isolated tests."""
    import whisperx_app.config as cfg_module

    config_dir = tmp_path / ".whisperx"
    config_dir.mkdir()

    monkeypatch.setattr(cfg_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_module, "CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_module, "INSTALL_TRACKER_FILE", config_dir / "installed_by_app.json")

    return config_dir


@pytest.fixture
def sample_segments():
    """Minimal WhisperX result segments for formatter tests."""
    return [
        {"start": 4.0, "end": 8.5, "text": " Hallo, willkommen zum Interview.", "speaker": "SPEAKER_00"},
        {"start": 9.0, "end": 13.2, "text": " Danke für die Einladung.", "speaker": "SPEAKER_01"},
        {"start": 14.0, "end": 18.0, "text": " Fangen wir direkt an.", "speaker": "SPEAKER_00"},
        {"start": 18.5, "end": 22.0, "text": " Sehr gerne.", "speaker": "SPEAKER_01"},
    ]


@pytest.fixture
def sample_whisperx_result(sample_segments):
    """Mock WhisperX transcription result."""
    return {
        "segments": sample_segments,
        "language": "de",
        "word_segments": [],
    }
