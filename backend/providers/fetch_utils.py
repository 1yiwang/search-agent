"""Shared helpers for fetch providers."""
from config import config


def truncate(text: str) -> str:
    max_chars = config.fetch_max_chars
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[... content truncated ...]"
    return text


def is_fetch_failure(text: str) -> bool:
    """True when fetch did not return usable page content."""
    if not text or not text.strip():
        return True
    stripped = text.strip()
    return stripped.startswith("[Failed to fetch") or stripped.startswith("Error:")
