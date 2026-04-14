"""Auto-update mechanism for WhisperX-App.

Checks PyPI for newer versions (cached with configurable TTL — default 24 hours).
The check runs silently in the background on startup and shows a brief notification
if a newer version is available.

Usage:
  - Automatic: called from startup.py (non-blocking, respects TTL)
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

PYPI_URL = "https://pypi.org/pypi/whisperx-app/json"
UPDATE_CHECK_INTERVAL_HOURS = 24


# ---------------------------------------------------------------------------
# Version utilities
# ---------------------------------------------------------------------------

def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a PEP-440 version string into a comparable tuple."""
    try:
        return tuple(int(x) for x in version_str.strip().split(".")[:3])
    except (ValueError, AttributeError):
        return (0,)


def is_newer(latest: str, current: str) -> bool:
    """Return True if latest is strictly newer than current."""
    return _parse_version(latest) > _parse_version(current)


# ---------------------------------------------------------------------------
# PyPI fetch
# ---------------------------------------------------------------------------

def fetch_latest_version(timeout: float = 5.0) -> Optional[str]:
    """Query PyPI for the latest published version of whisperx-app.

    Returns the version string (e.g. "0.2.1") or None on failure.
    """
    try:
        import httpx
        with httpx.Client(timeout=timeout) as client:
            response = client.get(PYPI_URL)
            response.raise_for_status()
            data = response.json()
            return data["info"]["version"]
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
    """Check for a newer version and offer to install it.

    Args:
        force: Skip TTL check and always query PyPI
    """
    console.print(f"Aktuelle Version: [cyan]{__version__}[/cyan]")
    console.print("Prüfe PyPI auf neue Version...")

    latest = fetch_latest_version(timeout=10.0)
    _record_check_time()

    if latest is None:
        console.print(
            "[yellow]Konnte PyPI nicht erreichen. Bitte Netzwerkverbindung prüfen.[/yellow]"
        )
        return

    console.print(f"Neueste Version auf PyPI: [cyan]{latest}[/cyan]")

    if not is_newer(latest, __version__):
        console.print("[green]WhisperX-App ist bereits auf dem neuesten Stand.[/green]")
        return

    if not Confirm.ask(
        f"\n[bold]Update auf {latest} installieren?[/bold]",
        default=True,
    ):
        console.print("Update abgebrochen.")
        return

    _perform_update(latest)


def _perform_update(target_version: Optional[str] = None) -> None:
    """Run pip to upgrade whisperx-app."""
    spec = f"whisperx-app=={target_version}" if target_version else "whisperx-app"
    console.print(f"\n[cyan]Installiere {spec}...[/cyan]")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", spec],
        capture_output=False,
        text=True,
    )

    if result.returncode == 0:
        console.print(
            f"\n[green]Update erfolgreich![/green] "
            f"Bitte WhisperX-App neu starten, um die neue Version zu verwenden."
        )
    else:
        console.print(
            "[red]Update fehlgeschlagen. Bitte manuell ausführen:[/red]\n"
            f"  pip install --upgrade whisperx-app"
        )
