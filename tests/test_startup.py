"""Tests for startup.py — self-test checks that run on every launch."""

import sys
from unittest.mock import patch

import pytest

from whisperx_app.startup import (
    CheckResult,
    assert_no_fatal_failures,
    check_config_dir,
    check_ffprobe,
    check_python_version,
    check_torch_importable,
    check_whisperx_importable,
    run_startup_checks,
)


def test_python_version_check_passes():
    """Should pass since we're running on a compatible Python."""
    result = check_python_version()
    assert result.passed is True
    assert result.fatal is True


def test_python_version_check_fails_on_old_version():
    with patch("sys.version_info", (3, 9, 0)):
        result = check_python_version()
        assert result.passed is False


def test_ffprobe_check_returns_result():
    result = check_ffprobe()
    assert isinstance(result, CheckResult)
    assert result.fatal is False  # ffprobe missing is a warning, not fatal


def test_ffprobe_check_detects_missing(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _: None)
    result = check_ffprobe()
    assert result.passed is False


def test_config_dir_check_passes(tmp_config_dir, monkeypatch):
    import whisperx_app.startup as startup_module
    monkeypatch.setattr(startup_module, "CONFIG_DIR", tmp_config_dir)
    result = check_config_dir()
    assert result.passed is True


def test_config_dir_check_fails_on_unwritable(tmp_path, monkeypatch):
    import whisperx_app.startup as startup_module
    read_only = tmp_path / "readonly"
    read_only.mkdir(mode=0o555)
    monkeypatch.setattr(startup_module, "CONFIG_DIR", read_only / "subdir")
    result = check_config_dir()
    import os
    if os.geteuid() != 0:
        assert result.passed is False


def test_whisperx_check_returns_result():
    result = check_whisperx_importable()
    assert isinstance(result, CheckResult)
    assert result.fatal is False


def test_torch_check_returns_result():
    result = check_torch_importable()
    assert isinstance(result, CheckResult)
    assert result.fatal is False


def test_run_startup_checks_returns_all(tmp_config_dir, monkeypatch):
    import whisperx_app.startup as startup_module
    monkeypatch.setattr(startup_module, "CONFIG_DIR", tmp_config_dir)
    results = run_startup_checks(verbose=False)
    assert len(results) == 5


def test_assert_no_fatal_failures_raises_on_fatal():
    results = [CheckResult("TestCheck", passed=False, fatal=True)]
    with pytest.raises(SystemExit):
        assert_no_fatal_failures(results)


def test_assert_no_fatal_failures_ok_on_warning():
    results = [CheckResult("TestCheck", passed=False, fatal=False)]
    assert_no_fatal_failures(results)


def test_assert_no_fatal_failures_ok_when_all_pass():
    results = [CheckResult("TestCheck", passed=True, fatal=True)]
    assert_no_fatal_failures(results)
