"""Audio duration detection and processing time estimation for WhisperX-App.

Audio duration is obtained via ffprobe (no additional Python dependency).
Processing time is estimated using empirically calibrated real-time factor (RTF) tables.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional


# Real-time factor table: processing_seconds = audio_seconds * RTF
# RTF < 1.0 means faster than real-time (GPU); > 1.0 means slower (CPU)
_CPU_RTF: dict[str, float] = {
    "tiny": 0.3,
    "base": 0.5,
    "small": 0.8,
    "medium": 1.8,
    "large-v2": 3.2,
    "large-v3": 3.5,
}

_GPU_RTF_BY_NAME: dict[str, float] = {
    # Pattern (lowercase) → RTF
    "a100": 0.08,
    "a10": 0.12,
    "a6000": 0.12,
    "3090": 0.18,
    "4090": 0.14,
    "3080": 0.22,
    "4080": 0.18,
    "3070": 0.28,
    "4070": 0.22,
    "3060": 0.35,
    "2080": 0.30,
    "t4": 0.25,
    "v100": 0.12,
}
_GPU_RTF_GENERIC = 0.35  # fallback for unrecognised GPUs

# Extra overhead factor for the diarization pass (on top of transcription)
_DIARIZATION_OVERHEAD = 0.15


def get_audio_duration(path: Path) -> Optional[float]:
    """Return audio duration in seconds using ffprobe, or None if unavailable."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if "duration" in stream:
                return float(stream["duration"])
        # Fallback: check format-level duration
        result2 = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result2.returncode == 0:
            data2 = json.loads(result2.stdout)
            dur = data2.get("format", {}).get("duration")
            if dur:
                return float(dur)
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def estimate_processing_time(
    audio_duration: float,
    device: str,
    model_name: str = "large-v3",
    gpu_device_name: Optional[str] = None,
    diarize: bool = True,
) -> float:
    """Return estimated total processing time in seconds.

    Args:
        audio_duration: Length of audio in seconds
        device: "cpu" or "cuda"
        model_name: WhisperX model identifier
        gpu_device_name: GPU name string (from torch.cuda.get_device_name); used for RTF lookup
        diarize: Whether speaker diarization is enabled (adds overhead)

    Returns:
        Estimated processing time in seconds
    """
    if device == "cuda":
        rtf = _lookup_gpu_rtf(gpu_device_name)
    else:
        rtf = _CPU_RTF.get(model_name, _CPU_RTF["large-v3"])

    transcription_time = audio_duration * rtf
    if diarize:
        transcription_time *= 1 + _DIARIZATION_OVERHEAD

    return transcription_time


def _lookup_gpu_rtf(device_name: Optional[str]) -> float:
    """Look up GPU RTF from known GPU name patterns."""
    if not device_name:
        return _GPU_RTF_GENERIC
    lower = device_name.lower()
    for pattern, rtf in _GPU_RTF_BY_NAME.items():
        if pattern in lower:
            return rtf
    return _GPU_RTF_GENERIC


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    total = max(0, int(seconds))
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
