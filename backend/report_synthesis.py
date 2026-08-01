"""LLM synthesis: thesis + arguments narrative (Wave 12b) + signal ledger."""
import json
import re

from llm_context import get_openai_client, get_request_keys
from models import ExtractedFact, ReportArgument, ReportSynthesis, StructuredFinding
from sources.pd_registry import has_private_debt_intent

SYNTHESIS_PROMPT = """You write the narrative layer of a research intelligence brief.

Research topic: {topic}
Topics searched: {topics}

Verified facts (citation index matches footnote [^n]):
{facts_json}

Instructions:
1. Write prose in the SAME language as the research topic (Chinese topic → Chinese).
2. Prefer local-market sources in EN/DE/FR/IT for Switzerland/DACH topics.
3. Preserve regulator/operator proper nouns from sources.
4. Use ONLY the facts above — do not invent claims.
5. thesis: EXACTLY ONE sentence that answers the topic. No multi-sentence paragraph.
6. arguments: 3–6 supporting points, ordered by importance. Each has:
   - claim: one sentence
   - detail: optional one short sentence (or "")
   - citation_indices: list of fact citation_index numbers that support the claim
   - confidence: high|medium|low (from supporting facts)
7. structured_findings: compact signal ledger (one row per distinct entity/signal) for an appendix table — not the main narrative.
8. coverage: what was searched / source types / languages.
9. gaps: what is still missing, off-topic, or unverified — be specific.
10. If facts are off-topic or empty of answer, thesis must say so plainly.

Return ONLY valid JSON:
```json
{{
  "thesis": "One sentence conclusion.",
  "arguments": [
    {{
      "claim": "Supporting point.",
      "detail": "",
      "citation_indices": [1, 2],
      "confidence": "high"
    }}
  ],
  "structured_findings": [
    {{
      "entity": "Name",
      "signal": "What happened",
      "date": "YYYY-MM or empty",
      "confidence": "high|medium|low",
      "citation_index": 1
    }}
  ],
  "coverage": "...",
  "gaps": "..."
}}
```"""


