"""WhisperX model management — check local availability and download with progress.

Models are stored in the HuggingFace hub cache (~/.cache/huggingface/hub).
This module uses huggingface_hub APIs directly for precise progress reporting.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Confirm

console = Console()

# Mapping model_name → HuggingFace repo ID (faster-whisper format)
MODEL_REPOS: dict[str, str] = {
    "tiny": "Systran/faster-whisper-tiny",
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base": "Systran/faster-whisper-base",
    "base.en": "Systran/faster-whisper-base.en",
    "small": "Systran/faster-whisper-small",
    "small.en": "Systran/faster-whisper-small.en",
    "medium": "Systran/faster-whisper-medium",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v2": "Systran/faster-whisper-large-v2",
    "large-v3": "Systran/faster-whisper-large-v3",
}

# Approximate download size in GB for user-facing display
MODEL_SIZES_GB: dict[str, float] = {
    "tiny": 0.15,
    "base": 0.29,
    "small": 0.97,
    "medium": 3.06,
    "large-v2": 3.09,
    "large-v3": 3.09,
}


def is_model_available(model_name: str) -> bool:
    """Return True if the model is cached locally (no download needed)."""
    try:
        from huggingface_hub import try_to_load_from_cache
        from huggingface_hub.utils import EntryNotFoundError, LocalEntryNotFoundError
    except ImportError:
        # huggingface_hub not installed — whisperx will handle download itself
        return False

    repo_id = MODEL_REPOS.get(model_name)
    if not repo_id:
        return False

    try:
        # Check for the model config file as a proxy for the full model
        result = try_to_load_from_cache(repo_id, "config.json")
        return result is not None and str(result) != "None"
    except Exception:
        return False


def download_model(model_name: str) -> bool:
    """Download the specified model with a rich progress bar.

    Returns True on success, False on failure/cancellation.
    """
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        console.print(
            "[red]huggingface_hub ist nicht installiert. "
            "Bitte zuerst `whisperx-app deps` ausführen.[/red]"
        )
        return False

    repo_id = MODEL_REPOS.get(model_name)
    if not repo_id:
        console.print(f"[red]Unbekanntes Modell: {model_name}[/red]")
        return False

    size_str = f"~{MODEL_SIZES_GB.get(model_name, '?')} GB"
    console.print(f"\n[cyan]Modell:[/cyan] {model_name}  ({repo_id})  [{size_str}]")

    if not Confirm.ask(f"Modell [bold]{model_name}[/bold] jetzt herunterladen?", default=True):
        console.print("[yellow]Download abgebrochen.[/yellow]")
        return False

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(f"Lade {model_name}...", total=None)

        try:
            snapshot_download(
                repo_id=repo_id,
                ignore_patterns=["*.msgpack", "flax_model*", "tf_model*", "rust_model*"],
            )
            progress.update(task, description=f"[green]{model_name} heruntergeladen[/green]", completed=1, total=1)
        except Exception as e:
            console.print(f"\n[red]Download fehlgeschlagen: {e}[/red]")
            return False

    console.print(f"[green]Modell {model_name} erfolgreich heruntergeladen.[/green]\n")
    return True


def ensure_model(model_name: str) -> None:
    """Ensure the model is locally available, prompting for download if needed.

    Raises SystemExit if the model is required but not available.
    """
    if is_model_available(model_name):
        console.print(f"[dim]Modell {model_name} ist lokal verfügbar.[/dim]")
        return

    console.print(f"\n[yellow]Modell [bold]{model_name}[/bold] ist nicht lokal installiert.[/yellow]")
    success = download_model(model_name)
    if not success:
        console.print(
            "[red]Modell nicht verfügbar. Starte die App erneut, um den Download durchzuführen.[/red]"
        )
        import sys
        sys.exit(1)


def list_available_models() -> list[str]:
    """Return names of all models that are locally cached."""
    return [name for name in MODEL_REPOS if is_model_available(name)]
