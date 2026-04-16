"""Gemma 4 via local Ollama — transcript correction and summary generation.

Configuration (environment variables):
  OLLAMA_BASE_URL   Ollama server URL              default: http://localhost:11434
  OLLAMA_MODEL      Model tag to use               default: gemma4:e4b
  OLLAMA_TIMEOUT    HTTP timeout in seconds        default: 300

Model recommendations (CPU-only):
  8 GB  RAM → gemma4:e2b  (fast, ~2–3 GB RAM)
  16 GB RAM → gemma4:e4b  (higher quality, ~4–5 GB RAM)
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
OLLAMA_TIMEOUT: float = float(os.environ.get("OLLAMA_TIMEOUT", "300"))

# Maximum transcript characters fed to the model in one call.
# Keeps memory usage bounded on small RAM setups.
_MAX_TRANSCRIPT_CHARS = 60_000
_CORRECTION_CONTEXT_CHARS = 500


# --------------------------------------------------------------------------- #
# Internal helper                                                              #
# --------------------------------------------------------------------------- #

async def _chat(
    messages: list[dict],
    model: Optional[str] = None,
) -> str:
    """Call Ollama's OpenAI-compatible chat completions endpoint."""
    url = f"{OLLAMA_BASE_URL}/v1/chat/completions"
    payload = {
        "model": model or OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

async def correct_transcript_chunk(
    chunk: str,
    prev_context: str = "",
    next_context: str = "",
    rough_context: str = "",
) -> str:
    """Ask Gemma 4 to correct one chunk of the final WhisperX transcript.

    Args:
        chunk:         The transcript segment to correct.
        prev_context:  Tail of the preceding chunk (for continuity).
        next_context:  Head of the following chunk (for continuity).
        rough_context: Corresponding portion of the rough rolling transcript
                       (used as a secondary reference for names / terms).
    """
    context_parts: list[str] = []
    if prev_context:
        context_parts.append(
            f"Vorhergehender Abschnitt (Kontext, nicht ändern):\n{prev_context}"
        )
    if next_context:
        context_parts.append(
            f"Nachfolgender Abschnitt (Kontext, nicht ändern):\n{next_context}"
        )
    if rough_context:
        context_parts.append(
            f"Live-Rohtranskript (unkorrigiert, nur als Referenz):\n{rough_context}"
        )

    preamble = "\n\n".join(context_parts)
    user_content = (
        f"{preamble}\n\n" if preamble else ""
    ) + f"Zu korrigierender Abschnitt:\n{chunk}"

    return await _chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein Spezialist für die Nachbearbeitung automatisch "
                    "erzeugter Transkripte. Korrigiere den gegebenen Abschnitt:\n"
                    "- Behebe Transkriptionsfehler (falsch erkannte Wörter, Eigennamen, "
                    "Fachbegriffe)\n"
                    "- Verbessere Zeichensetzung und Lesbarkeit\n"
                    "- Korrigiere fehlerhafte Sprecher-Zuordnungen anhand des Kontexts\n"
                    "- Behalte Bedeutung und Struktur vollständig bei\n"
                    "Gib NUR den korrigierten Text zurück – keine Erklärungen."
                ),
            },
            {"role": "user", "content": user_content},
        ]
    )


async def generate_summary(transcript: str) -> str:
    """Ask Gemma 4 to produce a structured summary of the full transcript."""
    truncated = transcript[:_MAX_TRANSCRIPT_CHARS]
    if len(transcript) > _MAX_TRANSCRIPT_CHARS:
        truncated += "\n\n[...Transkript gekürzt – nur Anfang verarbeitet...]"

    return await _chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "Du bist ein Assistent, der Transkripte von Audio-Aufnahmen "
                    "zusammenfasst. Erstelle eine strukturierte, prägnante "
                    "Zusammenfassung mit folgenden Abschnitten:\n"
                    "1. **Überblick** (2–3 Sätze)\n"
                    "2. **Hauptthemen** (Aufzählung)\n"
                    "3. **Wichtige Aussagen und Entscheidungen**\n"
                    "Gib NUR die Zusammenfassung zurück."
                ),
            },
            {
                "role": "user",
                "content": f"Bitte fasse dieses Transkript zusammen:\n\n{truncated}",
            },
        ]
    )
