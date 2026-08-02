"""Bilingual report skeleton labels (Wave 12h Step 88)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_LABELS_PATH = Path(__file__).resolve().parent / "report_labels.yaml"
_labels_cache: dict[str, dict[str, str]] | None = None
_labels_cache_key: float | None = None


def _load() -> dict[str, dict[str, str]]:
    global _labels_cache, _labels_cache_key
    try:
        mtime = _LABELS_PATH.stat().st_mtime
    except OSError:
        return {}
    if _labels_cache is not None and _labels_cache_key == mtime:
        return _labels_cache
    data: dict[str, Any] = yaml.safe_load(_LABELS_PATH.read_text(encoding="utf-8")) or {}
    out = {
        str(lang): {str(k): str(v) for k, v in (values or {}).items()}
        for lang, values in data.items()
    }
    _labels_cache = out
    _labels_cache_key = mtime
    return out


def clear_labels_cache() -> None:
    global _labels_cache, _labels_cache_key
    _labels_cache = None
    _labels_cache_key = None


def report_language(topic: str) -> str:
    """Report skeleton language — Chinese topic means a Chinese skeleton."""
    return "zh" if re.search(r"[\u4e00-\u9fff]", topic or "") else "en"


def get_labels(topic_or_lang: str) -> dict[str, str]:
    """Labels for a topic (or an explicit 'zh' / 'en'), falling back to English."""
    labels = _load()
    lang = topic_or_lang if topic_or_lang in labels else report_language(topic_or_lang)
    merged = dict(labels.get("en") or {})
    merged.update(labels.get(lang) or {})
    return merged