INVESTOR_BRIEF_PROMPT = """You write an investor-facing private markets intelligence brief.

Research topic: {topic}
Topics searched: {topics}

Verified facts (citation index matches footnote [^n]):
{facts_json}

Instructions:
1. Same language as the topic. Use ONLY the facts above.
2. thesis: EXACTLY ONE sentence — the main investment/market takeaway.
3. arguments: 3–6 ordered points (fundraising, deployment, spreads, credit risk, products, relative value — only if supported). Each with claim, detail, citation_indices, confidence.
4. structured_findings: signal ledger rows with signal_type/entity_type when clear.
5. fund_activity / credit_risk_watch: short paragraphs for appendix (optional if covered in arguments).
6. coverage and gaps: specific.

Return ONLY valid JSON:
```json
{{
  "thesis": "One sentence.",
  "arguments": [
    {{
      "claim": "...",
      "detail": "",
      "citation_indices": [1],
      "confidence": "medium"
    }}
  ],
  "structured_findings": [
    {{
      "entity": "Fund or actor",
      "signal": "What happened",
      "date": "",
      "confidence": "medium",
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


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    for sep in ("。", "！", "？", ". ", "! ", "? "):
        if sep in text:
            part = text.split(sep, 1)[0].strip()
            if sep.strip() in ("。", "！", "？"):
                return part + sep.strip()
            return part + "."
    return text


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


def _normalize_arguments(
    raw: list,
    fact_count: int,
    facts: list[ExtractedFact] | None = None,
) -> list[ReportArgument]:
    args: list[ReportArgument] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        indices: list[int] = []
        for v in item.get("citation_indices") or []:
            try:
                idx = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= fact_count and idx not in indices:
                indices.append(idx)
        # Legacy single citation_index
        if not indices and item.get("citation_index"):
            try:
                idx = int(item["citation_index"])
                if 1 <= idx <= fact_count:
                    indices = [idx]
            except (TypeError, ValueError):
                pass
        conf = str(item.get("confidence") or "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        if facts and indices:
            ranks = {"high": 3, "medium": 2, "low": 1}
            confs = [
                (facts[i - 1].confidence or "medium").lower()
                for i in indices
                if 1 <= i <= len(facts)
            ]
            if confs:
                # Use lowest supporting confidence (conservative)
                conf = min(confs, key=lambda c: ranks.get(c, 0))
                if conf not in ranks:
                    conf = "medium"
        args.append(ReportArgument(
            claim=claim,
            detail=str(item.get("detail") or "").strip(),
            citation_indices=indices[:6],
            confidence=conf,
        ))
        if len(args) >= 8:
            break
    return args


def _arguments_from_facts(facts: list[ExtractedFact]) -> list[ReportArgument]:
    ordered = sorted(
        enumerate(facts),
        key=lambda pair: {"high": 0, "medium": 1, "low": 2}.get(
            (pair[1].confidence or "medium").lower(), 1
        ),
    )
    args: list[ReportArgument] = []
    for i, fact in ordered[:6]:
        args.append(ReportArgument(
            claim=fact.fact.strip(),
            detail="",
            citation_indices=[i + 1],
            confidence=fact.confidence if fact.confidence in ("high", "medium", "low") else "medium",
        ))
    return args


def fallback_synthesis(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
) -> ReportSynthesis:
    """Deterministic thesis/arguments when LLM is unavailable."""
    searched_preview = ", ".join(topics_searched[:8]) if topics_searched else "(none recorded)"
    more = f" (+{len(topics_searched) - 8} more)" if len(topics_searched) > 8 else ""

    if not facts:
        lang = _topic_language_hint(topic)
        if lang == "zh":
            thesis = f"未能就「{topic}」提取到可验证事实，目前无法给出可靠结论。"
            gaps = "缺少可用页面内容或可引用主张；可换关键词、语言或放宽时效后再试。"
        else:
            thesis = (
                f"No verified facts were extracted for «{topic}»; "
                "no reliable conclusion is available yet."
            )
            gaps = (
                "Likely gaps: primary sources, rankings, market-size reports. "
                "Try broader keywords or alternate languages."
            )
        return ReportSynthesis(
            thesis=thesis,
            arguments=[],
            executive_summary=thesis,
            coverage=f"Searched: {searched_preview}{more}",
            gaps=gaps,
        )

    lang = _topic_language_hint(topic)
    thin = len(facts) < 8
    thesis = facts[0].fact.strip()
    if lang == "zh":
        coverage = f"已检索主题：{'、'.join(topics_searched[:12])}。"
        gaps = (
            "可能仍缺：排行榜原始数据、市场份额、竞品对比或付费报告。"
            if thin
            else "可能遗漏未公开或需订阅的信源；请以原文引用为准。"
        )
    else:
        coverage = f"Topics searched: {searched_preview}{more}."
        gaps = (
            "Still thin on rankings, market share, and competitor matrix."
            if thin
            else "Non-public or paywalled sources may be missing; verify via citations."
        )

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
    arguments = _arguments_from_facts(facts)

    return ReportSynthesis(
        thesis=thesis,
        arguments=arguments,
        executive_summary=thesis,
        structured_findings=structured,
        coverage=coverage,
        gaps=gaps,
    )


def _finalize_synthesis(
    raw: dict,
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
) -> ReportSynthesis:
    fallback = fallback_synthesis(topic, facts, topics_searched)
    findings = _normalize_findings(
        raw.get("structured_findings") or [], len(facts), facts=facts,
    )
    if not findings:
        findings = fallback.structured_findings

    arguments = _normalize_arguments(
        raw.get("arguments") or [], len(facts), facts=facts,
    )
    if not arguments:
        arguments = fallback.arguments

    thesis = str(raw.get("thesis") or "").strip()
    if not thesis:
        # Legacy multi-sentence executive_summary → first sentence
        thesis = _first_sentence(str(raw.get("executive_summary") or "")) or fallback.thesis

    return ReportSynthesis(
        thesis=thesis,
        arguments=arguments,
        executive_summary=thesis,
        structured_findings=findings,
        coverage=str(raw.get("coverage") or "").strip() or fallback.coverage,
        gaps=str(raw.get("gaps") or "").strip() or fallback.gaps,
        fund_activity=str(raw.get("fund_activity") or "").strip(),
        credit_risk_watch=str(raw.get("credit_risk_watch") or "").strip(),
    )


async def synthesize_report(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
    report_type: str | None = None,
) -> ReportSynthesis:
    """Generate thesis + arguments (+ signal ledger) from verified facts."""
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
            max_tokens=2500,
        )
        raw = _parse_synthesis_json(response.choices[0].message.content or "")
        if not raw:
            return fallback_synthesis(topic, facts, topics_searched)
        return _finalize_synthesis(raw, topic, facts, topics_searched)
    except Exception:
        return fallback_synthesis(topic, facts, topics_searched)
