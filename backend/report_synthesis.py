"""Two-pass report synthesis (Wave 12c): EvidenceDraft → structured Gemini-style write.

Pass A: assign verified facts into fixed outline slots; quarantine off-topic.
Pass B: write thesis + long section prose (~150–300 字) from the draft only.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from brief_rubric import harvest_entities
from llm_context import get_openai_client, get_request_keys
from report_labels import get_labels, report_language
from models import (
    EvidenceDraft,
    EvidenceDraftQuarantine,
    EvidenceDraftSlot,
    ExtractedFact,
    ReportArgument,
    ReportSynthesis,
    ResearchBrief,
    StructuredFinding,
)
from report_outlines import outline_prompt_block, resolve_slots
from sources.pd_registry import has_private_debt_intent

EmitCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

DRAFT_PROMPT = """You build an Evidence Draft for a research report. Do NOT write the final prose.

Research question (must stay on-topic): {topic_restatement}
Original topic: {topic}
Deprioritize / quarantine themes: {deprioritize}

{slots_block}

Verified facts (citation_index = footnote number):
{facts_json}

Instructions:
1. Assign each relevant fact to the BEST matching slot via fact_indices (1-based citation_index).
2. A fact may appear in at most TWO slots; prefer one.
3. Quarantine facts that are off-topic for the research question (e.g. GDP/macro when the question is industry market entry) — list fact_index + short reason.
4. topic_restatement: one clear sentence restating what the report must answer (same language as topic).
5. sufficiency: "thin" if required slots lack facts, else "ok".
6. notes: optional short note per slot (enough / thin / missing angle).

Return ONLY valid JSON:
```json
{{
  "topic_restatement": "...",
  "slots": [
    {{"slot_id": "...", "fact_indices": [1, 3], "notes": ""}}
  ],
  "quarantine": [
    {{"fact_index": 2, "reason": "Swiss GDP — off-topic for telecom entry"}}
  ],
  "sufficiency": "ok"
}}
```"""


WRITE_PROMPT = """You write a Gemini-style research brief from an Evidence Draft.

Research question to answer: {topic_restatement}
Original topic: {topic}
Language: match the research question (Chinese question → Chinese prose, Chinese headings).

Outline slots with assigned facts ({slot_count} slots — write exactly {slot_count} sections, same order, same slot_id):
{draft_slots_json}

Full fact list (citation_index):
{facts_json}

Quarantined (do NOT use as main claims): {quarantine_json}

Instructions:
1. thesis: ONE judgment answering the research question. Must contain a directional
   judgment + a quantitative anchor (number/share/date/named entity) + a qualifier
   (uncertainty or boundary of validity). 24–200 Chinese characters / 10–90 English words.
   FORBIDDEN meta wording — never "本报告整理了N条事实" / "this brief covers N facts from M sources".
   Never lead with GDP/macro if quarantined.
2. key_takeaways: 3–5 assertions, each ≤40 Chinese characters, each ending with its [n] citation.
3. arguments: exactly {slot_count} sections, one per slot, in the given order. Each:
   - heading: slot title, slot_id: the slot's id
   - claim: one finding sentence (not a process note)
   - body: 150–300 Chinese characters OR ~120–220 English words:
     claim → key evidence [n] → counter-evidence or boundary → what it means for this question.
     Answer the slot's must_answer when present. Cite only the slot's assigned indices.
   - citation_indices, confidence
4. Empty slot → claim that no citable evidence was found, and say what source would settle it.
   Never invent facts to fill a slot.
5. so_what: 120–200 characters — feasibility, priority path, next verification step across directions.
6. gaps: plain language — which direction is thin, why, and which source to add next.
7. structured_findings = compact appendix rows from on-topic facts only. Use ONLY provided facts.

Return ONLY valid JSON:
```json
{{
  "thesis": "Judgment + anchor + qualifier.",
  "key_takeaways": ["断言一 [1]", "断言二 [3]"],
  "arguments": [
    {{
      "heading": "Section title",
      "slot_id": "industry_structure",
      "claim": "Finding topic sentence.",
      "body": "Longer reasoned paragraphs with [1] [2]…",
      "citation_indices": [1, 2],
      "confidence": "high"
    }}
  ],
  "so_what": "...",
  "structured_findings": [],
  "coverage": "...",
  "gaps": "...",
  "fund_activity": "",
  "credit_risk_watch": ""
}}
```"""


THESIS_REWRITE_PROMPT = """重写这份研究报告的结论句，使其成为一个判断，而不是过程说明。

