"""Dependency installer for WhisperX-App.

Heavy ML and API packages are not required at install time. This module checks
which are missing and offers to install them automatically. It also tracks which
packages were installed by the app so they can be removed via `whisperx-app uninstall`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from whisperx_app.config import (
    load_install_tracker,
    save_install_tracker,
)

console = Console()

# Maps importable module name → pip install spec
HEAVY_DEPS: dict[str, str] = {
    "whisperx": "whisperx>=3.1",
    "torch": "torch>=2.0",
    "pyannote": "pyannote.audio>=3.1",
    "librosa": "librosa>=0.10",
    "soundfile": "soundfile>=0.12",
    "fastapi": "fastapi>=0.115",
    "uvicorn": "uvicorn[standard]>=0.30",
    "multipart": "python-multipart>=0.0.9",
    "jose": "python-jose[cryptography]>=3.3",
    "aiofiles": "aiofiles>=23.0",
}

# ffprobe is a system binary, not a pip package
FFPROBE_INSTRUCTIONS = {
    "linux": "sudo apt install ffmpeg   # Debian/Ubuntu\nsudo pacman -S ffmpeg    # Arch/Manjaro\nsudo dnf install ffmpeg  # Fedora",
    "darwin": "brew install ffmpeg",
    "win32": "winget install ffmpeg   # oder: https://ffmpeg.org/download.html",
}


def _is_importable(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _ffprobe_available() -> bool:
    import shutil
    return shutil.which("ffprobe") is not None


def check_missing_deps() -> list[tuple[str, str]]:
    """Return list of (module_name, pip_spec) tuples for packages that are not installed."""
    return [
        (mod, spec)
        for mod, spec in HEAVY_DEPS.items()
        if not _is_importable(mod)
    ]


def check_and_install(quiet: bool = False) -> bool:
    """Check for missing heavy dependencies and offer to install them.

    Returns True if all dependencies are available (after potential install),
    False if the user declined or an install failed.
    """
    missing = check_missing_deps()
    ffprobe_ok = _ffprobe_available()

    if not missing and ffprobe_ok:
        if not quiet:
            console.print("[green]Alle Abhängigkeiten sind installiert.[/green]")
        return True

    console.print()
    console.print(
        Panel(
            "[bold yellow]Fehlende Abhängigkeiten[/bold yellow]",
            expand=False,
        )
    )

    if missing:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Paket")
        table.add_column("Pip-Spezifikation")
        for mod, spec in missing:
            table.add_row(mod, spec)
        console.print(table)

    if not ffprobe_ok:
        console.print(
            "\n[yellow]ffprobe (ffmpeg) ist nicht auf dem PATH gefunden.[/yellow]\n"
            "Bitte manuell installieren:\n"
        )
        platform = sys.platform
        instructions = FFPROBE_INSTRUCTIONS.get(platform, FFPROBE_INSTRUCTIONS["linux"])
        console.print(f"  [cyan]{instructions}[/cyan]\n")
        console.print("  Danach diese App erneut starten.\n")

    if not missing:
        return False  # Only ffprobe missing — user must install manually

    if not Confirm.ask(
        f"\n[bold]{len(missing)} Paket(e) jetzt automatisch installieren?[/bold]"
    ):
        console.print("[red]Installation abgebrochen. Manche Funktionen sind nicht verfügbar.[/red]")
        return False

    return _install_packages([spec for _, spec in missing])


def _install_packages(specs: list[str]) -> bool:
    """Install the given pip specs and track them for potential uninstallation."""
    already_tracked = set(load_install_tracker())
    newly_installed: list[str] = []

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Installiere Pakete...", total=len(specs))

        for spec in specs:
            progress.update(task, description=f"Installiere [cyan]{spec}[/cyan]...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", spec],
                capture_output=False,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"\n[red]Fehler beim Installieren von {spec}.[/red]")
                return False

            if spec not in already_tracked:
                newly_installed.append(spec)
            progress.advance(task)

    # Persist tracking
    updated = list(already_tracked | set(newly_installed))
    save_install_tracker(updated)

    console.print(
        f"\n[green]Installation abgeschlossen.[/green] "
        f"({len(newly_installed)} neue Pakete vermerkt für spätere Deinstallation)\n"
    )
    return True


def uninstall_app_packages(dry_run: bool = False) -> None:
    """Remove all packages that were installed by this app.

    Only removes packages recorded in ~/.whisperx/installed_by_app.json.
    Packages that were already present before the app installed them are NOT removed.
    """
    tracked = load_install_tracker()

    if not tracked:
        console.print("[yellow]Keine durch die App installierten Pakete gefunden.[/yellow]")
        return

    console.print()
    console.print(Panel("[bold red]App-Abhängigkeiten deinstallieren[/bold red]", expand=False))
    console.print(
        "Folgende Pakete wurden durch WhisperX-App installiert und werden entfernt:\n"
    )

    table = Table(show_header=False)
    table.add_column("Paket", style="cyan")
    for pkg in tracked:
        table.add_row(pkg)
    console.print(table)

    if dry_run:
        console.print("\n[yellow](Dry-Run — keine Pakete wurden entfernt)[/yellow]")
        return

    if not Confirm.ask("\n[bold red]Wirklich deinstallieren?[/bold red]"):
        console.print("Abgebrochen.")
        return

    # Extract package names (strip version specifiers) for pip uninstall
    pkg_names = _extract_package_names(tracked)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Deinstalliere...", total=len(pkg_names))
        for name in pkg_names:
            progress.update(task, description=f"Entferne [cyan]{name}[/cyan]...")
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", name],
                capture_output=True,
            )
            progress.advance(task)

    # Clear tracker
    save_install_tracker([])
    console.print("\n[green]Alle App-Pakete wurden deinstalliert.[/green]")
    console.print(
        "[dim]Hinweis: whisperx-app selbst ist noch installiert. "
        "Zum vollständigen Entfernen: pip uninstall whisperx-app[/dim]"
    )


def _extract_package_names(specs: list[str]) -> list[str]:
    """Convert pip specs like 'torch>=2.0' to package names like 'torch'."""
    import re
    names = []
    for spec in specs:
        # Strip extras like [standard], version constraints, and whitespace
        name = re.split(r"[\[>=<!]", spec)[0].strip()
        if name:
            names.append(name)
    return names


def show_dependency_status() -> None:
    """Print a rich table showing which dependencies are installed."""
    console.print()
    table = Table(title="Abhängigkeits-Status", show_header=True, header_style="bold cyan")
    table.add_column("Paket")
    table.add_column("Status")
    table.add_column("Notizen")

    for mod, spec in HEAVY_DEPS.items():
        ok = _is_importable(mod)
        status = "[green]Installiert[/green]" if ok else "[red]Fehlt[/red]"
        notes = "" if ok else f"pip install {spec}"
        table.add_row(mod, status, notes)

    ffprobe_ok = _ffprobe_available()
    table.add_row(
        "ffprobe (System)",
        "[green]Gefunden[/green]" if ffprobe_ok else "[red]Nicht gefunden[/red]",
        "" if ffprobe_ok else "Systempaket: apt/pacman/brew install ffmpeg",
    )

    console.print(table)
    console.print()
