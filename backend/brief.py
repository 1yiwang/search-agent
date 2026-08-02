"""Industry ResearchBrief: clarify → generate → revise (Wave 12a).

No web search during brief generation — LLM + framework skeletons only.
"""

from __future__ import annotations

import json
import re

from frameworks import framework_prompt_block, get_framework, select_framework_id
from llm_context import get_openai_client, get_request_keys
from meta import _parse_json_object, format_human_feedback
from models import BriefDimension, ResearchBrief

INDUSTRY_CLARIFY_PROMPT = """You are scoping an INDUSTRY RESEARCH project (market structure → players/products → opportunities/barriers), not encyclopedia Q&A.

Research topic: {topic}

Ask 2–4 clarifying questions. Prefer covering these categories when relevant:
- boundary: what to include/exclude (e.g. exclude GDP/macro unless asked)
- breadth: sub-sectors / product lines to cover
- depth: overview vs executable commercial opportunities
- audience: who reads this and for what use
- geo_time: geography and time window
- must_include: must-answer questions

Return ONLY valid JSON:
```json
{{
  "questions": [
    {{
      "id": "q1",
      "category": "boundary",
      "question": "...",
      "hint": "optional",
      "options": ["optional choice A", "optional choice B"]
    }}
  ]
}}
```

Plain language. Match the user's language when the topic is Chinese. Max 4 questions."""


BRIEF_GENERATE_PROMPT = """You produce a ResearchBrief: a human-approved SEARCH PLAN with detailed retrieval directions.

Topic: {topic}

User clarifying answers (may be empty — then state assumed defaults):
{answers_block}

Selected framework skeleton (adapt; do not invent an unrelated structure):
{framework_block}

Hard rules:
1. Stay inside the TARGET INDUSTRY / commercial question. Do NOT make country GDP or general macroeconomy a primary direction unless the user explicitly asked.
2. Produce exactly 4–6 research DIRECTIONS (dimensions). Each direction must include:
   - title: short label
   - research_goal: one sentence outcome
   - direction_detail: a DETAILED paragraph (80–180 words / 150–350 Chinese characters) explaining WHAT to search, WHY it matters for answering the topic, WHAT kinds of sources/data to prefer, and what would count as a good answer for this direction
   - queries: 2–4 concrete searchable query strings (industry-specific, not vague)
   - priority, info_type, phase_id
3. Fill deprioritize (exclude GDP/macro unless asked).
4. If answers are missing, list assumed_defaults and mention them in overview_markdown.
5. overview_markdown: short plan overview for the reviewer (directions list + assumptions).
6. success_criteria: 3–5 questions the final report must answer (e.g. market shares, opportunities).

Return ONLY valid JSON:
```json
{{
  "problem_restatement": "...",
  "framework_id": "{framework_id}",
  "phases": [{{"id": "...", "title": "...", "goal": "..."}}],
  "dimensions": [
    {{
      "title": "...",
      "research_goal": "...",
      "direction_detail": "Detailed retrieval paragraph...",
      "queries": ["...", "..."],
      "priority": 1,
      "info_type": "facts",
      "phase_id": "..."
    }}
  ],
  "deprioritize": ["..."],
  "source_prefs": ["..."],
  "success_criteria": ["..."],
  "assumed_defaults": ["..."],
  "overview_markdown": "..."
}}
```

Match the user's language when the topic is Chinese."""


BRIEF_REVISE_PROMPT = """Revise this ResearchBrief based on user feedback. Keep industry focus; do not add GDP/macro as a primary direction unless feedback asks for it. Keep 4–6 directions with rich direction_detail paragraphs.

Current brief JSON:
{brief_json}

User feedback:
{feedback}

Return the full updated brief as ONLY valid JSON with the same schema
(problem_restatement, framework_id, phases, dimensions with direction_detail,
deprioritize, source_prefs, success_criteria, assumed_defaults, overview_markdown)."""


def _fallback_questions(topic: str) -> list[dict]:
    return [
        {
            "id": "q1",
            "category": "boundary",
            "question": "Should we exclude general country macro/GDP and stay inside the industry?",
            "hint": "Usually yes for market-entry briefs",
            "options": [
                "Yes — industry only, deprioritize GDP/macro",
                "Also include light macro context",
            ],
        },
        {
            "id": "q2",
            "category": "breadth",
            "question": "Which product / segment lines matter most?",
            "hint": "e.g. consumer mobile, B2B, wholesale, cloud/ICT",
            "options": [],
        },
        {
            "id": "q3",
            "category": "depth",
            "question": "Do you need executable opportunity paths and barriers, or mainly market overview?",
            "hint": "Interview prep vs internal proposal",
            "options": [
                "Overview + key players",
                "Overview + opportunities and barriers",
            ],
        },
        {
            "id": "q4",
            "category": "audience",
            "question": "Who is the primary reader and what will they use this for?",
            "hint": "e.g. sales interview, internal memo",
            "options": [],
        },
    ]


