"""Tests for config.py — load, save, token management, install tracker."""

import json

import pytest

from whisperx_app.config import (
    Config,
    load_config,
    load_install_tracker,
    save_config,
    save_install_tracker,
)


def test_load_config_defaults(tmp_config_dir):
    cfg = load_config()
    assert cfg.default_model == "large-v3"
    assert cfg.default_device == "auto"
    assert cfg.hf_token is None


def test_save_and_reload_config(tmp_config_dir):
    cfg = Config(hf_token="hf_testtoken", default_model="medium")
    save_config(cfg)
    reloaded = load_config()
    assert reloaded.hf_token == "hf_testtoken"
    assert reloaded.default_model == "medium"


def test_config_file_is_valid_json(tmp_config_dir):
    cfg = Config(hf_token="hf_abc", default_device="cpu")
    save_config(cfg)
    import whisperx_app.config as cfg_module
    raw = cfg_module.CONFIG_FILE.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed["hf_token"] == "hf_abc"
    assert parsed["default_device"] == "cpu"


def test_save_config_atomic(tmp_config_dir):
    """Verify no .tmp file lingers after a successful save."""
    cfg = Config()
    save_config(cfg)
    import whisperx_app.config as cfg_module
    tmp_file = cfg_module.CONFIG_FILE.with_suffix(".tmp")
    assert not tmp_file.exists()


def test_install_tracker_empty_by_default(tmp_config_dir):
    tracked = load_install_tracker()
    assert tracked == []


def test_install_tracker_roundtrip(tmp_config_dir):
    pkgs = ["torch>=2.0", "whisperx>=3.1", "pyannote.audio>=3.1"]
    save_install_tracker(pkgs)
    loaded = load_install_tracker()
    assert loaded == pkgs


def test_install_tracker_atomic(tmp_config_dir):
    save_install_tracker(["some-pkg>=1.0"])
    import whisperx_app.config as cfg_module
    tmp_file = cfg_module.INSTALL_TRACKER_FILE.with_suffix(".tmp")
    assert not tmp_file.exists()


def test_load_config_survives_corrupted_file(tmp_config_dir, capsys):
    import whisperx_app.config as cfg_module
    cfg_module.CONFIG_FILE.write_text("{ not valid json }", encoding="utf-8")
    cfg = load_config()
    assert cfg.default_model == "large-v3"  # falls back to defaults
