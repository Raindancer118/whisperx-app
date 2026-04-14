"""GPU detection and device selection for WhisperX-App."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm

console = Console()


def detect_hardware() -> dict:
    """Return information about available compute hardware.

    Returns a dict with keys:
      - cuda (bool): whether CUDA is available
      - device_name (str | None): GPU name if available
      - vram_gb (float | None): approximate VRAM in GB
    """
    try:
        import torch

        cuda = torch.cuda.is_available()
        device_name = torch.cuda.get_device_name(0) if cuda else None
        vram_gb: float | None = None
        if cuda:
            props = torch.cuda.get_device_properties(0)
            vram_gb = round(props.total_memory / (1024**3), 1)
        return {"cuda": cuda, "device_name": device_name, "vram_gb": vram_gb}
    except ImportError:
        return {"cuda": False, "device_name": None, "vram_gb": None}


def select_device(preference: str = "auto") -> tuple[str, str]:
    """Determine the device and compute type to use for transcription.

    Args:
        preference: "auto" (detect and prompt), "cpu" (force CPU), "cuda" (force GPU)

    Returns:
        Tuple of (device, compute_type) where:
          - device is "cuda" or "cpu"
          - compute_type is "float16" (GPU) or "int8" (CPU)
    """
    if preference == "cpu":
        console.print("[dim]Gerät: CPU (erzwungen)[/dim]")
        return "cpu", "int8"

    if preference == "cuda":
        hw = detect_hardware()
        if not hw["cuda"]:
            console.print("[yellow]CUDA angefordert, aber keine GPU gefunden. Fallback auf CPU.[/yellow]")
            return "cpu", "int8"
        console.print(f"[dim]Gerät: {hw['device_name']} (erzwungen)[/dim]")
        return "cuda", "float16"

    # auto: detect and ask
    hw = detect_hardware()
    if not hw["cuda"]:
        console.print("[dim]Kein GPU gefunden — verwende CPU.[/dim]")
        return "cpu", "int8"

    vram_info = f" ({hw['vram_gb']} GB VRAM)" if hw["vram_gb"] else ""
    console.print(f"\n[cyan]GPU erkannt:[/cyan] {hw['device_name']}{vram_info}")

    use_gpu = Confirm.ask("GPU für Transkription verwenden?", default=True)
    if use_gpu:
        return "cuda", "float16"
    return "cpu", "int8"
