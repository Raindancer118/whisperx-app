"""Startup self-tests for WhisperX-App.

These checks run on every startup before user interaction begins.
The same assertions are also exercised by tests/test_startup.py.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from whisperx_app.config import CONFIG_DIR

console = Console()

MIN_PYTHON = (3, 10)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    fatal: bool = True


def check_python_version() -> CheckResult:
    ok = sys.version_info >= MIN_PYTHON
    detail = f"Python {sys.version_info[0]}.{sys.version_info[1]} (mindestens {MIN_PYTHON[0]}.{MIN_PYTHON[1]} erforderlich)"
    return CheckResult("Python-Version", ok, detail, fatal=True)


def check_ffprobe() -> CheckResult:
    found = shutil.which("ffprobe") is not None
    detail = shutil.which("ffprobe") or "Nicht gefunden — bitte ffmpeg installieren"
    return CheckResult("ffprobe (ffmpeg)", found, detail, fatal=False)


def check_config_dir() -> CheckResult:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        test_file = CONFIG_DIR / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return CheckResult("Konfigurationsverzeichnis", True, str(CONFIG_DIR))
    except Exception as e:
        return CheckResult("Konfigurationsverzeichnis", False, str(e), fatal=True)


def check_whisperx_importable() -> CheckResult:
    ok = importlib.util.find_spec("whisperx") is not None
    detail = "Installiert" if ok else "Nicht installiert — wird beim Start angeboten"
    return CheckResult("whisperx", ok, detail, fatal=False)


def check_torch_importable() -> CheckResult:
    ok = importlib.util.find_spec("torch") is not None
    detail = "Installiert" if ok else "Nicht installiert — wird beim Start angeboten"
    return CheckResult("torch", ok, detail, fatal=False)


ALL_CHECKS = [
    check_python_version,
    check_ffprobe,
    check_config_dir,
    check_whisperx_importable,
    check_torch_importable,
]


def run_startup_checks(verbose: bool = True) -> list[CheckResult]:
    """Execute all startup checks and return results."""
    results = [fn() for fn in ALL_CHECKS]

    if verbose:
        _print_results(results)

    return results


def _print_results(results: list[CheckResult]) -> None:
    table = Table(title="Startup-Checks", show_header=True, header_style="bold cyan")
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    for r in results:
        if r.passed:
            status = "[green]OK[/green]"
        elif r.fatal:
            status = "[red]FEHLER[/red]"
        else:
            status = "[yellow]WARNUNG[/yellow]"
        table.add_row(r.name, status, r.detail)

    console.print(table)


def assert_no_fatal_failures(results: list[CheckResult]) -> None:
    """Raise SystemExit if any fatal check failed."""
    failures = [r for r in results if r.fatal and not r.passed]
    if failures:
        console.print("\n[bold red]Kritische Fehler — App kann nicht gestartet werden:[/bold red]")
        for r in failures:
            console.print(f"  [red]✗[/red] {r.name}: {r.detail}")
        sys.exit(1)
