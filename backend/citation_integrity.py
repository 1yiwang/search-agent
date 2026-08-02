"""Deterministic citation gate for written sections (Wave 12h Step 89).

Pass A decides which fact belongs to which slot; Pass B may only cite within that
assignment. Nothing here invents or auto-fills citations — a claim that cannot be
traced back to an assigned fact is demoted, never quietly backfilled.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from models import EvidenceDraft, ExtractedFact, ReportArgument

_CITE_RE = re.compile(r"\[\^?(\d{1,3})\]")
_NUMBER_RE = re.compile(r"\d+(?:[.,\u00a0]\d+)*\s*%?")

# One citation per this many characters of prose (soft floor)
_DENSITY_CHARS = 150

ISSUE_TEXT = {
    "zh": {
        "out_of_slot": "引用超出本方向分配的证据",
        "no_citation": "正文没有可核验的引用",
        "unbacked_number": "数字在被引原文中找不到",
        "low_density": "引用密度偏低",
    },
    "en": {
        "out_of_slot": "cited facts outside this direction's assignment",
        "no_citation": "no verifiable citation in the section",
        "unbacked_number": "figures not found in the cited excerpts",
        "low_density": "citation density below floor",
    },
}


@dataclass
class CitationIssue:
    slot_id: str
    kind: str
    detail: str = ""


@dataclass
class IntegrityReport:
    arguments: list[ReportArgument]
    issues: list[CitationIssue] = field(default_factory=list)

    def summary(self, lang: str = "zh") -> str:
        """Plain-language note for the Limits section."""
        if not self.issues:
            return ""
        text = ISSUE_TEXT.get(lang) or ISSUE_TEXT["en"]
        by_kind: dict[str, list[str]] = {}
        for issue in self.issues:
            by_kind.setdefault(issue.kind, []).append(issue.slot_id or "?")
        sep, joiner = ("；", "、") if lang == "zh" else ("; ", ", ")
        parts = [
            f"{text.get(kind, kind)}（{joiner.join(dict.fromkeys(slots))}）"
            if lang == "zh"
            else f"{text.get(kind, kind)} ({joiner.join(dict.fromkeys(slots))})"
            for kind, slots in by_kind.items()
        ]
        return sep.join(parts)


def _cited_indices(text: str) -> list[int]:
    out: list[int] = []
    for m in _CITE_RE.finditer(text or ""):
        idx = int(m.group(1))
        if idx not in out:
            out.append(idx)
    return out


def _strip_citations(text: str, drop: set[int]) -> str:
    if not drop:
        return text

    def repl(m: re.Match[str]) -> str:
        return "" if int(m.group(1)) in drop else m.group(0)

    cleaned = _CITE_RE.sub(repl, text or "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return re.sub(r"\s+([。，；.,;])", r"\1", cleaned).strip()


def _normalize_digits(text: str) -> str:
    return re.sub(r"[,\s\u00a0]", "", text or "")


def _claim_numbers(text: str) -> list[str]:
    """Numbers a reader would want backed — skips bare single digits."""
    out: list[str] = []
    for m in _NUMBER_RE.finditer(text or ""):
        raw = m.group(0).strip()
        digits = _normalize_digits(raw)
        if "%" not in digits and len(re.sub(r"\D", "", digits)) < 2:
            continue
        if digits not in out:
            out.append(digits)
    return out


def _cited_corpus(indices: list[int], facts: list[ExtractedFact]) -> str:
    parts: list[str] = []
    for idx in indices:
        if 1 <= idx <= len(facts):
            fact = facts[idx - 1]
            parts.append(fact.fact or "")
            parts.append(fact.quoted_text or "")
    return _normalize_digits(" ".join(parts))


def enforce_citation_integrity(
    arguments: list[ReportArgument],
    draft: EvidenceDraft,
    facts: list[ExtractedFact],
    *,
    lang: str = "zh",
) -> IntegrityReport:
    """Trim citations to the Pass A assignment and demote unverifiable prose."""
    allowed_by_slot = {s.slot_id: set(s.fact_indices) for s in draft.slots}
    issues: list[CitationIssue] = []
    out: list[ReportArgument] = []

    for arg in arguments:
        allowed = allowed_by_slot.get(arg.slot_id, set())
        body = arg.body or ""
        claim = arg.claim or ""
        cited = _cited_indices(f"{claim} {body}")
        stray = {n for n in cited if n not in allowed}
        if stray:
            issues.append(CitationIssue(
                arg.slot_id, "out_of_slot", ", ".join(str(n) for n in sorted(stray)),
            ))
            body = _strip_citations(body, stray)
            claim = _strip_citations(claim, stray)

        kept = [n for n in cited if n in allowed]
        arg.citation_indices = kept  # never backfill from the slot assignment
        arg.body = body
        arg.claim = claim

        prose = f"{claim} {body}".strip()
        has_prose = bool(re.sub(r"\s+", "", prose))
        if not kept and has_prose and allowed:
            issues.append(CitationIssue(arg.slot_id, "no_citation"))
            arg.confidence = "low"
        elif kept:
            corpus = _cited_corpus(kept, facts)
            unbacked = [n for n in _claim_numbers(prose) if n not in corpus]
            if unbacked:
                issues.append(CitationIssue(
                    arg.slot_id, "unbacked_number", ", ".join(unbacked[:5]),
                ))
                arg.confidence = "low"
            length = len(re.sub(r"\s+", "", body))
            if length >= _DENSITY_CHARS * 2 and len(kept) < length // _DENSITY_CHARS:
                issues.append(CitationIssue(arg.slot_id, "low_density", str(len(kept))))
                if arg.confidence == "high":
                    arg.confidence = "medium"
        out.append(arg)

    return IntegrityReport(arguments=out, issues=issues)
