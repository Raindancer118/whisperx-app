"""Configuration management for WhisperX-App.

Config is stored in ~/.whisperx/config.json and managed via the Config Pydantic model.
Writes are atomic (write to .tmp then rename) to prevent corruption on crash.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from rich.console import Console
from rich.prompt import Prompt

console = Console()

CONFIG_DIR = Path.home() / ".whisperx"
CONFIG_FILE = CONFIG_DIR / "config.json"
INSTALL_TRACKER_FILE = CONFIG_DIR / "installed_by_app.json"


class Config(BaseModel):
    hf_token: Optional[str] = None
    default_model: str = "large-v3"
    default_device: str = "auto"
    model_cache_dir: str = str(Path.home() / ".whisperx" / "models")
    api_batch_size_gpu: int = 16
    api_batch_size_cpu: int = 4
    volantic_client_id: str = "whisperx-app"
    volantic_issuer: str = "https://accounts.volantic.de"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    last_update_check: Optional[str] = None  # ISO timestamp of last GitHub version check


def ensure_config_dir() -> None:
    """Create ~/.whisperx/ if it does not yet exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    model_cache = Path(load_config().model_cache_dir)
    model_cache.mkdir(parents=True, exist_ok=True)


def load_config() -> Config:
    """Load config from disk, returning defaults if file does not exist."""
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return Config(**data)
        except Exception:
            console.print(
                "[yellow]Warnung: Konfigurationsdatei konnte nicht gelesen werden. "
                "Standardwerte werden verwendet.[/yellow]"
            )
    return Config()


def save_config(config: Config) -> None:
    """Atomically write config to ~/.whisperx/config.json."""
    ensure_config_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def load_install_tracker() -> list[str]:
    """Return list of pip package specs installed by this app."""
    if INSTALL_TRACKER_FILE.exists():
        try:
            return json.loads(INSTALL_TRACKER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_install_tracker(packages: list[str]) -> None:
    """Atomically persist the list of app-installed packages."""
    ensure_config_dir()
    tmp = INSTALL_TRACKER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(packages, indent=2), encoding="utf-8")
    tmp.replace(INSTALL_TRACKER_FILE)


def ensure_hf_token() -> str:
    """Return the HuggingFace token, prompting the user if not yet configured.

    Speaker diarization via pyannote.audio requires:
    1. A HuggingFace account token with read access
    2. Accepted terms at https://hf.co/pyannote/speaker-diarization-3.1
    """
    config = load_config()
    if config.hf_token:
        return config.hf_token

    console.print()
    console.print("[bold cyan]HuggingFace-Token erforderlich[/bold cyan]")
    console.print(
        "Die Sprecher-Diarisierung (pyannote.audio) benötigt einen HuggingFace-Account-Token.\n"
        "\n"
        "[bold]Schritte:[/bold]\n"
        "  1. Erstelle einen Account auf [link=https://huggingface.co]huggingface.co[/link]\n"
        "  2. Akzeptiere die Nutzungsbedingungen unter:\n"
        "     [blue]https://hf.co/pyannote/speaker-diarization-3.1[/blue]\n"
        "  3. Erstelle einen Access Token unter:\n"
        "     [blue]https://hf.co/settings/tokens[/blue]\n"
    )

    token = Prompt.ask("[bold]HuggingFace Token eingeben[/bold]", password=True)
    if not token.strip():
        raise ValueError("Kein Token eingegeben. Abbruch.")

    config.hf_token = token.strip()
    save_config(config)
    console.print("[green]Token gespeichert.[/green]\n")
    return config.hf_token
