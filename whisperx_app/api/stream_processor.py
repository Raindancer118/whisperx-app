"""Background processing pipeline for live audio stream sessions.

Pipeline (triggered after 'bye'):
  1. Convert full raw audio → 16 kHz mono WAV via ffmpeg
  2. Full WhisperX pass (transcription + alignment + diarization)
  3. Gemma 4 correction pass (chunk-by-chunk with rolling context)
  4. Gemma 4 summary

Rolling transcription:
  Runs concurrently with the stream.  Every CROWD_ROLLING_INTERVAL seconds a
  small faster-whisper model transcribes newly buffered audio.  The result is
  stored only as rough context for the later Gemma correction pass — it is
  never delivered to the caller as a final result.

Configuration (environment variables):
  CROWD_ROLLING_INTERVAL   seconds between rolling passes   default: 30
  CROWD_LIVE_MODEL         faster-whisper model for rolling default: base
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whisperx_app.api.stream_store import StreamSession

log = logging.getLogger(__name__)

ROLLING_INTERVAL_SECONDS: float = float(os.environ.get("CROWD_ROLLING_INTERVAL", "30"))
LIVE_TRANSCRIPTION_MODEL: str = os.environ.get("CROWD_LIVE_MODEL", "base")

# Correction pass: chars of neighbouring chunk passed as context
_CONTEXT_CHARS = 500
# Target chunk size for the correction pass (~5 min of speech ≈ 2 000 chars)
_CORRECTION_CHUNK_SIZE = 2_000


# =========================================================================== #
# Rolling transcription (runs during stream)                                  #
# =========================================================================== #

async def rolling_transcription_loop(session: "StreamSession") -> None:
    """Periodically transcribe newly buffered audio with a small model.

    Results are appended to *session.interim_text* for use as rough context
    in the later Gemma correction pass.  This loop runs until the session
    status changes away from 'streaming'.
    """
    while session.status == "streaming":
        await asyncio.sleep(ROLLING_INTERVAL_SECONDS)
        try:
            if session.unprocessed_seconds() >= ROLLING_INTERVAL_SECONDS * 0.8:
                await _transcribe_new_chunk(session)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning(
                "Rolling transcription error [session=%s]: %s",
                session.session_id, exc,
            )


async def _transcribe_new_chunk(session: "StreamSession") -> None:
    """Transcribe bytes buffered since the last rolling pass."""
    if not session.audio_raw_path.exists():
        return

    start_byte = session.processed_bytes
    current_size = session.total_bytes_received
    if current_size <= start_byte:
        return

    chunk_wav = session.work_dir / f"rolling_{start_byte}.wav"
    try:
        await _extract_and_convert(
            src_path=session.audio_raw_path,
            out_path=chunk_wav,
            start_byte=start_byte,
            byte_count=current_size - start_byte,
            src_format=session.audio_format,
            sample_rate=session.sample_rate,
            channels=session.channels,
        )
        text = await asyncio.get_event_loop().run_in_executor(
            None, _quick_transcribe, chunk_wav
        )
        if text:
            session.interim_text += (" " if session.interim_text else "") + text
        session.processed_bytes = current_size
    finally:
        chunk_wav.unlink(missing_ok=True)


# =========================================================================== #
# Final processing pipeline (runs after stream ends)                          #
# =========================================================================== #

async def process_stream_final(session: "StreamSession") -> None:
    """Full post-stream pipeline.  Updates session fields in place.

    Steps:
      1. Convert all raw audio → 16 kHz mono WAV
      2. Full WhisperX pipeline (transcription + alignment + diarization)
      3. Gemma 4 correction pass
      4. Gemma 4 summary
    """
    from whisperx_app.api.ollama_client import generate_summary

    session.status = "processing"

    full_wav = session.work_dir / "full.wav"
    try:
        # ── Step 1: Audio conversion ──────────────────────────────────── #
        log.info("Session %s: converting audio…", session.session_id)
        await _convert_full_audio(session, full_wav)

        # ── Step 2: WhisperX transcription ────────────────────────────── #
        log.info("Session %s: running WhisperX…", session.session_id)
        session.final_transcript = await asyncio.get_event_loop().run_in_executor(
            None, _full_transcribe, full_wav
        )

        # ── Step 3: Gemma correction pass ─────────────────────────────── #
        log.info("Session %s: running Gemma correction pass…", session.session_id)
        session.corrected_transcript = await _correction_pass(
            transcript=session.final_transcript,
            rough_text=session.interim_text,
        )

        # ── Step 4: Gemma summary ─────────────────────────────────────── #
        log.info("Session %s: generating summary…", session.session_id)
        session.summary = await generate_summary(session.corrected_transcript)

        session.status = "done"
        log.info("Session %s: processing complete.", session.session_id)

    except Exception as exc:
        session.status = "failed"
        session.error = str(exc)
        log.error("Session %s: processing failed: %s", session.session_id, exc, exc_info=True)
        raise

    finally:
        # Remove large intermediate files; keep work_dir for potential debugging
        full_wav.unlink(missing_ok=True)
        if session.audio_raw_path.exists():
            session.audio_raw_path.unlink(missing_ok=True)


# =========================================================================== #
# Time estimation                                                              #
# =========================================================================== #

def estimate_postprocess_seconds(session: "StreamSession") -> float:
    """Rough estimate of total post-processing wall time in seconds."""
    audio_secs = session.total_audio_seconds()

    # WhisperX estimate
    try:
        from whisperx_app.config import load_config
        from whisperx_app.estimator import estimate_processing_time
        from whisperx_app.gpu import detect_hardware

        hw = detect_hardware()
        cfg = load_config()
        device = "cuda" if hw["cuda"] else "cpu"
        whisperx_est = estimate_processing_time(
            audio_secs, device, cfg.default_model,
            gpu_device_name=hw.get("device_name"),
            diarize=True,
        )
    except Exception:
        whisperx_est = audio_secs * 0.5  # fallback: 50 % of audio duration

    # Gemma correction: ~30 s per 2 000-char chunk on CPU
    # Rough heuristic: ~15 chars per second of speech
    n_chunks = max(1, int(audio_secs * 15 / _CORRECTION_CHUNK_SIZE))
    gemma_correction_est = n_chunks * 30.0

    # Summary: fixed ~60 s
    return whisperx_est + gemma_correction_est + 60.0


# =========================================================================== #
# Internal helpers                                                             #
# =========================================================================== #

async def _extract_and_convert(
    src_path: Path,
    out_path: Path,
    start_byte: int,
    byte_count: int,
    src_format: str,
    sample_rate: int,
    channels: int,
) -> None:
    """Pipe a byte slice of *src_path* through ffmpeg → 16 kHz mono WAV."""
    if src_format == "pcm_s16le":
        input_args = ["-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels)]
    else:
        input_args = []  # let ffmpeg auto-detect

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-i", "pipe:0",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out_path),
    ]

    with open(src_path, "rb") as f:
        f.seek(start_byte)
        chunk_data = f.read(byte_count)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate(input=chunk_data)

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg chunk conversion failed: {stderr.decode(errors='replace')[:300]}"
        )


async def _convert_full_audio(session: "StreamSession", out_path: Path) -> None:
    """Convert the entire raw audio file to 16 kHz mono WAV."""
    if not session.audio_raw_path.exists() or session.total_bytes_received == 0:
        raise FileNotFoundError("Session contains no audio data")

    if session.audio_format == "pcm_s16le":
        input_args = [
            "-f", "s16le",
            "-ar", str(session.sample_rate),
            "-ac", str(session.channels),
        ]
    else:
        input_args = []

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-i", str(session.audio_raw_path),
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(out_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg full conversion failed: {stderr.decode(errors='replace')[:400]}"
        )


def _quick_transcribe(wav_path: Path) -> str:
    """Transcribe with a small faster-whisper model (no alignment/diarization)."""
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
    except ImportError:
        return ""

    model = WhisperModel(LIVE_TRANSCRIPTION_MODEL, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(wav_path),
        beam_size=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


def _full_transcribe(wav_path: Path) -> str:
    """Full WhisperX pipeline: transcription + alignment + diarization."""
    from whisperx_app.config import load_config
    from whisperx_app.formatter import format_result
    from whisperx_app.gpu import detect_hardware
    from whisperx_app.transcriber import transcribe

    cfg = load_config()
    hw = detect_hardware()
    device = "cuda" if hw["cuda"] else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    batch_size = cfg.api_batch_size_gpu if device == "cuda" else cfg.api_batch_size_cpu

    result = transcribe(
        audio_path=wav_path,
        model_name=cfg.default_model,
        device=device,
        compute_type=compute_type,
        hf_token=cfg.hf_token,
        diarize=True,
        language=None,
        batch_size=batch_size,
    )
    return format_result(result=result, fmt="md", model_name=cfg.default_model)


async def _correction_pass(transcript: str, rough_text: str) -> str:
    """Run Gemma 4 over every chunk of *transcript* with surrounding context."""
    from whisperx_app.api.ollama_client import correct_transcript_chunk

    if len(transcript) <= _CORRECTION_CHUNK_SIZE:
        return await correct_transcript_chunk(
            chunk=transcript,
            rough_context=rough_text[:2_000],
        )

    chunks = _split_at_paragraphs(transcript, _CORRECTION_CHUNK_SIZE)
    corrected: list[str] = []

    for i, chunk in enumerate(chunks):
        prev_ctx = chunks[i - 1][-_CONTEXT_CHARS:] if i > 0 else ""
        next_ctx = chunks[i + 1][:_CONTEXT_CHARS] if i < len(chunks) - 1 else ""

        # Align rough text to approximate position in the stream
        rough_offset = int(len(rough_text) * i / len(chunks))
        rough_slice = rough_text[rough_offset: rough_offset + 1_000]

        result = await correct_transcript_chunk(
            chunk=chunk,
            prev_context=prev_ctx,
            next_context=next_ctx,
            rough_context=rough_slice,
        )
        corrected.append(result)
        log.debug(
            "Correction pass: chunk %d/%d done [session context]",
            i + 1, len(chunks),
        )

    return "\n\n".join(corrected)


def _split_at_paragraphs(text: str, chunk_size: int) -> list[str]:
    """Split *text* into chunks of ≤ *chunk_size* chars at paragraph boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Prefer double newline, then single newline, then hard cut
        split_at = text.rfind("\n\n", start, end)
        if split_at == -1:
            split_at = text.rfind("\n", start, end)
        if split_at == -1 or split_at == start:
            split_at = end
        chunks.append(text[start:split_at])
        if split_at == end:
            # Hard cut — no separator to skip over
            start = end
        elif text[split_at: split_at + 2] == "\n\n":
            start = split_at + 2
        else:
            start = split_at + 1
    return [c.strip() for c in chunks if c.strip()]
