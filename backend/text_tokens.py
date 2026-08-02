"""Language-aware tokenization for coverage / query expand (Wave 12h).

Chinese has no spaces — naive ``str.split()`` yields one giant token and breaks
brief coverage matching. Use CJK character n-grams plus Latin words.
"""

from __future__ import annotations

import re

_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9&.-]{1,}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_STOP_LATIN = frozenset({
    "a", "an", "and", "the", "of", "in", "for", "to", "or", "vs", "versus",
    "on", "at", "by", "with", "from", "that", "this", "into", "over", "under",
})
_STOP_CJK = frozenset({
    "以及", "或者", "还有", "一个", "我们", "他们", "可以", "进行", "相关",
    "包括", "如果", "因为", "所以", "但是", "然后", "这个", "那个",
})


def tokens(text: str, *, max_tokens: int = 24) -> list[str]:
    """Return distinctive tokens: Latin words + CJK 2–4grams (lowercased Latin)."""
    if not (text or "").strip():
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _add(tok: str) -> None:
        key = tok.lower() if re.match(r"^[A-Za-z]", tok) else tok
        if not key or key in seen:
            return
        if key in _STOP_LATIN or key in _STOP_CJK:
            return
        seen.add(key)
        out.append(tok if not re.match(r"^[A-Za-z]", tok) else tok.lower())

    for m in _LATIN_RE.finditer(text):
        w = m.group(0)
        if len(w) >= 2:
            _add(w)
        if len(out) >= max_tokens:
            return out

    for m in _CJK_RE.finditer(text):
        span = m.group(0)
        if len(span) <= 4:
            _add(span)
        else:
            for n in (2, 3, 4):
                for i in range(0, len(span) - n + 1):
                    _add(span[i : i + n])
                    if len(out) >= max_tokens:
                        return out
        if len(out) >= max_tokens:
            return out

    return out[:max_tokens]


def keyword_list(*parts: str, max_tokens: int = 16) -> list[str]:
    """Merge tokens from several text parts (title, goal, detail, entities)."""
    merged: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for t in tokens(part or "", max_tokens=max_tokens):
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(t)
            if len(merged) >= max_tokens:
                return merged
    return merged
