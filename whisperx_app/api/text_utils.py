"""Text utility functions shared between api and worker."""

from __future__ import annotations


def split_at_paragraphs(text: str, chunk_size: int) -> list[str]:
    """Split *text* into chunks of ≤ *chunk_size* chars at paragraph boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        split_at = text.rfind("\n\n", start, end)
        if split_at == -1:
            split_at = text.rfind("\n", start, end)
        if split_at == -1 or split_at == start:
            split_at = end
        chunks.append(text[start:split_at])
        if split_at == end:
            start = end
        elif text[split_at: split_at + 2] == "\n\n":
            start = split_at + 2
        else:
            start = split_at + 1
    return [c.strip() for c in chunks if c.strip()]
