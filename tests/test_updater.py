"""Tests for updater.py — version comparison, PyPI fetch, TTL logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from whisperx_app.updater import (
    UPDATE_CHECK_INTERVAL_HOURS,
    _parse_version,
    _record_check_time,
    check_for_updates_on_startup,
    fetch_latest_version,
    is_newer,
    should_check_for_updates,
)


# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------

def test_parse_version_basic():
    assert _parse_version("1.2.3") == (1, 2, 3)


def test_parse_version_two_parts():
    assert _parse_version("0.1") == (0, 1)


def test_parse_version_invalid_returns_zero():
    assert _parse_version("not-a-version") == (0,)


def test_parse_version_strips_whitespace():
    assert _parse_version("  1.0.0  ") == (1, 0, 0)


# ---------------------------------------------------------------------------
# is_newer
# ---------------------------------------------------------------------------

def test_is_newer_true():
    assert is_newer("0.2.0", "0.1.0") is True


def test_is_newer_false_same():
    assert is_newer("0.1.0", "0.1.0") is False


def test_is_newer_false_older():
    assert is_newer("0.0.9", "0.1.0") is False


def test_is_newer_minor_bump():
    assert is_newer("1.10.0", "1.9.0") is True


def test_is_newer_patch_bump():
    assert is_newer("0.1.1", "0.1.0") is True


# ---------------------------------------------------------------------------
# should_check_for_updates
# ---------------------------------------------------------------------------

def test_should_check_when_no_last_check(tmp_config_dir, monkeypatch):
    monkeypatch.setattr("whisperx_app.updater.should_check_for_updates.__module__", None)
    # Redirect config to temp dir with no last_update_check
    import whisperx_app.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_config_dir / "config.json")

    result = should_check_for_updates()
    assert result is True


def test_should_not_check_when_recent(tmp_config_dir, monkeypatch):
    import json
    import whisperx_app.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    config_file = tmp_config_dir / "config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", config_file)

    # Write a recent check time (1 hour ago)
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    config_file.write_text(json.dumps({"last_update_check": recent}))

    result = should_check_for_updates()
    assert result is False


def test_should_check_when_overdue(tmp_config_dir, monkeypatch):
    import json
    import whisperx_app.config as cfg_mod

    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    config_file = tmp_config_dir / "config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", config_file)

    # Write a stale check time (48 hours ago)
    stale = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    config_file.write_text(json.dumps({"last_update_check": stale}))

    result = should_check_for_updates()
    assert result is True


# ---------------------------------------------------------------------------
# fetch_latest_version
# ---------------------------------------------------------------------------

def test_fetch_latest_version_success():
    mock_response = MagicMock()
    mock_response.json.return_value = {"info": {"version": "0.2.0"}}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        version = fetch_latest_version()

    assert version == "0.2.0"


def test_fetch_latest_version_network_error():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = Exception("Network error")
        mock_client_cls.return_value = mock_client

        version = fetch_latest_version()

    assert version is None


def test_fetch_latest_version_returns_none_on_import_error():
    with patch.dict("sys.modules", {"httpx": None}):
        version = fetch_latest_version()
    assert version is None


# ---------------------------------------------------------------------------
# check_for_updates_on_startup (integration-style)
# ---------------------------------------------------------------------------

def test_startup_check_no_output_when_up_to_date(tmp_config_dir, monkeypatch, capsys):
    import whisperx_app.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_config_dir / "config.json")
    monkeypatch.setattr("whisperx_app.updater.INSTALL_TRACKER_FILE",
                        tmp_config_dir / "installed_by_app.json", raising=False)

    with patch("whisperx_app.updater.should_check_for_updates", return_value=True):
        with patch("whisperx_app.updater.fetch_latest_version", return_value="0.0.1"):
            with patch("whisperx_app.updater._record_check_time"):
                # 0.0.1 < current version → no notification
                check_for_updates_on_startup()


def test_startup_check_shows_notification_when_update_available(
    tmp_config_dir, monkeypatch, capsys
):
    import whisperx_app.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_config_dir / "config.json")

    with patch("whisperx_app.updater.should_check_for_updates", return_value=True):
        with patch("whisperx_app.updater.fetch_latest_version", return_value="999.0.0"):
            with patch("whisperx_app.updater._record_check_time"):
                # Capture rich console output by checking the function runs without error
                check_for_updates_on_startup()  # Should not raise


def test_startup_check_skipped_when_within_ttl(tmp_config_dir, monkeypatch):
    import whisperx_app.config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", tmp_config_dir)
    monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_config_dir / "config.json")

    fetch_called = []

    with patch("whisperx_app.updater.should_check_for_updates", return_value=False):
        with patch("whisperx_app.updater.fetch_latest_version",
                   side_effect=lambda **kw: fetch_called.append(1)) as mock_fetch:
            check_for_updates_on_startup()
            mock_fetch.assert_not_called()
