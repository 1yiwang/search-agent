"""LLM synthesis for executive summary and structured findings (Phase 0)."""
import json
import re

from llm_context import get_openai_client, get_request_keys
from models import ExtractedFact, ReportSynthesis, StructuredFinding

SYNTHESIS_PROMPT = """You write the narrative layer of a research intelligence brief.

Research topic: {topic}
Topics searched: {topics}

Verified facts (citation index matches footnote [^n]):
{facts_json}

Instructions:
1. Write in the SAME language as the research topic (Chinese topic → Chinese prose).
2. Preserve German/French proper nouns and terms from sources when they are more precise.
3. Use ONLY the facts above — do not add outside knowledge.
4. executive_summary: 3–5 sentences answering the topic directly.
5. structured_findings: one row per distinct entity/signal; map each row to citation_index from facts.
6. coverage: what was searched and what types of sources were covered.
7. gaps: what may still be missing or unverified.

Return ONLY valid JSON:
```json
{{
  "executive_summary": "...",
  "structured_findings": [
    {{
      "entity": "Company or fund name",
      "signal": "Funding round, hiring, event, etc.",
      "date": "YYYY-MM or YYYY or empty string",
      "confidence": "high|medium|low",
      "citation_index": 1
    }}
  ],
  "coverage": "...",
  "gaps": "..."
}}
```"""


def _topic_language_hint(topic: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", topic):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", topic):
        return "de"
    return "en"


def _parse_synthesis_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3].strip()
    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _normalize_findings(raw: list, fact_count: int) -> list[StructuredFinding]:
    findings: list[StructuredFinding] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        idx = int(item.get("citation_index") or 0)
        if idx < 1 or idx > fact_count:
            idx = min(len(findings) + 1, fact_count) if fact_count else 0
        conf = str(item.get("confidence") or "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        findings.append(StructuredFinding(
            entity=str(item.get("entity") or "").strip(),
            signal=str(item.get("signal") or "").strip(),
            date=str(item.get("date") or "").strip(),
            confidence=conf,
            citation_index=idx,
        ))
    return findings


def fallback_synthesis(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
) -> ReportSynthesis:
    """Deterministic summary when LLM is unavailable."""
    if not facts:
        return ReportSynthesis(
            executive_summary="No verified facts were extracted for this topic.",
            coverage=f"Searched: {', '.join(topics_searched)}",
            gaps="No sources returned usable content.",
        )

    lang = _topic_language_hint(topic)
    if lang == "zh":
        summary = f"本报告围绕「{topic}」整理了 {len(facts)} 条已验证事实，来自 {len({f.source_url for f in facts})} 个独立来源。"
        coverage = f"已检索主题：{'、'.join(topics_searched)}。"
        gaps = "可能遗漏未公开或需订阅的信源；请以原文引用为准。"
    else:
        summary = (
            f"This brief covers {len(facts)} verified facts on «{topic}» "
            f"from {len({f.source_url for f in facts})} unique sources."
        )
        coverage = f"Topics searched: {', '.join(topics_searched)}."
        gaps = "Non-public or paywalled sources may be missing; verify via citations."

    structured = [
        StructuredFinding(
            entity=fact.fact[:60].split("—")[0].strip() or fact.source_title[:40],
            signal=fact.fact,
            date="",
            confidence=fact.confidence,
            citation_index=i + 1,
        )
        for i, fact in enumerate(facts[:15])
    ]

    return ReportSynthesis(
        executive_summary=summary,
        structured_findings=structured,
        coverage=coverage,
        gaps=gaps,
    )


async def synthesize_report(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
) -> ReportSynthesis:
    """Generate executive summary and structured table from verified facts."""
    if not facts:
        return fallback_synthesis(topic, facts, topics_searched)

    keys = get_request_keys()
    if not keys or not keys.llm_api_key:
        return fallback_synthesis(topic, facts, topics_searched)

    facts_payload = [
        {
            "citation_index": i + 1,
            "fact": f.fact,
            "confidence": f.confidence,
            "source_title": f.source_title,
            "source_url": f.source_url,
            "quoted_excerpt": f.quoted_text[:200],
        }
        for i, f in enumerate(facts)
    ]

    try:
        response = await get_openai_client().chat.completions.create(
            model=keys.llm_model,
            messages=[{
                "role": "user",
                "content": SYNTHESIS_PROMPT.format(
                    topic=topic,
                    topics=", ".join(topics_searched),
                    facts_json=json.dumps(facts_payload, ensure_ascii=False, indent=2),
                ),
            }],
            temperature=0.3,
            max_tokens=2048,
        )
        raw = _parse_synthesis_json(response.choices[0].message.content or "")
        findings = _normalize_findings(raw.get("structured_findings") or [], len(facts))
        if not findings:
            findings = fallback_synthesis(topic, facts, topics_searched).structured_findings

        fallback = fallback_synthesis(topic, facts, topics_searched)
        return ReportSynthesis(
            executive_summary=str(raw.get("executive_summary") or "").strip()
            or fallback.executive_summary,
            structured_findings=findings,
            coverage=str(raw.get("coverage") or "").strip() or fallback.coverage,
            gaps=str(raw.get("gaps") or "").strip() or fallback.gaps,
        )
    except Exception:
        return fallback_synthesis(topic, facts, topics_searched)