async def generate_industry_clarifying_questions(topic: str) -> list[dict]:
    """2–4 industry-research clarifying questions (no web search)."""
    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[
            {"role": "user", "content": INDUSTRY_CLARIFY_PROMPT.format(topic=topic)},
        ],
        temperature=0.4,
        max_tokens=700,
    )
    raw = _parse_json_object(response.choices[0].message.content or "")
    questions: list[dict] = []
    for i, item in enumerate(raw.get("questions") or []):
        if isinstance(item, str):
            questions.append({
                "id": f"q{i + 1}",
                "category": "boundary",
                "question": item,
                "hint": "",
                "options": [],
            })
            continue
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        opts = item.get("options") or []
        if not isinstance(opts, list):
            opts = []
        questions.append({
            "id": str(item.get("id") or f"q{i + 1}"),
            "category": str(item.get("category") or "boundary"),
            "question": question,
            "hint": str(item.get("hint") or ""),
            "options": [str(o) for o in opts if str(o).strip()][:6],
        })
    if not questions:
        questions = _fallback_questions(topic)
    return questions[:4]


def _answers_block(answers: dict[str, str], questions: list[dict]) -> str:
    text = format_human_feedback(answers, questions)
    return text or "(No answers provided — use framework defaults and list assumed_defaults.)"


def _parse_brief_payload(
    raw: dict,
    *,
    topic: str,
    framework_id: str,
    answers: dict[str, str],
) -> ResearchBrief:
    dims: list[BriefDimension] = []
    for item in raw.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        queries = [
            str(q).strip() for q in (item.get("queries") or [])
            if str(q).strip()
        ][:8]
        dims.append(BriefDimension(
            title=title,
            research_goal=str(item.get("research_goal") or "").strip(),
            direction_detail=str(item.get("direction_detail") or "").strip()[:2500],
            queries=queries,
            priority=int(item.get("priority") or 1),
            info_type=str(item.get("info_type") or "facts"),
            phase_id=str(item.get("phase_id") or ""),
        ))

    if not dims:
        fw = get_framework(framework_id)
        for phase in fw.get("phases") or []:
            goal = str(phase.get("goal") or "")
            dims.append(BriefDimension(
                title=str(phase.get("title") or phase.get("id") or "Research"),
                research_goal=goal,
                direction_detail=goal,
                queries=[f"{topic} {phase.get('title', '')}".strip()],
                phase_id=str(phase.get("id") or ""),
            ))

    phases = raw.get("phases") if isinstance(raw.get("phases"), list) else []
    deps = [str(d).strip() for d in (raw.get("deprioritize") or []) if str(d).strip()]
    fw_deps = [str(d) for d in (get_framework(framework_id).get("default_deprioritize") or [])]
    for d in fw_deps:
        if d not in deps:
            deps.append(d)

    return ResearchBrief(
        topic=topic,
        problem_restatement=str(raw.get("problem_restatement") or topic).strip(),
        framework_id=str(raw.get("framework_id") or framework_id),
        clarify_answers=dict(answers),
        phases=[p for p in phases if isinstance(p, dict)],
        dimensions=dims,
        deprioritize=deps,
        source_prefs=[str(s).strip() for s in (raw.get("source_prefs") or []) if str(s).strip()],
        success_criteria=[
            str(s).strip() for s in (raw.get("success_criteria") or []) if str(s).strip()
        ],
        assumed_defaults=[
            str(s).strip() for s in (raw.get("assumed_defaults") or []) if str(s).strip()
        ],
        overview_markdown=str(raw.get("overview_markdown") or "").strip(),
        confirmed=False,
    )


async def generate_research_brief(
    topic: str,
    *,
    answers: dict[str, str] | None = None,
    questions: list[dict] | None = None,
    framework_id: str | None = None,
) -> ResearchBrief:
    """LLM ResearchBrief from framework skeleton + clarifying answers."""
    answers = answers or {}
    questions = questions or []
    fid = framework_id or select_framework_id(topic)
    prompt = BRIEF_GENERATE_PROMPT.format(
        topic=topic,
        answers_block=_answers_block(answers, questions),
        framework_block=framework_prompt_block(fid),
        framework_id=fid,
    )
    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )
    raw = _parse_json_object(response.choices[0].message.content or "")
    return _parse_brief_payload(raw, topic=topic, framework_id=fid, answers=answers)


