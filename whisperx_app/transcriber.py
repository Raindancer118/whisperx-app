"""WhisperX transcription pipeline with speaker diarization.

Wraps whisperx.load_model → transcribe → align → diarize in a single call,
reporting progress to the terminal via Rich spinners.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def transcribe(
    audio_path: Path,
    model_name: str = "large-v3",
    device: str = "cpu",
    compute_type: str = "int8",
    hf_token: Optional[str] = None,
    diarize: bool = True,
    language: Optional[str] = None,
    batch_size: int = 4,
) -> dict[str, Any]:
    """Transcribe an audio file using WhisperX with optional speaker diarization.

    Args:
        audio_path: Path to the audio or video file
        model_name: WhisperX model identifier (e.g. "large-v3")
        device: "cpu" or "cuda"
        compute_type: "int8" (CPU) or "float16" (GPU)
        hf_token: HuggingFace token for pyannote diarization
        diarize: Enable speaker diarization
        language: ISO language code or None for auto-detection
        batch_size: Transcription batch size (4 for CPU, 16 for GPU)

    Returns:
        WhisperX result dict with keys: segments, language, word_segments
        Each segment has: start, end, text, speaker (if diarization enabled)
    """
    try:
        import whisperx
    except ImportError:
        raise RuntimeError(
            "whisperx ist nicht installiert. Bitte `whisperx-app deps` ausführen."
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # Stage 1: Load model
        task = progress.add_task("Lade Modell...", total=None)
        model = whisperx.load_model(
            model_name,
            device=device,
            compute_type=compute_type,
            language=language,
        )

        # Stage 2: Transcribe
        progress.update(task, description="Transkribiere Audio...")
        audio = whisperx.load_audio(str(audio_path))
        result = model.transcribe(audio, batch_size=batch_size)

        # Stage 3: Align (word-level timestamps)
        progress.update(task, description="Aligniere Wort-Zeitstempel...")
        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], device=device
            )
            result = whisperx.align(
                result["segments"], model_a, metadata, audio, device,
                return_char_alignments=False,
            )
        except Exception as e:
            console.print(f"[yellow]Alignment übersprungen: {e}[/yellow]")

        # Stage 4: Speaker diarization
        if diarize and hf_token:
            progress.update(task, description="Diarisiere Sprecher...")
            try:
                diarize_model = whisperx.DiarizationPipeline(
                    use_auth_token=hf_token, device=device
                )
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
            except Exception as e:
                console.print(f"[yellow]Diarisierung fehlgeschlagen: {e}[/yellow]")
        elif diarize and not hf_token:
            console.print(
                "[yellow]Diarisierung übersprungen: kein HuggingFace-Token konfiguriert.[/yellow]"
            )

        progress.update(task, description="[green]Fertig![/green]")

    return result
