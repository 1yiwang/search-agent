"""Offline eval L1 (brief directions) + L2 (writing contract) — no network, no LLM.

Usage (from repo root):
    backend/.venv/Scripts/python.exe -m eval.offline
    backend/.venv/Scripts/python.exe -m eval.offline --layer l2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402

from brief_rubric import check_instruction, harvest_entities  # noqa: E402
from citation_integrity import enforce_citation_integrity  # noqa: E402
from models import (  # noqa: E402
    BriefDimension,
    EvidenceDraft,
    EvidenceDraftSlot,
    ExtractedFact,
    ReportArgument,
    ResearchBrief,
)
from report_labels import get_labels, report_language  # noqa: E402
from report_synthesis import check_thesis, fallback_synthesis  # noqa: E402
from reporter import generate_report  # noqa: E402

_FIXTURES = _REPO_ROOT / "eval" / "fixtures"

_ENGLISH_HEADINGS = ("## Conclusion", "## Arguments", "## Limits", "## Sources", "## Coverage")


def _load_fixture(name: str) -> dict:
    return yaml.safe_load((_FIXTURES / name).read_text(encoding="utf-8")) or {}


def _brief_from_fixture(data: dict) -> ResearchBrief:
    return ResearchBrief(
        topic=data["topic"],
        framework_id=data.get("framework_id", ""),
        problem_restatement=data.get("problem_restatement", ""),
        dimensions=[
            BriefDimension(
                title=d["title"],
                research_goal=d.get("research_goal", ""),
                direction_detail=d.get("direction_detail", ""),
                queries=list(d.get("queries") or []),
                priority=int(d.get("priority", i + 1)),
                phase_id=d.get("phase_id", ""),
                direction_id=d.get("direction_id", d.get("phase_id", "")),
                must_answer=list(d.get("must_answer") or []),
            )
            for i, d in enumerate(data.get("dimensions") or [])
        ],
    )


def _facts_from_fixture(data: dict) -> list[ExtractedFact]:
    return [
        ExtractedFact(
            fact=f["fact"],
            source_url=f["source_url"],
            source_title=f.get("source_title", ""),
            quoted_text=f.get("quoted_text", ""),
            confidence=f.get("confidence", "medium"),
        )
        for f in data.get("facts") or []
    ]


def run_l1() -> list[str]:
    """Every approved direction must be a usable, entity-bearing instruction."""
    errors: list[str] = []
    for path in sorted(_FIXTURES.glob("brief_*.yaml")):
        data = _load_fixture(path.name)
        brief = _brief_from_fixture(data)
        min_entities = int(data.get("min_entities_per_direction", 1))
        for dim in brief.dimensions:
            label = f"{path.name}/{dim.direction_id or dim.title}"
            verdict = check_instruction(dim.direction_detail, brief.topic)
            if not verdict.ok:
                errors.append(f"L1 {label}: instruction rejected ({', '.join(verdict.reasons)})")
            if len(harvest_entities(dim.direction_detail)) < min_entities:
                errors.append(f"L1 {label}: fewer than {min_entities} entities")
            if not dim.direction_id:
                errors.append(f"L1 {label}: missing direction_id")
        ids = [d.direction_id for d in brief.dimensions]
        if len(set(ids)) != len(ids):
            errors.append(f"L1 {path.name}: duplicate direction_id {ids}")
    return errors


def run_l2() -> list[str]:
    """Fixed facts + brief must produce a lawful report without calling out."""
    errors: list[str] = []
    for path in sorted(_FIXTURES.glob("writing_*.yaml")):
        data = _load_fixture(path.name)
        brief = _brief_from_fixture(data)
        facts = _facts_from_fixture(data)
        searched = list(data.get("topics_searched") or [brief.topic])

        synthesis = fallback_synthesis(brief.topic, facts, searched, brief=brief)
        name = path.name

        if len(synthesis.arguments) != len(brief.dimensions):
            errors.append(
                f"L2 {name}: {len(synthesis.arguments)} sections for "
                f"{len(brief.dimensions)} directions"
            )
        verdict = check_thesis(synthesis.thesis, brief.topic)
        if not verdict.ok:
            errors.append(f"L2 {name}: thesis gate failed ({', '.join(verdict.reasons)})")
        if synthesis.citation_issues:
            errors.append(f"L2 {name}: citation issues {synthesis.citation_issues}")
        for arg in synthesis.arguments:
            for idx in arg.citation_indices:
                if not 1 <= idx <= len(facts):
                    errors.append(f"L2 {name}/{arg.slot_id}: citation [{idx}] out of range")

        report = generate_report(brief.topic, facts, synthesis=synthesis)
        if report_language(brief.topic) == "zh":
            for heading in _ENGLISH_HEADINGS:
                if heading in report.markdown:
                    errors.append(f"L2 {name}: English heading {heading} in Chinese report")
            labels = get_labels(brief.topic)
            if f"## {labels['conclusion']}" not in report.markdown:
                errors.append(f"L2 {name}: missing Chinese conclusion heading")
        head = report.markdown.split("---", 1)[0]
        if "facts from" in head or "Generated:" in head:
            errors.append(f"L2 {name}: process metrics in the report header")

        errors.extend(_check_gate_rejects(brief, facts))
    return errors


def _check_gate_rejects(brief: ResearchBrief, facts: list[ExtractedFact]) -> list[str]:
    """The citation gate must catch stray refs, missing refs and invented numbers."""
    errors: list[str] = []
    if not brief.dimensions or not facts:
        return errors
    slot_id = brief.dimensions[0].direction_id or brief.dimensions[0].phase_id or "dim_0"
    draft = EvidenceDraft(
        topic_restatement=brief.topic,
        outline_id=brief.framework_id,
        slots=[EvidenceDraftSlot(slot_id=slot_id, title="s", fact_indices=[1], required=True)],
    )
    probes = [
        (ReportArgument(claim="有结论。", body="正文 [1] 与越界引用 [99]", slot_id=slot_id), "out_of_slot"),
        (ReportArgument(claim="有结论。", body="正文没有任何引用标记。", slot_id=slot_id), "no_citation"),
        (
            ReportArgument(claim="有结论。", body="份额高达 98.7% [1]", slot_id=slot_id),
            "unbacked_number",
        ),
    ]
    for arg, expected in probes:
        result = enforce_citation_integrity([arg], draft, facts, lang="zh")
        kinds = {i.kind for i in result.issues}
        if expected not in kinds:
            errors.append(f"L2 gate: expected {expected}, got {sorted(kinds) or 'none'}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline brief/writing eval")
    parser.add_argument("--layer", choices=["l1", "l2", "all"], default="all")
    args = parser.parse_args()

    errors: list[str] = []
    if args.layer in ("l1", "all"):
        errors.extend(run_l1())
    if args.layer in ("l2", "all"):
        errors.extend(run_l2())

    if errors:
        print(f"FAIL — {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"PASS — offline eval ({args.layer}) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