async def revise_research_brief(
    brief: ResearchBrief,
    feedback: str,
) -> ResearchBrief:
    """Revise an existing brief from human feedback."""
    payload = brief.model_dump()
    payload.pop("confirmed", None)
    prompt = BRIEF_REVISE_PROMPT.format(
        brief_json=json.dumps(payload, ensure_ascii=False, indent=2),
        feedback=feedback.strip(),
    )
    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )
    raw = _parse_json_object(response.choices[0].message.content or "")
    if not raw:
        return brief
    return _parse_brief_payload(
        raw,
        topic=brief.topic,
        framework_id=brief.framework_id,
        answers=brief.clarify_answers,
    )


def brief_seed_queries(brief: ResearchBrief, *, max_queries: int = 18) -> list[str]:
    """Round-robin queries across directions so every direction gets search budget."""
    blocked = _deprioritize_patterns(brief.deprioritize)
    dims = sorted(brief.dimensions, key=lambda d: d.priority)
    per_dim: list[list[str]] = []
    for dim in dims:
        bucket: list[str] = []
        for q in dim.queries:
            q = q.strip()
            if q and not _matches_deprioritize(q, blocked) and q not in bucket:
                bucket.append(q)
        seed = f"{brief.topic} {dim.research_goal or dim.title}".strip()
        if seed and not _matches_deprioritize(seed, blocked) and seed not in bucket:
            bucket.append(seed)
        if dim.direction_detail:
            # Pull a short keyword seed from detail first clause
            tip = dim.direction_detail.strip().split("。")[0].split(".")[0][:80]
            if tip:
                extra = f"{brief.topic} {tip}".strip()
                if extra not in bucket and not _matches_deprioritize(extra, blocked):
                    bucket.append(extra)
        per_dim.append(bucket)

    out: list[str] = []
    seen: set[str] = set()
    # Round-robin so direction 1..N each get a turn before stacking
    max_len = max((len(b) for b in per_dim), default=0)
    for i in range(max_len):
        for bucket in per_dim:
            if i >= len(bucket):
                continue
            q = bucket[i]
            if q not in seen:
                out.append(q)
                seen.add(q)
            if len(out) >= max_queries:
                return out
    return out[:max_queries]


def brief_direction_queries(
    brief: ResearchBrief,
    missing_ids: list[str],
    *,
    max_queries: int = 8,
) -> list[str]:
    """Queries only for missing coverage direction ids."""
    blocked = _deprioritize_patterns(brief.deprioritize)
    id_list = brief_gap_dimension_ids(brief)
    missing = set(missing_ids)
    out: list[str] = []
    for dim_id, dim in zip(id_list, brief.dimensions):
        if dim_id not in missing:
            continue
        for q in dim.queries:
            q = q.strip()
            if q and not _matches_deprioritize(q, blocked) and q not in out:
                out.append(q)
            if len(out) >= max_queries:
                return out
        seed = f"{brief.topic} {dim.research_goal or dim.title}".strip()
        if seed and seed not in out and not _matches_deprioritize(seed, blocked):
            out.append(seed)
    return out[:max_queries]


def _deprioritize_patterns(items: list[str]) -> list[str]:
    pats: list[str] = []
    for item in items:
        low = item.lower()
        pats.append(low)
        # Common GDP/macro tokens
        if "gdp" in low or "macro" in low:
            pats.extend(["gdp", "gross domestic product", "macroeconom", "瑞士gdp", "瑞士经济概况"])
    return list(dict.fromkeys(pats))


def _matches_deprioritize(text: str, patterns: list[str]) -> bool:
    t = text.lower()
    return any(p and p in t for p in patterns)


def filter_queries_by_deprioritize(
    queries: list[str],
    deprioritize: list[str],
) -> list[str]:
    blocked = _deprioritize_patterns(deprioritize)
    return [q for q in queries if not _matches_deprioritize(q, blocked)]


def brief_gap_dimension_ids(brief: ResearchBrief) -> list[str]:
    """Stable dimension keys for coverage."""
    ids: list[str] = []
    for i, dim in enumerate(brief.dimensions):
        key = (dim.phase_id or re.sub(r"[^a-z0-9]+", "_", dim.title.lower()).strip("_") or f"dim_{i}")
        if key not in ids:
            ids.append(key)
        else:
            ids.append(f"{key}_{i}")
    return ids
