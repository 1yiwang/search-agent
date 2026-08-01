"""Two-pass report synthesis (Wave 12c): EvidenceDraft → structured Gemini-style write.

Pass A: assign verified facts into fixed outline slots; quarantine off-topic.
Pass B: write thesis + long section prose (~150–300 字) from the draft only.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from llm_context import get_openai_client, get_request_keys
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


WRITE_PROMPT = """You write a Gemini-style research report section narrative from an Evidence Draft.

Research question to answer: {topic_restatement}
Original topic: {topic}
Language: match the research question (Chinese question → Chinese prose).

Outline slots with assigned facts:
{draft_slots_json}

Full fact list (citation_index):
{facts_json}

Quarantined (do NOT use as main claims): {quarantine_json}

Instructions:
1. thesis: EXACTLY ONE sentence that directly answers the research question. Never meta ("this report collected N facts"). Never lead with GDP/macro if quarantined.
2. For EACH slot that has fact_indices, write one argument object:
   - heading: use the provided slot title
   - slot_id: copy slot_id
   - claim: one topic sentence
   - body: 150–300 Chinese characters if writing Chinese, or ~120–220 English words if English — 1–2 short paragraphs. Cite as [n] using only assigned citation indices. Substantive analysis, not a bullet dump.
   - citation_indices: the indices you used
   - confidence: high|medium|low from supporting facts
3. Skip empty optional slots. For empty required slots, one short claim saying evidence is insufficient (no invention) + empty body ok.
4. gaps: include material gaps + summarize quarantine themes.
5. coverage: what was searched / languages.
6. structured_findings: compact appendix rows (entity/signal/date/confidence/citation_index) from on-topic facts only.
7. Use ONLY provided facts — no outside knowledge.

Return ONLY valid JSON:
```json
{{
  "thesis": "One sentence answering the question.",
  "arguments": [
    {{
      "heading": "Section title",
      "slot_id": "industry_structure",
      "claim": "Topic sentence.",
      "body": "Longer Gemini-style paragraphs with [1] [2] citations...",
      "citation_indices": [1, 2],
      "confidence": "high"
    }}
  ],
  "structured_findings": [],
  "coverage": "...",
  "gaps": "...",
  "fund_activity": "",
  "credit_risk_watch": ""
}}
```"""


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
    dep_l = (deprioritize or "").lower()
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
        tokens = [t.lower() for t in re.split(r"[\s,/|]+", goal) if len(t) > 3][:8]
        matched: list[int] = []
        for i in on_topic_indices:
            if i in qset:
                continue
            blob = f"{facts[i - 1].fact} {facts[i - 1].quoted_text}".lower()
            if not tokens or any(t in blob for t in tokens):
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
            f"未能就「{restatement}」提取到可验证事实，目前无法给出可靠结论。"
            if lang == "zh"
            else f"No verified facts for «{restatement}»; no reliable conclusion yet."
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

    arguments = _arguments_from_draft(draft, facts)
    thesis = draft.topic_restatement
    if facts:
        # Prefer first on-topic fact as provisional thesis answer seed
        qset = {q.fact_index for q in draft.quarantine}
        for i, f in enumerate(facts, 1):
            if i not in qset:
                thesis = _first_sentence(f.fact) or f.fact
                break

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

        arguments = _normalize_write_arguments(
            raw.get("arguments") or [], draft, facts,
        )
        thesis = str(raw.get("thesis") or "").strip()
        if not thesis:
            thesis = _first_sentence(str(raw.get("executive_summary") or "")) or (
                draft.topic_restatement or topic
            )
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
