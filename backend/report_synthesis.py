"""LLM synthesis for executive summary and structured findings (Phase 0–2)."""
import json
import re

from llm_context import get_openai_client, get_request_keys
from models import ExtractedFact, ReportSynthesis, StructuredFinding
from sources.pd_registry import has_private_debt_intent

SYNTHESIS_PROMPT = """You write the narrative layer of a research intelligence brief.

Research topic: {topic}
Topics searched: {topics}

Verified facts (citation index matches footnote [^n]):
{facts_json}

Instructions:
1. Write in the SAME language as the research topic (Chinese topic → Chinese prose).
2. Preserve German/French proper nouns and terms from sources when they are more precise.
3. Use ONLY the facts above — do not add outside knowledge.
4. executive_summary: 3–5 sentences answering the topic directly. If facts are off-topic, outdated, or explicitly say the answer was not found, say so plainly instead of inventing an answer.
5. structured_findings: one row per distinct entity/signal; map each row to citation_index from facts.
6. coverage: what was searched and what types of sources were covered.
7. gaps: what may still be missing, wrong timeframe, paywalled, or unverified — be specific when facts contradict the topic.

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


INVESTOR_BRIEF_PROMPT = """You write an investor-facing private markets intelligence brief (allocator / product team audience).

Research topic: {topic}
Topics searched: {topics}

Verified facts (citation index matches footnote [^n]):
{facts_json}

Instructions:
1. Write in the SAME language as the research topic (English topic → English prose).
2. Preserve proper nouns from sources (fund names, managers, regulators).
3. Use ONLY the facts above — do not add outside knowledge.
4. executive_summary: 4–6 sentences. Lead with the main conclusion; end with key risk or data gap. Cover fundraising, deployment, credit risk, and relative value only as supported by facts.
5. structured_findings: one row per distinct entity/signal (funds, managers, market trends). Keep signal under ~120 characters. Include signal_type when clear: fund_close, fundraise, deployment, refinance, default_distress, spread_market, regulatory, product_launch, team_move, or other.
6. fund_activity: paragraph on fund launches, closes, ELTIF/BDC/evergreen activity, or product milestones — cite fact indices inline as [^n] where helpful.
7. credit_risk_watch: paragraph on defaults, leverage, spreads, borrower fundamentals — only from facts.
8. coverage: sources and geographies covered.
9. gaps: paywalled data, missing deal-level terms, or timeframe limits.

Return ONLY valid JSON:
```json
{{
  "executive_summary": "...",
  "structured_findings": [
    {{
      "entity": "Fund or market actor",
      "signal": "What happened",
      "date": "YYYY-MM or empty",
      "confidence": "high|medium|low",
      "citation_index": 1,
      "signal_type": "fundraise",
      "entity_type": "fund"
    }}
  ],
  "fund_activity": "...",
  "credit_risk_watch": "...",
  "coverage": "...",
  "gaps": "..."
}}
```"""


def detect_report_type(topic: str) -> str:
    """Choose report template from topic intent."""
    if has_private_debt_intent(topic):
        return "investor_brief"
    return "intelligence_brief"


def _prompt_for_report_type(report_type: str) -> str:
    if report_type == "investor_brief":
        return INVESTOR_BRIEF_PROMPT
    return SYNTHESIS_PROMPT


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


def _normalize_findings(
    raw: list,
    fact_count: int,
    facts: list[ExtractedFact] | None = None,
) -> list[StructuredFinding]:
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
        signal_type = str(item.get("signal_type") or "").strip()
        entity_type = str(item.get("entity_type") or "").strip()
        # Prefer extraction-time classification when synthesis leaves blanks
        if facts and 1 <= idx <= len(facts):
            fact = facts[idx - 1]
            if not signal_type or signal_type == "other":
                fact_sig = getattr(fact, "signal_type", "") or ""
                if fact_sig and fact_sig != "other":
                    signal_type = fact_sig
            if not entity_type or entity_type == "other":
                fact_ent = getattr(fact, "entity_type", "") or ""
                if fact_ent and fact_ent != "other":
                    entity_type = fact_ent
        findings.append(StructuredFinding(
            entity=str(item.get("entity") or "").strip(),
            signal=str(item.get("signal") or "").strip(),
            date=str(item.get("date") or "").strip(),
            confidence=conf,
            citation_index=idx,
            signal_type=signal_type,
            entity_type=entity_type,
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
            date=getattr(fact, "event_date", "") or "",
            confidence=fact.confidence,
            citation_index=i + 1,
            signal_type=getattr(fact, "signal_type", "") or "other",
            entity_type=getattr(fact, "entity_type", "") or "other",
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
    report_type: str | None = None,
) -> ReportSynthesis:
    """Generate executive summary and structured table from verified facts."""
    if report_type is None:
        report_type = detect_report_type(topic)

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
            "event_date": f.event_date,
            "source_title": f.source_title,
            "source_url": f.source_url,
            "quoted_excerpt": f.quoted_text[:200],
            "signal_type": getattr(f, "signal_type", "") or "other",
            "entity_type": getattr(f, "entity_type", "") or "other",
        }
        for i, f in enumerate(facts)
    ]

    prompt_template = _prompt_for_report_type(report_type)

    try:
        response = await get_openai_client().chat.completions.create(
            model=keys.llm_model,
            messages=[{
                "role": "user",
                "content": prompt_template.format(
                    topic=topic,
                    topics=", ".join(topics_searched),
                    facts_json=json.dumps(facts_payload, ensure_ascii=False, indent=2),
                ),
            }],
            temperature=0.3,
            max_tokens=2048,
        )
        raw = _parse_synthesis_json(response.choices[0].message.content or "")
        findings = _normalize_findings(
            raw.get("structured_findings") or [], len(facts), facts=facts,
        )
        if not findings:
            findings = fallback_synthesis(topic, facts, topics_searched).structured_findings

        fallback = fallback_synthesis(topic, facts, topics_searched)
        return ReportSynthesis(
            executive_summary=str(raw.get("executive_summary") or "").strip()
            or fallback.executive_summary,
            structured_findings=findings,
            coverage=str(raw.get("coverage") or "").strip() or fallback.coverage,
            gaps=str(raw.get("gaps") or "").strip() or fallback.gaps,
            fund_activity=str(raw.get("fund_activity") or "").strip(),
            credit_risk_watch=str(raw.get("credit_risk_watch") or "").strip(),
        )
    except Exception:
        return fallback_synthesis(topic, facts, topics_searched)