研究问题：{topic_restatement}
原始选题：{topic}

当前结论：{current}
不合格原因：{reasons}

可用事实（只能用这些，不要引入外部知识）：
{facts_json}

要求：
- 语言与研究问题一致（中文问题 → 中文结论）。
- 必须包含：方向性判断 + 量化锚点（数字/份额/日期/具名实体）+ 限定条件（不确定性或适用边界）。
- 中文 24–200 字；英文 10–90 词。
- 禁止：本报告整理了 N 条 / 来自 M 个来源 / 综上所述 / 本文将探讨。

只返回 JSON：{{"thesis": "..."}}"""


def detect_report_type(topic: str) -> str:
    if has_private_debt_intent(topic):
        return "investor_brief"
    return "intelligence_brief"


def _topic_language_hint(topic: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", topic):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", topic):
        return "de"
    return "en"


def _parse_json_object(content: str) -> dict:
    content = (content or "").strip()
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


_META_THESIS_RE = re.compile(
    r"(本报告围绕|整理了\s*\d+\s*条|已验证事实|来自\s*\d+\s*个独立来源|"
    r"this brief covers\s*\d+|verified facts on|unique sources|"
    r"No verified facts were extracted|"
    r"未能就「[^」]+」提取到可验证事实)",
    re.IGNORECASE,
)


def _is_meta_thesis(text: str) -> bool:
    return bool(_META_THESIS_RE.search(text or ""))


_THESIS_HARD_REASONS = frozenset({
    "empty", "meta_narrative", "language_mismatch", "too_short",
})

THESIS_REASON_TEXT_ZH = {
    "empty": "结论为空",
    "meta_narrative": "写成了过程元叙述（整理了 N 条 / 来自 M 个来源）",
    "language_mismatch": "语言与选题不一致",
    "too_short": "太短，不构成判断",
    "too_long": "太长，不像一句结论",
    "no_anchor": "缺少量化锚点或具名实体",
    "no_qualifier": "缺少限定条件（不确定性 / 适用边界）",
}

_ANCHOR_RE = re.compile(r"\d|%|percent|亿|万|CHF|EUR|USD|€|\$", re.IGNORECASE)
_QUALIFIER_MARKERS = (
    "但", "不过", "然而", "限于", "仅", "尚", "需", "若", "除非", "取决于",
    "however", "but ", "although", "unless", "depends", "limited", "pending",
)


@dataclass
class ThesisVerdict:
    """Deterministic gate result for the report conclusion."""
    ok: bool
    reasons: list[str]

    def explain_zh(self) -> str:
        return "；".join(THESIS_REASON_TEXT_ZH.get(r, r) for r in self.reasons)


def check_thesis(thesis: str, topic: str) -> ThesisVerdict:
    """A thesis must be a judgment in the topic language, not a process note."""
    text = (thesis or "").strip()
    if not text:
        return ThesisVerdict(ok=False, reasons=["empty"])

    reasons: list[str] = []
    if _is_meta_thesis(text):
        reasons.append("meta_narrative")

    lang = _topic_language_hint(topic)
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    if lang == "zh":
        if not has_cjk:
            reasons.append("language_mismatch")
        length = len(re.sub(r"\s+", "", text))
        if length < 24:
            reasons.append("too_short")
        elif length > 200:
            reasons.append("too_long")
    else:
        if has_cjk:
            reasons.append("language_mismatch")
        words = len(text.split())
        if words < 10:
            reasons.append("too_short")
        elif words > 90:
            reasons.append("too_long")

    # CJK n-grams are too weak to count as an anchor — require figures or proper nouns
    proper_nouns = [e for e in harvest_entities(text, max_n=6) if e[:1].isupper()]
    if not _ANCHOR_RE.search(text) and len(proper_nouns) < 2:
        reasons.append("no_anchor")
    low = text.lower()
    if not any(m in text or m in low for m in _QUALIFIER_MARKERS):
        reasons.append("no_qualifier")

    hard = [r for r in reasons if r in _THESIS_HARD_REASONS]
    return ThesisVerdict(ok=not hard, reasons=reasons)


def _judgment_thesis(
    topic: str,
    restatement: str,
    facts: list[ExtractedFact],
    quarantine_indices: set[int],
    *,
    sufficiency: str = "ok",
) -> str:
    """Deterministic fallback: a judgment with a qualifier, not two glued facts."""
    lang = _topic_language_hint(topic)
    question = (restatement or topic).strip()
    kept = [
        f for i, f in enumerate(facts, 1)
        if i not in quarantine_indices and (f.fact or "").strip()
    ]
    if not kept:
        if lang == "zh":
            return f"证据不足：现有材料尚不能对「{question}」给出可靠判断。"
        return f"Insufficient evidence to answer «{question}»."

    ordered = sorted(
        kept,
        key=lambda f: {"high": 0, "medium": 1, "low": 2}.get(
            (f.confidence or "medium").lower(), 1
        ),
    )
    core = ""
    for fact in ordered[:3]:
        candidate = _first_sentence(fact.fact) or (fact.fact or "").strip()
        if candidate and not _is_meta_thesis(candidate):
            core = candidate
            break
    if not core:
        core = (ordered[0].fact or "").strip()
    core = core.rstrip("。.!！?？").strip()

    thin = sufficiency == "thin" or len(kept) < 4
    high_conf = sum(1 for f in ordered if (f.confidence or "").lower() == "high")
    if lang == "zh":
        qualifier = (
            "但关键量化数据仍缺乏公开来源，该判断需进一步验证。"
            if thin or high_conf == 0
            else "该判断可在多个独立来源间交叉印证，但仍受公开数据口径限制。"
        )
        return f"就「{question}」，现有证据支持的判断是：{core}。{qualifier}"
    qualifier = (
        "Key figures still lack public sources, so this needs further verification."
        if thin or high_conf == 0
        else "This holds across several independent sources, within the limits of public data."
    )
    return f"On «{question}», the evidence supports this judgment: {core}. {qualifier}"


def _sanitize_thesis(
    thesis: str,
    topic: str,
    restatement: str,
    facts: list[ExtractedFact],
    quarantine_indices: set[int],
    *,
    sufficiency: str = "ok",
) -> str:
    verdict = check_thesis(thesis, topic)
    if verdict.ok:
        return (thesis or "").strip()
    return _judgment_thesis(
        topic, restatement, facts, quarantine_indices, sufficiency=sufficiency,
    )


# Legacy alias — code-built thesis used by older call sites and tests
_substantive_thesis = _judgment_thesis


def _facts_payload(facts: list[ExtractedFact]) -> list[dict]:
    return [
        {
            "citation_index": i + 1,
            "fact": f.fact,
            "confidence": f.confidence,
            "event_date": f.event_date,
            "source_title": f.source_title,
            "source_url": f.source_url,
            "quoted_excerpt": (f.quoted_text or "")[:200],
            "signal_type": getattr(f, "signal_type", "") or "other",
            "entity_type": getattr(f, "entity_type", "") or "other",
        }
        for i, f in enumerate(facts)
    ]


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


def _slot_title(slot: dict, zh: bool) -> str:
    if zh and slot.get("title_zh"):
        return str(slot["title_zh"])
    return str(slot.get("title") or slot.get("id") or "")


def _heuristic_draft(
    topic: str,
    facts: list[ExtractedFact],
    slots: list[dict],
    outline_id: str,
    deprioritize: str,
    topic_restatement: str,
) -> EvidenceDraft:
    """Deterministic draft when LLM unavailable: keyword overlap + GDP quarantine."""
    zh = _topic_language_hint(topic) == "zh"
    quarantine: list[EvidenceDraftQuarantine] = []
    on_topic_indices: list[int] = []

    macro_markers = ("gdp", "gross domestic", "macroeconom", "国内生产总值", "宏观经济")
    for i, fact in enumerate(facts, 1):
        blob = f"{fact.fact} {fact.quoted_text}".lower()
        topic_blob = f"{topic} {topic_restatement}".lower()
        is_macro_fact = any(m in blob for m in macro_markers)
        topic_is_macro = any(m in topic_blob for m in ("gdp", "宏观", "宏观经济", "macroeconom"))
        if is_macro_fact and not topic_is_macro:
            quarantine.append(EvidenceDraftQuarantine(
                fact_index=i,
                reason="GDP/macro — off-topic for industry brief",
            ))
            continue
        on_topic_indices.append(i)

    qset = {q.fact_index for q in quarantine}
    draft_slots: list[EvidenceDraftSlot] = []
    for slot in slots:
        goal = str(slot.get("writing_goal") or slot.get("title") or "")
        from text_tokens import tokens as text_tokens
        tokens = text_tokens(goal, max_tokens=8)
        matched: list[int] = []
        for i in on_topic_indices:
            if i in qset:
                continue
            blob = f"{facts[i - 1].fact} {facts[i - 1].quoted_text}".lower()
            if not tokens or any(t.lower() in blob for t in tokens):
                matched.append(i)
        if not matched and on_topic_indices and slot.get("required"):
            # Round-robin leftover for required slots
            matched = [on_topic_indices[(len(draft_slots)) % len(on_topic_indices)]]
        draft_slots.append(EvidenceDraftSlot(
            slot_id=str(slot["id"]),
            title=_slot_title(slot, zh),
            writing_goal=goal,
            fact_indices=matched[:8],
            notes="",
            required=bool(slot.get("required")),
        ))

    required_empty = any(
        s.required and not s.fact_indices for s in draft_slots
    )
    return EvidenceDraft(
        topic_restatement=topic_restatement or topic,
        outline_id=outline_id,
        slots=draft_slots,
        quarantine=quarantine,
        sufficiency="thin" if required_empty or len(facts) < 4 else "ok",
    )


def _arguments_from_draft(
    draft: EvidenceDraft,
    facts: list[ExtractedFact],
) -> list[ReportArgument]:
    args: list[ReportArgument] = []
    for slot in draft.slots:
        if not slot.fact_indices and not slot.required:
            continue
        bodies: list[str] = []
        confs: list[str] = []
        for idx in slot.fact_indices[:5]:
            if 1 <= idx <= len(facts):
                bodies.append(facts[idx - 1].fact)
                confs.append(facts[idx - 1].confidence or "medium")
        if not bodies:
            claim = (
                f"材料不足，尚无法充分论述「{slot.title or slot.slot_id}」。"
                if _topic_language_hint(draft.topic_restatement) == "zh"
                else f"Insufficient evidence for «{slot.title or slot.slot_id}»."
            )
            args.append(ReportArgument(
                claim=claim,
                body="",
                heading=slot.title,
                slot_id=slot.slot_id,
                citation_indices=[],
                confidence="low",
            ))
            continue
        claim = bodies[0]
        body = " ".join(bodies)
        # Pad lightly toward Gemini length when only short facts
        if len(body) < 120 and len(bodies) > 1:
            body = "\n\n".join(bodies)
        ranks = {"high": 3, "medium": 2, "low": 1}
        conf = min(confs, key=lambda c: ranks.get(c, 0)) if confs else "medium"
        args.append(ReportArgument(
            claim=_first_sentence(claim) or claim,
            detail="",
            body=body,
            heading=slot.title,
            slot_id=slot.slot_id,
            citation_indices=list(slot.fact_indices[:6]),
            confidence=conf if conf in ranks else "medium",
        ))
    return args


def _slot_queries(
    slot: EvidenceDraftSlot,
    topics_searched: list[str],
    *,
    max_n: int = 3,
) -> list[str]:
    """Executed queries most related to a slot — for honest empty sections."""
    from text_tokens import keyword_list

    keys = [k.lower() for k in keyword_list(slot.title, slot.writing_goal, max_tokens=10)]
    scored: list[tuple[int, str]] = []
    for query in topics_searched:
        low = query.lower()
        score = sum(1 for k in keys if k in low)
        if score:
            scored.append((score, query))
    scored.sort(key=lambda pair: -pair[0])
    picked = [q for _, q in scored[:max_n]]
    return picked or list(topics_searched[:max_n])


def _empty_slot_argument(
    slot: EvidenceDraftSlot,
    topics_searched: list[str],
    lang: str,
) -> ReportArgument:
    """Say what was searched and what is missing instead of dropping the section."""
    title = slot.title or slot.slot_id
    queries = _slot_queries(slot, topics_searched)
    entities = harvest_entities(slot.writing_goal or "", max_n=3)
    if lang == "zh":
        claim = f"「{title}」未获得可引用证据。"
        parts = [claim]
        if queries:
            parts.append("已执行检索：" + "、".join(queries) + "。")
        parts.append("可能原因：公开来源未覆盖该角度，或目标页面抓取失败。")
        parts.append(
            "建议补充信源：" + "、".join(f"{e} 官网或年报" for e in entities) + "。"
            if entities
            else "建议补充信源：监管机构公开数据、行业协会年报、当地公司财报。"
        )
    else:
        claim = f"No citable evidence for «{title}» yet."
        parts = [claim]
        if queries:
            parts.append("Queries run: " + "; ".join(queries) + ".")
        parts.append("Likely cause: no public source covers this angle, or fetching failed.")
        parts.append(
            "Suggested sources: " + ", ".join(f"{e} filings or site" for e in entities) + "."
            if entities
            else "Suggested sources: regulator data, industry association reports, local filings."
        )
    return ReportArgument(
        claim=claim,
        body=" ".join(parts[1:]),
        heading=title,
        slot_id=slot.slot_id,
        citation_indices=[],
        confidence="low",
    )


def _align_arguments_to_slots(
    arguments: list[ReportArgument],
    draft: EvidenceDraft,
    topics_searched: list[str],
    topic: str,
) -> list[ReportArgument]:
    """One section per approved direction, in order — no silent drops (Step 88)."""
    lang = _topic_language_hint(topic)
    by_slot: dict[str, ReportArgument] = {}
    by_heading: dict[str, ReportArgument] = {}
    for arg in arguments:
        if arg.slot_id and arg.slot_id not in by_slot:
            by_slot[arg.slot_id] = arg
        heading = (arg.heading or "").strip()
        if heading and heading not in by_heading:
            by_heading[heading] = arg

    used: set[int] = set()
    out: list[ReportArgument] = []
    for slot in draft.slots:
        arg = by_slot.get(slot.slot_id)
        if arg is None or id(arg) in used:
            candidate = by_heading.get((slot.title or "").strip())
            arg = candidate if candidate is not None and id(candidate) not in used else None
        if arg is not None and (arg.claim or arg.body) and id(arg) not in used:
            used.add(id(arg))
            arg.slot_id = slot.slot_id
            arg.heading = (arg.heading or "").strip() or slot.title
            out.append(arg)
            continue
        out.append(_empty_slot_argument(slot, topics_searched, lang))
    return out


def fallback_synthesis(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
    brief: ResearchBrief | None = None,
) -> ReportSynthesis:
    outline_id, slots, dep = resolve_slots(topic, brief)
    restatement = (
        (brief.problem_restatement if brief else "") or topic
    ).strip()
    draft = _heuristic_draft(topic, facts, slots, outline_id, dep, restatement)

    if not facts:
        lang = _topic_language_hint(topic)
        thesis = (
            f"证据不足：现有材料尚不能对「{restatement}」给出可靠判断。"
            if lang == "zh"
            else f"Insufficient evidence to answer «{restatement}»."
        )
        return ReportSynthesis(
            thesis=thesis,
            arguments=[],
            executive_summary=thesis,
            coverage=f"Searched: {', '.join(topics_searched[:8])}",
            gaps="No citable page content.",
            outline_id=outline_id,
            draft_sufficiency="thin",
        )

    arguments = _align_arguments_to_slots(
        _arguments_from_draft(draft, facts), draft, topics_searched, topic,
    )
    qset = {q.fact_index for q in draft.quarantine}
    thesis = _judgment_thesis(
        topic,
        draft.topic_restatement or restatement,
        facts,
        qset,
        sufficiency=draft.sufficiency,
    )

    structured = [
        StructuredFinding(
            entity=f.fact[:60].split("—")[0].strip() or f.source_title[:40],
            signal=f.fact,
            date=getattr(f, "event_date", "") or "",
            confidence=f.confidence,
            citation_index=i + 1,
            signal_type=getattr(f, "signal_type", "") or "other",
            entity_type=getattr(f, "entity_type", "") or "other",
        )
        for i, f in enumerate(facts[:15])
        if (i + 1) not in {q.fact_index for q in draft.quarantine}
    ]
    q_notes = "; ".join(f"[{q.fact_index}] {q.reason}" for q in draft.quarantine[:5])
    gaps = (
        f"Quarantined off-topic: {q_notes}" if q_notes else "Verify via citations."
    )
    return ReportSynthesis(
        thesis=thesis,
        arguments=arguments,
        executive_summary=thesis,
        structured_findings=structured,
        coverage=f"Topics: {', '.join(topics_searched[:12])}",
        gaps=gaps,
        outline_id=outline_id,
        draft_sufficiency=draft.sufficiency,
    )


def _apply_draft_raw(
    raw: dict,
    topic: str,
    facts: list[ExtractedFact],
    slots: list[dict],
    outline_id: str,
    deprioritize: str,
    topic_restatement: str,
) -> EvidenceDraft:
    zh = _topic_language_hint(topic) == "zh"
    slot_meta = {str(s["id"]): s for s in slots}
    draft_slots: list[EvidenceDraftSlot] = []
    seen_ids: set[str] = set()

    for item in raw.get("slots") or []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("slot_id") or "").strip()
        if not sid or sid not in slot_meta or sid in seen_ids:
            continue
        seen_ids.add(sid)
        meta = slot_meta[sid]
        indices: list[int] = []
        for v in item.get("fact_indices") or []:
            try:
                idx = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= len(facts) and idx not in indices:
                indices.append(idx)
        draft_slots.append(EvidenceDraftSlot(
            slot_id=sid,
            title=_slot_title(meta, zh),
            writing_goal=str(meta.get("writing_goal") or ""),
            fact_indices=indices[:10],
            notes=str(item.get("notes") or "").strip(),
            required=bool(meta.get("required")),
        ))

    # Ensure all outline slots appear
    for meta in slots:
        sid = str(meta["id"])
        if sid in seen_ids:
            continue
        draft_slots.append(EvidenceDraftSlot(
            slot_id=sid,
            title=_slot_title(meta, zh),
            writing_goal=str(meta.get("writing_goal") or ""),
            fact_indices=[],
            required=bool(meta.get("required")),
        ))

    quarantine: list[EvidenceDraftQuarantine] = []
    for item in raw.get("quarantine") or []:
        if not isinstance(item, dict):
            continue
        try:
            fi = int(item.get("fact_index") or 0)
        except (TypeError, ValueError):
            continue
        if 1 <= fi <= len(facts):
            quarantine.append(EvidenceDraftQuarantine(
                fact_index=fi,
                reason=str(item.get("reason") or "").strip() or "off-topic",
            ))

    if not draft_slots:
        return _heuristic_draft(
            topic, facts, slots, outline_id, deprioritize, topic_restatement,
        )

    sufficiency = str(raw.get("sufficiency") or "ok").lower()
    if sufficiency not in ("thin", "ok"):
        sufficiency = "ok"
    rest = str(raw.get("topic_restatement") or "").strip() or topic_restatement

    return EvidenceDraft(
        topic_restatement=rest,
        outline_id=outline_id,
        slots=draft_slots,
        quarantine=quarantine,
        sufficiency=sufficiency,
    )


def _normalize_write_arguments(
    raw: list,
    draft: EvidenceDraft,
    facts: list[ExtractedFact],
) -> list[ReportArgument]:
    args: list[ReportArgument] = []
    slot_by_id = {s.slot_id: s for s in draft.slots}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        sid = str(item.get("slot_id") or "").strip()
        heading = str(item.get("heading") or "").strip()
        if not heading and sid in slot_by_id:
            heading = slot_by_id[sid].title
        indices: list[int] = []
        for v in item.get("citation_indices") or []:
            try:
                idx = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= idx <= len(facts) and idx not in indices:
                indices.append(idx)
        if not indices and sid in slot_by_id:
            indices = list(slot_by_id[sid].fact_indices[:6])
        body = str(item.get("body") or item.get("detail") or "").strip()
        conf = str(item.get("confidence") or "medium").lower()
        if conf not in ("high", "medium", "low"):
            conf = "medium"
        args.append(ReportArgument(
            claim=claim,
            detail=str(item.get("detail") or "").strip() if not body else "",
            body=body,
            heading=heading,
            slot_id=sid,
            citation_indices=indices,
            confidence=conf,
        ))
        if len(args) >= 10:
            break
    if not args:
        return _arguments_from_draft(draft, facts)
    return args


async def _repair_thesis(
    thesis: str,
    topic: str,
    draft: EvidenceDraft,
    facts: list[ExtractedFact],
    verdict: ThesisVerdict,
    *,
    model: str,
) -> str:
    """One targeted rewrite when the thesis fails the gate; caller re-checks."""
    top_facts = [
        {"citation_index": i + 1, "fact": f.fact, "confidence": f.confidence}
        for i, f in enumerate(facts[:8])
    ]
    prompt = THESIS_REWRITE_PROMPT.format(
        topic_restatement=draft.topic_restatement or topic,
        topic=topic,
        current=thesis or "(empty)",
        reasons=verdict.explain_zh(),
        facts_json=json.dumps(top_facts, ensure_ascii=False, indent=2),
    )
    try:
        response = await get_openai_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
        )
    except Exception:
        return thesis
    raw = _parse_json_object(response.choices[0].message.content or "")
    return str(raw.get("thesis") or "").strip() or thesis


async def build_evidence_draft(
    topic: str,
    facts: list[ExtractedFact],
    *,
    brief: ResearchBrief | None = None,
) -> EvidenceDraft:
    """Pass A: assign facts into fixed outline slots."""
    outline_id, slots, dep = resolve_slots(topic, brief)
    restatement = ((brief.problem_restatement if brief else "") or topic).strip()
    if not facts:
        return EvidenceDraft(
            topic_restatement=restatement,
            outline_id=outline_id,
            slots=[
                EvidenceDraftSlot(
                    slot_id=str(s["id"]),
                    title=_slot_title(s, _topic_language_hint(topic) == "zh"),
                    writing_goal=str(s.get("writing_goal") or ""),
                    required=bool(s.get("required")),
                )
                for s in slots
            ],
            sufficiency="thin",
        )

    keys = get_request_keys()
    if not keys or not keys.llm_api_key:
        return _heuristic_draft(topic, facts, slots, outline_id, dep, restatement)

    zh = _topic_language_hint(topic) == "zh"
    prompt = DRAFT_PROMPT.format(
        topic_restatement=restatement,
        topic=topic,
        deprioritize=dep or "(none)",
        slots_block=outline_prompt_block(slots, zh=zh),
        facts_json=json.dumps(_facts_payload(facts), ensure_ascii=False, indent=2),
    )
    try:
        response = await get_openai_client().chat.completions.create(
            model=keys.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = _parse_json_object(response.choices[0].message.content or "")
        if not raw:
            return _heuristic_draft(topic, facts, slots, outline_id, dep, restatement)
        return _apply_draft_raw(
            raw, topic, facts, slots, outline_id, dep, restatement,
        )
    except Exception:
        return _heuristic_draft(topic, facts, slots, outline_id, dep, restatement)


async def write_from_draft(
    topic: str,
    facts: list[ExtractedFact],
    draft: EvidenceDraft,
    topics_searched: list[str],
    report_type: str | None = None,
) -> ReportSynthesis:
    """Pass B: Gemini-style thesis + long sections from draft."""
    if report_type is None:
        report_type = detect_report_type(topic)

    if not facts:
        return fallback_synthesis(topic, facts, topics_searched)

    keys = get_request_keys()
    if not keys or not keys.llm_api_key:
        syn = fallback_synthesis(topic, facts, topics_searched)
        syn.outline_id = draft.outline_id
        syn.draft_sufficiency = draft.sufficiency
        return syn

    draft_slots_json = json.dumps(
        [
            {
                "slot_id": s.slot_id,
                "title": s.title,
                "writing_goal": s.writing_goal,
                "fact_indices": s.fact_indices,
                "required": s.required,
                "notes": s.notes,
            }
            for s in draft.slots
        ],
        ensure_ascii=False,
        indent=2,
    )
    quarantine_json = json.dumps(
        [{"fact_index": q.fact_index, "reason": q.reason} for q in draft.quarantine],
        ensure_ascii=False,
    )
    prompt = WRITE_PROMPT.format(
        topic_restatement=draft.topic_restatement or topic,
        topic=topic,
        slot_count=len(draft.slots),
        draft_slots_json=draft_slots_json,
        facts_json=json.dumps(_facts_payload(facts), ensure_ascii=False, indent=2),
        quarantine_json=quarantine_json,
    )
    try:
        response = await get_openai_client().chat.completions.create(
            model=keys.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4500,
        )
        raw = _parse_json_object(response.choices[0].message.content or "")
        if not raw:
            syn = fallback_synthesis(topic, facts, topics_searched)
            syn.outline_id = draft.outline_id
            return syn

        arguments = _align_arguments_to_slots(
            _normalize_write_arguments(raw.get("arguments") or [], draft, facts),
            draft,
            topics_searched,
            topic,
        )
        qset = {q.fact_index for q in draft.quarantine}
        raw_thesis = (
            str(raw.get("thesis") or "").strip()
            or _first_sentence(str(raw.get("executive_summary") or ""))
        )
        verdict = check_thesis(raw_thesis, topic)
        if not verdict.ok:
            raw_thesis = await _repair_thesis(
                raw_thesis, topic, draft, facts, verdict, model=keys.llm_model,
            )
            verdict = check_thesis(raw_thesis, topic)
        thesis = _sanitize_thesis(
            raw_thesis,
            topic,
            draft.topic_restatement or topic,
            facts,
            qset,
            sufficiency=draft.sufficiency,
        )
        takeaways = [
            str(t).strip() for t in (raw.get("key_takeaways") or []) if str(t).strip()
        ][:5]
        so_what = str(raw.get("so_what") or "").strip()
        findings = _normalize_findings(
            raw.get("structured_findings") or [], len(facts), facts=facts,
        )
        q_notes = "; ".join(
            f"[{q.fact_index}] {q.reason}" for q in draft.quarantine[:6]
        )
        gaps = str(raw.get("gaps") or "").strip()
        if q_notes:
            gaps = (gaps + f" Quarantined: {q_notes}").strip() if gaps else f"Quarantined: {q_notes}"

        return ReportSynthesis(
            thesis=thesis,
            arguments=arguments,
            executive_summary=thesis,
            key_takeaways=takeaways,
            so_what=so_what,
            structured_findings=findings or fallback_synthesis(
                topic, facts, topics_searched,
            ).structured_findings,
            coverage=str(raw.get("coverage") or "").strip()
            or f"Topics: {', '.join(topics_searched[:12])}",
            gaps=gaps,
            fund_activity=str(raw.get("fund_activity") or "").strip(),
            credit_risk_watch=str(raw.get("credit_risk_watch") or "").strip(),
            outline_id=draft.outline_id,
            draft_sufficiency=draft.sufficiency,
            thesis_reasons=verdict.reasons,
        )
    except Exception:
        syn = fallback_synthesis(topic, facts, topics_searched)
        syn.outline_id = draft.outline_id
        syn.draft_sufficiency = draft.sufficiency
        return syn


async def synthesize_report(
    topic: str,
    facts: list[ExtractedFact],
    topics_searched: list[str],
    report_type: str | None = None,
    brief: ResearchBrief | None = None,
    event_callback: EmitCallback | None = None,
) -> ReportSynthesis:
    """Two-pass: EvidenceDraft → structured write."""
    if report_type is None:
        report_type = detect_report_type(topic)

    async def emit(event_type: str, data: dict) -> None:
        if event_callback:
            await event_callback(event_type, data)

    draft = await build_evidence_draft(topic, facts, brief=brief)
    await emit("draft_ready", {
        "outline_id": draft.outline_id,
        "slot_count": len(draft.slots),
        "filled_slots": sum(1 for s in draft.slots if s.fact_indices),
        "quarantine_count": len(draft.quarantine),
        "sufficiency": draft.sufficiency,
        "topic_restatement": draft.topic_restatement[:240],
    })

    return await write_from_draft(
        topic, facts, draft, topics_searched, report_type=report_type,
    )
