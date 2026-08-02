"""Report generation: assemble facts into structured Markdown with citations."""
import re
from datetime import datetime, timezone

from models import (
    ExtractedFact,
    Citation,
    ResearchReport,
    ReportMetadata,
    ReportSynthesis,
    SearchResult,
)
from report_labels import get_labels, report_language
from report_synthesis import fallback_synthesis
from source_snapshots import build_source_snapshots


def _slugify(text: str, now: datetime) -> str:
    """Convert text to URL-safe slug with timestamp suffix."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    if not slug:
        slug = "research"
    slug = slug[:60]
    return f"{slug}-{now.strftime('%Y%m%d-%H%M%S')}"


def _build_citations(facts: list[ExtractedFact]) -> list[Citation]:
    """Build citation index from extracted facts."""
    citations = []
    for i, fact in enumerate(facts, 1):
        highlight = fact.quoted_text[:100] if fact.quoted_text else fact.fact[:100]
        citations.append(Citation(
            index=i,
            source_name=fact.source_title,
            source_url=fact.source_url,
            quoted_text=fact.quoted_text,
            highlight_anchor=highlight.strip(),
        ))
    return citations


def _build_sources_markdown(citations: list[Citation]) -> list[str]:
    """Aggregate citations by unique URL for the Sources section."""
    from dedup import normalize_url

    by_url: dict[str, list[Citation]] = {}
    for citation in citations:
        key = normalize_url(citation.source_url)
        by_url.setdefault(key, []).append(citation)

    lines: list[str] = []
    for group in by_url.values():
        primary = group[0]
        indices = ", ".join(f"[^{c.index}]" for c in sorted(group, key=lambda c: c.index))
        quote = primary.quoted_text[:120] + ("..." if len(primary.quoted_text) > 120 else "")
        lines.append(
            f"- [{primary.source_name}]({primary.source_url}) — refs {indices} — *\"{quote}\"*"
        )
        lines.append("")
    return lines


def _truncate_signal(signal: str, max_len: int = 120) -> str:
    signal = signal.strip()
    if len(signal) <= max_len:
        return signal
    return signal[: max_len - 1].rstrip() + "…"


def _findings_table_markdown(
    synthesis: ReportSynthesis,
    heading: str = "Structured Findings",
    labels: dict[str, str] | None = None,
) -> list[str]:
    labels = labels or {}
    head = (
        f"| {labels.get('table_signal', 'Signal')} "
        f"| {labels.get('table_date', 'Date')} "
        f"| {labels.get('table_confidence', 'Confidence')} "
        f"| {labels.get('table_ref', 'Ref')} |"
    )
    lines = [
        f"## {heading}",
        "",
        head,
        "| --- | --- | --- | --- |",
    ]
    for row in synthesis.structured_findings:
        signal = _truncate_signal(row.signal.replace("|", "\\|"))
        date = row.date or "—"
        ref = f"[^{row.citation_index}]" if row.citation_index else "—"
        lines.append(
            f"| {signal} | {date} | {row.confidence} | {ref} |"
        )
    lines.append("")
    return lines


def _generate_markdown(
    topic: str,
    facts: list[ExtractedFact],
    citations: list[Citation],
    synthesis: ReportSynthesis,
    started_at: datetime,
    completed_at: datetime,
    report_type: str = "intelligence_brief",
) -> str:
    """Structured Markdown in the topic's language: thesis → sections → appendix."""
    labels = get_labels(topic)
    title = labels.get(report_type) or labels.get("intelligence_brief", "Intelligence Brief")
    thesis = (synthesis.thesis or synthesis.executive_summary or "").strip()
    lines = [
        f"# {title}：{topic}" if report_language(topic) == "zh" else f"# {title}: {topic}",
        "",
        "---",
        "",
        f"## {labels['conclusion']}",
        "",
        thesis or f"_{labels['no_conclusion']}_",
        "",
    ]

    if synthesis.key_takeaways:
        lines.extend([f"## {labels['takeaways']}", ""])
        lines.extend(f"- {t}" for t in synthesis.key_takeaways[:5])
        lines.append("")

    lines.extend(["---", "", f"## {labels['arguments']}", ""])

    if synthesis.arguments:
        for i, arg in enumerate(synthesis.arguments, 1):
            refs = " ".join(f"[^{n}]" for n in arg.citation_indices) or ""
            heading = (arg.heading or "").strip()
            if heading:
                lines.append(f"### {i}. {heading}")
                lines.append("")
            lines.append(f"**{arg.claim}** {refs}".rstrip())
            lines.append("")
            body = (arg.body or arg.detail or "").strip()
            if body:
                lines.append(body)
                lines.append("")
    else:
        lines.append(f"_{labels['no_arguments']}_")
        lines.append("")

    lines.extend(["---", ""])

    if synthesis.so_what:
        lines.extend([
            f"## {labels['so_what']}",
            "",
            synthesis.so_what,
            "",
            "---",
            "",
        ])

    if synthesis.gaps:
        lines.extend([
            f"## {labels['limits']}",
            "",
            synthesis.gaps,
            "",
            "---",
            "",
        ])

    if report_type == "investor_brief":
        if synthesis.fund_activity:
            lines.extend([
                f"## {labels['fund_activity']}",
                "",
                synthesis.fund_activity,
                "",
                "---",
                "",
            ])
        if synthesis.credit_risk_watch:
            lines.extend([
                f"## {labels['credit_risk_watch']}",
                "",
                synthesis.credit_risk_watch,
                "",
                "---",
                "",
            ])

    if synthesis.structured_findings:
        lines.extend(_findings_table_markdown(
            synthesis, heading=labels["signal_ledger"], labels=labels,
        ))
        lines.extend(["---", ""])

    if synthesis.coverage:
        lines.extend([
            f"## {labels['coverage']}",
            "",
            synthesis.coverage,
            "",
            "---",
            "",
        ])

    lines.extend([
        f"## {labels['sources']}",
        "",
    ])
    lines.extend(_build_sources_markdown(citations))

    # Run metadata belongs at the end — a brief must not open with process metrics
    unique_urls = len({f.source_url for f in facts})
    lines.extend([
        "---",
        "",
        f"## {labels['appendix_meta']}",
        "",
        f"- {labels['generated_at']}: {completed_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- {labels['fact_count']}: {len(facts)}",
        f"- {labels['url_count']}: {unique_urls}",
        "",
        "---",
        "",
        f"*{labels['footer']}*",
    ])

    return "\n".join(lines)


