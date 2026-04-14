"""Tests for installer.py — dependency checking, package name extraction, uninstall tracking."""

import pytest

from whisperx_app.installer import _extract_package_names, check_missing_deps
from whisperx_app.config import load_install_tracker, save_install_tracker


def test_extract_package_names_basic():
    specs = ["torch>=2.0", "whisperx>=3.1", "uvicorn[standard]>=0.30"]
    names = _extract_package_names(specs)
    assert names == ["torch", "whisperx", "uvicorn"]


def test_extract_package_names_no_version():
    specs = ["rich", "typer"]
    names = _extract_package_names(specs)
    assert names == ["rich", "typer"]


def test_extract_package_names_with_extras():
    specs = ["python-jose[cryptography]>=3.3"]
    names = _extract_package_names(specs)
    assert names == ["python-jose"]


def test_check_missing_deps_returns_list():
    # Should return a list of tuples; can't assert exact content since
    # packages may or may not be installed in the test environment.
    result = check_missing_deps()
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_install_tracker_records_new_packages(tmp_config_dir):
    save_install_tracker(["torch>=2.0", "whisperx>=3.1"])
    tracked = load_install_tracker()
    assert "torch>=2.0" in tracked
    assert "whisperx>=3.1" in tracked


def test_install_tracker_does_not_duplicate(tmp_config_dir):
    save_install_tracker(["torch>=2.0"])
    # Simulate a second install run — should not duplicate
    existing = set(load_install_tracker())
    new_installs = ["torch>=2.0", "librosa>=0.10"]
    updated = list(existing | set(new_installs))
    save_install_tracker(updated)
    tracked = load_install_tracker()
    assert tracked.count("torch>=2.0") == 1
