"""Auto-update mechanism for WhisperX-App.

Checks the GitHub Releases API for newer versions (cached with configurable
TTL — default 24 hours). Installs via git+https so no PyPI publishing needed.

Usage:
  - Automatic: called from cli.py on startup (non-blocking, respects TTL)
  - Manual: `whisperx-app update`
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from whisperx_app import __version__

console = Console()

GITHUB_REPO = "Raindancer118/whisperx-app"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_INSTALL_URL = f"git+https://github.com/{GITHUB_REPO}.git"
UPDATE_CHECK_INTERVAL_HOURS = 24


# ---------------------------------------------------------------------------
# Version utilities
# ---------------------------------------------------------------------------

def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a comparable tuple, stripping a leading v."""
    try:
        clean = version_str.strip().lstrip("v")
        return tuple(int(x) for x in clean.split(".")[:3])
    except (ValueError, AttributeError):
        return (0,)


def is_newer(latest: str, current: str) -> bool:
    """Return True if latest is strictly newer than current."""
    return _parse_version(latest) > _parse_version(current)


# ---------------------------------------------------------------------------
# GitHub Releases fetch
# ---------------------------------------------------------------------------

def fetch_latest_version(timeout: float = 5.0) -> Optional[str]:
    """Query the GitHub Releases API for the latest tag of whisperx-app.

    Returns the version string (e.g. "0.2.1") or None on failure.
    The tag_name may have a leading "v" which is stripped.
    """
    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            tag = response.json().get("tag_name", "")
            return tag.lstrip("v") if tag else None
    except Exception:
        return None


def fetch_latest_tag(timeout: float = 5.0) -> Optional[str]:
    """Return the raw tag_name from the latest GitHub release (e.g. 'v0.2.1')."""
    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                GITHUB_API_URL,
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            return response.json().get("tag_name") or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# TTL-aware startup check
# ---------------------------------------------------------------------------

def should_check_for_updates() -> bool:
    """Return True if enough time has passed since the last update check."""
    from whisperx_app.config import load_config

    cfg = load_config()
    if not cfg.last_update_check:
        return True

    try:
        last_check = datetime.fromisoformat(cfg.last_update_check)
        now = datetime.now(timezone.utc)
        elapsed_hours = (now - last_check).total_seconds() / 3600
        return elapsed_hours >= UPDATE_CHECK_INTERVAL_HOURS
    except Exception:
        return True


def _record_check_time() -> None:
    """Persist the current UTC time as the last update check timestamp."""
    from whisperx_app.config import load_config, save_config

    cfg = load_config()
    cfg.last_update_check = datetime.now(timezone.utc).isoformat()
    save_config(cfg)


def check_for_updates_on_startup() -> None:
    """Silently check for updates on startup; print a one-line notice if available.

    Respects the UPDATE_CHECK_INTERVAL_HOURS TTL. Never blocks the user.
    """
    if not should_check_for_updates():
        return

    _record_check_time()
    latest = fetch_latest_version(timeout=3.0)
    if latest and is_newer(latest, __version__):
        console.print(
            f"[dim]Neue Version verfügbar: [cyan]{latest}[/cyan] "
            f"(aktuell: {__version__}) — `whisperx-app update` zum Aktualisieren[/dim]"
        )


# ---------------------------------------------------------------------------
# Interactive update command
# ---------------------------------------------------------------------------

def check_and_update(force: bool = False) -> None:
    """Check for a newer version on GitHub and offer to install it."""
    console.print(f"Aktuelle Version: [cyan]{__version__}[/cyan]")
    console.print(f"Prüfe GitHub auf neue Version ([dim]{GITHUB_REPO}[/dim])...")

    latest = fetch_latest_version(timeout=10.0)
    tag = fetch_latest_tag(timeout=10.0)
    _record_check_time()

    if latest is None:
        console.print(
            "[yellow]Konnte GitHub nicht erreichen. Bitte Netzwerkverbindung prüfen.[/yellow]"
        )
        return

    console.print(f"Neueste Version auf GitHub: [cyan]{latest}[/cyan]")

    if not is_newer(latest, __version__):
        console.print("[green]WhisperX-App ist bereits auf dem neuesten Stand.[/green]")
        return

    if not Confirm.ask(
        f"\n[bold]Update auf {latest} installieren?[/bold]",
        default=True,
    ):
        console.print("Update abgebrochen.")
        return

    _perform_update(tag or f"v{latest}")


def _perform_update(tag: str) -> None:
    """Install the given git tag from GitHub via pip."""
    install_spec = f"{GITHUB_INSTALL_URL}@{tag}"
    console.print(f"\n[cyan]Installiere {install_spec}...[/cyan]")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", install_spec],
        capture_output=False,
        text=True,
    )

    if result.returncode == 0:
        console.print(
            "\n[green]Update erfolgreich![/green] "
            "Bitte WhisperX-App neu starten, um die neue Version zu verwenden."
        )
    else:
        console.print(
            "[red]Update fehlgeschlagen. Bitte manuell ausführen:[/red]\n"
            f"  pip install --upgrade {install_spec}"
        )