def generate_report(
    topic: str,
    facts: list[ExtractedFact],
    started_at: datetime = None,
    synthesis: ReportSynthesis | None = None,
    topics_searched: list[str] | None = None,
    fetched_results: list[SearchResult] | None = None,
    report_type: str = "intelligence_brief",
) -> ResearchReport:
    """Generate a complete ResearchReport from extracted facts."""
    now = datetime.now(timezone.utc)
    if started_at is None:
        started_at = now

    searched = topics_searched or [topic]
    if synthesis is None:
        synthesis = fallback_synthesis(topic, facts, searched)

    slug = _slugify(topic, now)
    citations = _build_citations(facts)
    markdown = _generate_markdown(
        topic, facts, citations, synthesis, started_at, now, report_type=report_type,
    )

    unique_urls = set(f.source_url for f in facts)
    metadata = ReportMetadata(
        execution_time_seconds=(now - started_at).total_seconds(),
        source_count=len(unique_urls),
        topics_searched=searched,
        started_at=started_at.isoformat(),
        completed_at=now.isoformat(),
    )

    snapshots = build_source_snapshots(fetched_results or [])

    return ResearchReport(
        topic=topic,
        slug=slug,
        report_type=report_type,
        facts=facts,
        citations=citations,
        markdown=markdown,
        thesis=synthesis.thesis or synthesis.executive_summary,
        arguments=list(synthesis.arguments),
        summary=synthesis.thesis or synthesis.executive_summary,
        key_takeaways=list(synthesis.key_takeaways),
        so_what=synthesis.so_what,
        structured_findings=synthesis.structured_findings,
        coverage=synthesis.coverage,
        gaps=synthesis.gaps,
        fund_activity=synthesis.fund_activity,
        credit_risk_watch=synthesis.credit_risk_watch,
        source_snapshots=snapshots,
        metadata=metadata,
    )
