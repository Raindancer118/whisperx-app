"""WhisperX-App CLI — main entry point.

Commands:
  whisperx-app                    Interactive transcription flow
  whisperx-app transcribe <file>  Direct transcription with flags
  whisperx-app config             Interactive configuration editor
  whisperx-app api                Start the REST API server
  whisperx-app check              Run startup self-tests and exit
  whisperx-app deps               Show dependency status
  whisperx-app uninstall          Remove packages installed by this app
  whisperx-app update             Check for updates and install if available
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from whisperx_app import __version__

app = typer.Typer(
    name="whisperx-app",
    help="WhisperX-App — schnelle Audio-Transkription mit Sprecher-Diarisierung",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"whisperx-app [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Version anzeigen"),
    ] = None,
) -> None:
    """Wenn kein Unterbefehl angegeben, startet der interaktive Transkriptions-Flow."""
    if ctx.invoked_subcommand is None:
        _interactive_flow()


# ---------------------------------------------------------------------------
# whisperx-app check
# ---------------------------------------------------------------------------

@app.command("check")
def cmd_check() -> None:
    """Startup-Selbsttests ausführen und Ergebnis anzeigen."""
    from whisperx_app.startup import assert_no_fatal_failures, run_startup_checks

    console.print(Panel(f"[bold cyan]WhisperX-App {__version__}[/bold cyan] — Systemcheck", expand=False))
    results = run_startup_checks(verbose=True)
    assert_no_fatal_failures(results)
    console.print("[green]Alle kritischen Checks bestanden.[/green]")


# ---------------------------------------------------------------------------
# whisperx-app deps
# ---------------------------------------------------------------------------

@app.command("deps")
def cmd_deps() -> None:
    """Abhängigkeits-Status anzeigen und fehlende Pakete installieren."""
    from whisperx_app.installer import check_and_install, show_dependency_status

    show_dependency_status()
    missing = __import__("whisperx_app.installer", fromlist=["check_missing_deps"]).check_missing_deps()
    if missing:
        check_and_install()


# ---------------------------------------------------------------------------
# whisperx-app config
# ---------------------------------------------------------------------------

@app.command("config")
def cmd_config() -> None:
    """Konfiguration interaktiv bearbeiten."""
    from whisperx_app.config import Config, load_config, save_config

    cfg = load_config()
    console.print(Panel("[bold cyan]Konfigurationseditor[/bold cyan]", expand=False))
    console.print(f"Konfigurationsdatei: [dim]~/.whisperx/config.json[/dim]\n")

    new_model = Prompt.ask(
        "Standard-Modell",
        default=cfg.default_model,
        choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"],
        show_choices=True,
    )
    new_device = Prompt.ask(
        "Standard-Gerät",
        default=cfg.default_device,
        choices=["auto", "cpu", "cuda"],
        show_choices=True,
    )

    # HF Token
    change_token = Confirm.ask(
        f"HuggingFace-Token {'ändern' if cfg.hf_token else 'setzen'}?",
        default=not bool(cfg.hf_token),
    )
    if change_token:
        new_token = Prompt.ask("HuggingFace Token", password=True)
        cfg.hf_token = new_token.strip() or cfg.hf_token

    cfg.default_model = new_model
    cfg.default_device = new_device
    save_config(cfg)
    console.print("\n[green]Konfiguration gespeichert.[/green]")


# ---------------------------------------------------------------------------
# whisperx-app uninstall
# ---------------------------------------------------------------------------

@app.command("uninstall")
def cmd_uninstall(
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Nur anzeigen, nicht wirklich entfernen")] = False,
) -> None:
    """Durch die App installierte Abhängigkeiten entfernen."""
    from whisperx_app.installer import uninstall_app_packages
    uninstall_app_packages(dry_run=dry_run)


# ---------------------------------------------------------------------------
# whisperx-app update
# ---------------------------------------------------------------------------

@app.command("update")
def cmd_update(
    force: Annotated[bool, typer.Option("--force", "-f", help="TTL ignorieren, immer PyPI prüfen")] = False,
) -> None:
    """Auf neue Version prüfen und bei Bedarf aktualisieren."""
    from whisperx_app.updater import check_and_update
    check_and_update(force=force)


# ---------------------------------------------------------------------------
# whisperx-app transcribe
# ---------------------------------------------------------------------------

@app.command("transcribe")
def cmd_transcribe(
    file: Annotated[Path, typer.Argument(help="Audio-/Videodatei zum Transkribieren")],
    output: Annotated[Optional[Path], typer.Option("--output", "-o", help="Ausgabedatei (leer = Terminal)")] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help="Ausgabeformat")] = "md",
    device: Annotated[str, typer.Option("--device", "-d", help="Gerät: auto, cpu oder cuda")] = "auto",
    model: Annotated[Optional[str], typer.Option("--model", "-m", help="WhisperX-Modell")] = None,
    no_diarize: Annotated[bool, typer.Option("--no-diarize", help="Sprecher-Diarisierung deaktivieren")] = False,
    language: Annotated[Optional[str], typer.Option("--language", "-l", help="Sprache (leer = auto)")] = None,
) -> None:
    """Audio-/Videodatei direkt transkribieren."""
    _run_transcription(
        audio_path=file,
        output_path=output,
        fmt=fmt,
        device=device,
        model_name=model,
        diarize=not no_diarize,
        language=language,
    )


# ---------------------------------------------------------------------------
# whisperx-app api
# ---------------------------------------------------------------------------

@app.command("api")
def cmd_api(
    host: Annotated[str, typer.Option("--host", help="Host-Adresse")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p", help="Port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Auto-Reload (nur Entwicklung)")] = False,
) -> None:
    """REST-API-Server starten."""
    _ensure_api_deps()
    import uvicorn
    from whisperx_app.api.main import create_app

    console.print(Panel(
        f"[bold cyan]WhisperX-App API[/bold cyan]\n"
        f"Läuft auf [link=http://{host}:{port}]http://{host}:{port}[/link]",
        expand=False,
    ))
    uvicorn.run(
        "whisperx_app.api.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_deps() -> None:
    """Check and optionally install heavy dependencies before transcription."""
    from whisperx_app.installer import check_and_install, check_missing_deps
    missing = check_missing_deps()
    if missing:
        ok = check_and_install()
        if not ok:
            console.print("[red]Fehlende Abhängigkeiten. Abbruch.[/red]")
            raise typer.Exit(code=1)


def _ensure_api_deps() -> None:
    """Ensure API-specific deps (fastapi, uvicorn) are installed."""
    import importlib.util
    needed = ["fastapi", "uvicorn"]
    missing = [m for m in needed if importlib.util.find_spec(m) is None]
    if missing:
        from whisperx_app.installer import _install_packages
        _install_packages([f"{m}>=0.115" if m == "fastapi" else f"{m}[standard]>=0.30" for m in missing])


def _interactive_flow() -> None:
    """Full interactive transcription wizard."""
    from whisperx_app.config import ensure_config_dir, load_config
    from whisperx_app.installer import check_and_install, check_missing_deps
    from whisperx_app.startup import assert_no_fatal_failures, run_startup_checks

    console.print(Panel(
        f"[bold cyan]WhisperX-App {__version__}[/bold cyan]\n"
        "[dim]Audio-Transkription mit Sprecher-Diarisierung[/dim]",
        expand=False,
    ))

    # 1. Startup checks
    results = run_startup_checks(verbose=True)
    assert_no_fatal_failures(results)

    # 1b. Non-blocking update check (respects 24h TTL)
    try:
        from whisperx_app.updater import check_for_updates_on_startup
        check_for_updates_on_startup()
    except Exception:
        pass  # Never let an update check crash the app

    console.print()

    # 2. Dependency check / install
    missing = check_missing_deps()
    if missing:
        ok = check_and_install()
        if not ok:
            console.print("[red]Kann ohne vollständige Abhängigkeiten nicht fortfahren.[/red]")
            raise typer.Exit(code=1)

    # 3. Config / HF token
    ensure_config_dir()
    cfg = load_config()

    # 4. Model check / download
    from whisperx_app.model_manager import ensure_model
    model_name = cfg.default_model
    ensure_model(model_name)

    # 5. File input
    console.print()
    console.print("[bold]Audio-Datei auswählen[/bold]")
    console.print("[dim]Tipp: Datei per Drag & Drop in das Terminal ziehen oder Pfad eingeben[/dim]")
    raw_path = Prompt.ask("Dateipfad")
    audio_path = Path(raw_path.strip("'\""))

    if not audio_path.exists():
        console.print(f"[red]Datei nicht gefunden: {audio_path}[/red]")
        raise typer.Exit(code=1)

    # 6. GPU detection
    from whisperx_app.gpu import select_device
    device, compute_type = select_device(cfg.default_device)

    # 7. Time estimation
    from whisperx_app.estimator import estimate_processing_time, get_audio_duration
    duration = get_audio_duration(audio_path)
    if duration:
        estimate = estimate_processing_time(duration, device)
        console.print(f"\n[cyan]Audiodauer:[/cyan] {_format_duration(duration)}")
        console.print(f"[cyan]Geschätzte Verarbeitungszeit:[/cyan] ~{_format_duration(estimate)}\n")

    # 8. Output format
    fmt = Prompt.ask(
        "Ausgabeformat",
        choices=["txt", "json", "md"],
        default="md",
    )

    # 9. Output destination
    output_choice = Prompt.ask(
        "Ausgabe",
        choices=["terminal", "datei"],
        default="terminal",
    )
    output_path: Optional[Path] = None
    if output_choice == "datei":
        out_raw = Prompt.ask("Ausgabedatei (Pfad)")
        output_path = Path(out_raw.strip("'\""))

    # 10. Speaker name mapping
    speaker_names: dict[str, str] = {}
    if Confirm.ask("Sprecher benennen? (z.B. SPEAKER_00 = Tom)", default=False):
        console.print("[dim]Format: SPEAKER_00=Tom (Enter zum Beenden)[/dim]")
        while True:
            entry = Prompt.ask("Sprecher-Mapping (oder Enter zum Beenden)", default="")
            if not entry:
                break
            if "=" in entry:
                k, v = entry.split("=", 1)
                speaker_names[k.strip()] = v.strip()

    # 11. Run transcription
    _run_transcription(
        audio_path=audio_path,
        output_path=output_path,
        fmt=fmt,
        device=device,
        model_name=model_name,
        diarize=True,
        language=None,
        speaker_names=speaker_names,
    )


def _run_transcription(
    audio_path: Path,
    output_path: Optional[Path],
    fmt: str,
    device: str,
    model_name: Optional[str],
    diarize: bool,
    language: Optional[str],
    speaker_names: Optional[dict[str, str]] = None,
) -> None:
    """Core transcription logic used by both interactive flow and direct command."""
    _ensure_deps()

    from whisperx_app.config import ensure_hf_token, load_config
    from whisperx_app.formatter import format_result
    from whisperx_app.gpu import select_device
    from whisperx_app.transcriber import transcribe

    cfg = load_config()
    if model_name is None:
        model_name = cfg.default_model

    if device == "auto":
        device, compute_type = select_device("auto")
    else:
        compute_type = "float16" if device == "cuda" else "int8"

    hf_token = None
    if diarize:
        try:
            hf_token = ensure_hf_token()
        except ValueError as e:
            console.print(f"[yellow]Diarisierung übersprungen: {e}[/yellow]")
            diarize = False

    batch_size = cfg.api_batch_size_gpu if device == "cuda" else cfg.api_batch_size_cpu

    result = transcribe(
        audio_path=audio_path,
        model_name=model_name,
        device=device,
        compute_type=compute_type,
        hf_token=hf_token,
        diarize=diarize,
        language=language,
        batch_size=batch_size,
    )

    output_text = format_result(
        result=result,
        fmt=fmt,
        source_file=audio_path,
        model_name=model_name,
        speaker_names=speaker_names or {},
    )

    if output_path:
        output_path.write_text(output_text, encoding="utf-8")
        console.print(f"\n[green]Ergebnis gespeichert:[/green] {output_path}")
    else:
        console.print("\n" + output_text)


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
