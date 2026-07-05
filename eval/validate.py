"""Validate research reports against golden case expectations."""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from models import ResearchReport


@dataclass
class GoldenCase:
    id: str
    topic: str
    max_sources: int = 10
    min_sources: int = 3
    min_facts: int = 3
    required_keywords: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenCase":
        return cls(
            id=data["id"],
            topic=data["topic"],
            max_sources=int(data.get("max_sources", 10)),
            min_sources=int(data.get("min_sources", 3)),
            min_facts=int(data.get("min_facts", 3)),
            required_keywords=list(data.get("required_keywords") or []),
        )


def validate_report(report: ResearchReport, case: GoldenCase) -> list[str]:
    """Return a list of validation error messages (empty = pass)."""
    errors: list[str] = []

    if not report.markdown.strip():
        errors.append("report markdown is empty")

    unique_urls = {f.source_url for f in report.facts if f.source_url}
    if len(unique_urls) < case.min_sources:
        errors.append(
            f"expected >= {case.min_sources} unique source URLs, got {len(unique_urls)}"
        )

    if len(report.facts) < case.min_facts:
        errors.append(f"expected >= {case.min_facts} facts, got {len(report.facts)}")

    for i, fact in enumerate(report.facts, 1):
        if not fact.quoted_text.strip():
            errors.append(f"fact {i} missing quoted_text")
        if not fact.source_url.strip():
            errors.append(f"fact {i} missing source_url")

    haystack = report.markdown.lower()
    haystack += " " + " ".join(f.fact.lower() for f in report.facts)
    for keyword in case.required_keywords:
        if keyword.lower() not in haystack:
            errors.append(f"required keyword not found: {keyword!r}")

    return errors
