"""Industry ResearchBrief: clarify → generate → revise (Wave 12a).

No web search during brief generation — LLM + framework skeletons only.
"""

from __future__ import annotations

import json
import re

from brief_rubric import (
    INSTRUCTION_VERBS_ZH as _INSTRUCTION_VERBS_ZH,
    RubricResult,
    check_direction,
    check_instruction,
    contains_skeleton_phrase,
    harvest_entities,
    is_skeleton_title,
    topic_is_zh,
    weak_query,
)
from frameworks import (
    example_instruction,
    example_seed_queries,
    few_shot_block,
    framework_forbidden_phrases,
    framework_prompt_block,
    get_framework,
    select_framework_id,
)
from llm_context import get_openai_client, get_request_keys, get_strong_model
from meta import _parse_json_object, format_human_feedback
from models import BriefDimension, ResearchBrief
from config import config


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


BRIEF_SYSTEM_PROMPT = """你是资深行业研究策划（不是百科问答助手）。你的唯一任务：把用户选题写成「Gemini 搜索概览」风格的研究计划。

什么叫好的研究计划：
- 5–6 条编号方向，每条是一条完整、可执行的检索指令。
- 动词开头（调研/梳理/评估/研究/分析/对比/探索），点名具体对象：市场、品类、平台、监管、物流、支付、公司、指标。
- 每条 direction_detail 至少含 2 个具名实体；entities 与 must_answer 必填。
- 读完就能直接拿去搜；不是栏目名、不是英文骨架、不是空泛「机会分析」。

════════════════════════════════
【金标准范例】{few_shot_examples}
════════════════════════════════

【禁止输出】（出现即不合格）
- 英文栏目名：Demand segments and use cases / Rough opportunity sizing / Industry structure…
- 把 checklist 的英文 goal 原样粘贴，例如 Order-of-magnitude revenue/TAM…
- 查询写成「选题 + 英文标题」：中国商品… Rough opportunity sizing
- 只有抽象词：市场分析、机会研究、竞争格局（无实体）

【硬规则】
1. 输出语言 = 选题语言（中文选题 → 全文中文指令；queries 可中英德混用以提高检索命中）。
2. 每条 direction_detail = 一整句可执行指令（可两句，但必须具体）；title = ≤12 字中文短标签。
3. research_goal = 该方向答完后应得到什么（中文一句），不得照抄英文。
4. queries：2–4 条真实可搜字符串，必须含实体名（平台/监管/品类/公司），禁止「topic + English label」。
5. 紧扣选题行业；除非用户要求，否则降权国家 GDP/宏观百科。
6. overview_markdown = 把 5–6 条 direction_detail 编成 (1)(2)(3)… 列表（与金标准同格式）。

只返回合法 JSON，不要 markdown 解释。"""


BRIEF_GENERATE_PROMPT = """请为下面选题生成研究计划 JSON。

选题：{topic}

用户澄清答案（可能为空——请写出 assumed_defaults）：
{answers_block}

覆盖角度清单（只参考 angle_id 与中文提示；禁止粘贴任何英文标签）：
{framework_block}

JSON schema：
{{
  "problem_restatement": "用一句话重述研究问题",
  "framework_id": "{framework_id}",
  "phases": [],
  "dimensions": [
    {{
      "title": "短中文标题",
      "research_goal": "答完本方向应得到什么（中文）",
      "direction_detail": "调研/梳理/评估……（完整可执行指令，含具体实体）",
      "entities": ["具名实体1", "具名实体2"],
      "must_answer": ["本方向必须回答的具体问题"],
      "queries": ["含实体的检索词1", "含实体的检索词2"],
      "priority": 1,
      "info_type": "facts",
      "phase_id": "对应 angle_id"
    }}
  ],
  "deprioritize": ["..."],
  "source_prefs": ["..."],
  "success_criteria": ["报告必须回答的问题1", "..."],
  "assumed_defaults": ["..."],
  "overview_markdown": "(1) …\\n(2) …\\n(3) …"
}}

务必写出 5–6 条 dimensions，质量对齐金标准范例。"""


BRIEF_REVISE_PROMPT = """根据用户反馈修订研究计划。保持 Gemini 搜索概览风格：每条 direction_detail 必须是动词开头、含具名实体的完整中文指令。禁止退回英文骨架标题或英文 goal。保持 5–6 条。语言与选题一致。

当前 brief JSON：
{brief_json}

用户反馈：
{feedback}

只返回同 schema 的合法 JSON。"""


BRIEF_REWRITE_PROMPT = """以下研究方向未通过质量校验，请只重写这些条目，其余方向不要动。

选题：{topic}

不合格条目与原因：
{failures}

重写要求：
- 保持每条的 phase_id 与 priority 不变。
- direction_detail：动词开头的完整中文指令，30–120 字，至少 2 个具名实体（平台/监管/公司/品类/指标）。
- research_goal：答完该方向应得到什么产出物，措辞不得与 direction_detail 重复。
- entities：≥2 个具名实体；must_answer：1–2 个具体问题。
- queries：2–4 条含实体的可搜字符串，禁止「选题 + 英文标题」。

只返回被重写条目的 JSON：{{"dimensions": [ ... ]}}"""


def get_brief_model() -> str:
    """Planning step uses the strongest available model (never weak BYOK aliases)."""
    return get_strong_model()


def _fallback_questions(topic: str) -> list[dict]:
    if _topic_is_zh(topic):
        return [
            {
                "id": "q1",
                "category": "boundary",
                "question": "是否排除该国宏观/GDP，只做目标行业本身？",
                "hint": "市场进入类选题通常选「只做行业」",
                "options": [
                    "是 — 只做行业，弱化 GDP/宏观",
                    "也需要少量宏观背景",
                ],
            },
            {
                "id": "q2",
                "category": "breadth",
                "question": "最关键的产品线 / 细分市场是哪些？",
                "hint": "例如：消费移动、B2B、批发、云/ICT",
                "options": [],
            },
            {
                "id": "q3",
                "category": "depth",
                "question": "需要可执行的进入路径与壁垒，还是以市场概览为主？",
                "hint": "面试准备 vs 内部提案",
                "options": [
                    "概览 + 主要玩家",
                    "概览 + 机会与壁垒",
                ],
            },
            {
                "id": "q4",
                "category": "audience",
                "question": "主要读者是谁、报告将用于什么决策？",
                "hint": "例如：销售面试、内部备忘",
                "options": [],
            },
        ]
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
        model=get_brief_model(),
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


# Rubric owns the judging vocabulary (Wave 12h Step 87); brief keeps thin aliases.
_topic_is_zh = topic_is_zh
_is_skeleton_title = is_skeleton_title
_contains_skeleton_phrase = contains_skeleton_phrase
_weak_query = weak_query
_harvest_entities = harvest_entities


def _is_good_instruction(text: str, topic: str, *, forbidden: set[str] | None = None) -> bool:
    return check_instruction(text, topic, forbidden=forbidden).ok


def _instruction_from_phase(topic: str, phase: dict) -> str:
    """Last-resort verb-led instruction when the LLM still dumps skeleton text.

    Domain wording lives in frameworks/examples/*.yaml, never in code.
    """
    pid = str(phase.get("id") or "")
    goal = str(phase.get("goal") or phase.get("title") or "")
    zh = _topic_is_zh(topic)

    from_example = example_instruction(topic, pid)
    if from_example:
        return from_example

    templates_zh = {
        "industry_structure": f"调研「{topic}」所在市场的规模、增速、主要玩家与市场份额（聚焦行业本身，不含宏观经济/GDP）。",
        "regulation": f"研究进入该市场的监管与准入要求：主管机构、牌照/许可、外资限制与合规门槛（围绕「{topic}」）。",
        "demand_segments": f"梳理「{topic}」相关的需求细分与使用场景：谁在买、买什么、哪些细分最有商业价值。",
        "own_capabilities": f"对比进入方/主角能力与当地可比产品或服务，找出差异化与可对标的产品线（「{topic}」）。",
        "opportunities": f"评估「{topic}」的具体商业机会与进入路径：合作、渠道、定价与可行商业模式。",
        "risks": f"分析「{topic}」落地的主要风险与障碍：竞争、监管、渠道、品牌与资本强度。",
        "sizing": f"在有公开数据的前提下，粗估「{topic}」相关机会的数量级，并标明不确定性。",
        "overview": f"概述「{topic}」所属行业的定义、范围与当前状态。",
        "size_drivers": f"调研「{topic}」相关市场规模与关键增长/需求驱动因素。",
        "players": f"梳理「{topic}」领域的主要玩家、挑战者与利基参与者。",
        "trends": f"分析「{topic}」的技术、监管与客户趋势及短期展望。",
        "player_map": f"绘制「{topic}」竞争玩家地图：分段与定位。",
        "shares": f"查找「{topic}」相关市占、用户数或收入排名等公开数据。",
        "products": f"对比「{topic}」相关产品/套餐/渠道差异。",
        "dynamics": f"追踪「{topic}」竞争动态：并购、监管冲击与新进入者。",
    }
    templates_en = {
        "industry_structure": f"Map market size, growth, and competitor shares for «{topic}» (industry only, not GDP/macro).",
        "regulation": f"Research regulators, licenses, and foreign-entry rules relevant to «{topic}».",
        "demand_segments": f"Identify buyer segments and use cases that matter for «{topic}».",
        "opportunities": f"Assess concrete commercial entry paths and business models for «{topic}».",
        "risks": f"Analyze competitive, regulatory, and channel barriers for «{topic}».",
    }
    if zh:
        return templates_zh.get(pid) or f"调研并梳理「{topic}」：{goal}"
    return templates_en.get(pid) or f"Research «{topic}»: {goal}"


def _short_title_from_instruction(instruction: str, fallback: str) -> str:
    text = (instruction or "").strip()
    if not text:
        return fallback[:20] if fallback else "方向"
    # Strip leading verb for a short label
    for verb in ("调研", "梳理", "评估", "研究", "分析", "对比", "探索", "综合"):
        if text.startswith(verb):
            text = text[len(verb):].lstrip("：: ")
            break
    # Take up to first comma/顿号/与
    for sep in ("，", "、", ",", "及", "和", "（", "("):
        if sep in text:
            text = text.split(sep, 1)[0]
            break
    text = text.strip("「」\"' ")
    if len(text) > 18:
        text = text[:18]
    return text or fallback[:20] or "方向"


def _seed_queries_for_topic(topic: str, detail: str) -> list[str]:
    """Entity-rich fallback queries when LLM emits topic+skeleton titles."""
    seeds: list[str] = list(example_seed_queries(topic))
    # Pull named entities out of the instruction itself
    for token in harvest_entities(detail or "", max_n=8):
        tip = f"{topic} {token}".strip()
        if tip not in seeds:
            seeds.append(tip)
        if len(seeds) >= 6:
            break
    if topic not in seeds:
        seeds.insert(0, topic)
    return seeds[:6]


def _repair_queries(topic: str, title: str, detail: str, queries: list[str]) -> list[str]:
    kept = [q for q in queries if not _weak_query(q, topic, title)]
    if len(kept) >= 2:
        return kept[:4]
    seeds = _seed_queries_for_topic(topic, detail)
    if title and not _is_skeleton_title(title) and not _contains_skeleton_phrase(title):
        tip = f"{topic} {title}".strip()
        if tip not in seeds:
            seeds.append(tip)
    out: list[str] = []
    for q in kept + seeds:
        q = q.strip()
        if not q or q in out:
            continue
        if _weak_query(q, topic, title) and q != topic:
            continue
        out.append(q)
    if not out:
        out = [topic]
    return out[:4]


def _harvest_entities(text: str, *, max_n: int = 8) -> list[str]:
    """Pull named entities from instruction text when LLM omits entities[]."""
    from text_tokens import tokens as text_tokens

    skip = frozenset({
        "research", "researching", "map", "mapping", "analyze", "assess",
        "evaluate", "study", "review", "industry", "market", "demand",
        "调研", "梳理", "评估", "研究", "分析",
    })
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9&.-]{1,40})\b", text or ""):
        w = m.group(1)
        key = w.lower()
        if key in seen or key in skip or len(w) < 2:
            continue
        seen.add(key)
        found.append(w)
        if len(found) >= max_n:
            return found
    for tok in text_tokens(text or "", max_tokens=20):
        if not re.search(r"[\u4e00-\u9fff]", tok):
            continue
        if len(tok) < 2 or tok in seen or tok in skip:
            continue
        seen.add(tok)
        found.append(tok)
        if len(found) >= max_n:
            break
    return found


def _build_brief_dimension(
    *,
    title: str,
    goal: str,
    detail: str,
    queries: list[str],
    priority: int = 1,
    info_type: str = "facts",
    phase_id: str = "",
    direction_id: str = "",
    entities: list[str] | None = None,
    must_answer: list[str] | None = None,
    budget_weight: int = 1,
) -> BriefDimension:
    did = (direction_id or phase_id or title)[:80]
    ents = [str(e).strip() for e in (entities or []) if str(e).strip()][:8]
    if not ents:
        ents = _harvest_entities(f"{detail} {goal} {title}")
    answers = [str(a).strip() for a in (must_answer or []) if str(a).strip()][:6]
    weight = max(1, min(10, int(budget_weight or 1)))
    return BriefDimension(
        title=title[:200] or "方向",
        research_goal=(goal or detail)[:500],
        direction_detail=detail,
        queries=queries,
        priority=priority,
        info_type=info_type,
        phase_id=phase_id,
        direction_id=did,
        entities=ents,
        must_answer=answers,
        budget_weight=weight,
    )


def _parse_brief_payload(
    raw: dict,
    *,
    topic: str,
    framework_id: str,
    answers: dict[str, str],
) -> ResearchBrief:
    fw = get_framework(framework_id)
    forbidden = framework_forbidden_phrases(framework_id)
    phase_by_id = {
        str(p.get("id") or ""): p for p in (fw.get("phases") or []) if isinstance(p, dict)
    }

    dims: list[BriefDimension] = []
    fallback_ids: list[str] = []

    def _mark_fallback(direction_id: str) -> None:
        did = direction_id or "方向"
        if did not in fallback_ids:
            fallback_ids.append(did)

    for item in raw.get("dimensions") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        detail = str(item.get("direction_detail") or "").strip()[:2500]
        goal = str(item.get("research_goal") or "").strip()
        phase_id = str(item.get("phase_id") or "")
        if not title and not detail and not goal:
            continue
        # Prefer instruction text; lift goal into detail if needed
        if not detail:
            detail = goal or title

        # Replace skeleton / non-instructional dumps with topic-specific templates
        if not _is_good_instruction(detail, topic, forbidden=forbidden):
            phase = phase_by_id.get(phase_id) or {"id": phase_id, "goal": goal or title}
            detail = _instruction_from_phase(topic, phase)
            title = _short_title_from_instruction(detail, phase_id or "方向")
            goal = detail
            _mark_fallback(phase_id or title)
        elif (
            _is_skeleton_title(title)
            or _contains_skeleton_phrase(title, forbidden)
            or not title
        ):
            title = _short_title_from_instruction(detail, phase_id or title or "方向")

        if goal and not _is_good_instruction(goal, topic, forbidden=forbidden):
            # Keep Chinese research_goal only when instructional; else mirror detail
            goal = detail

        queries = [
            str(q).strip() for q in (item.get("queries") or [])
            if str(q).strip()
        ][:8]
        queries = _repair_queries(topic, title, detail, queries)
        dims.append(_build_brief_dimension(
            title=title[:200] or "方向",
            goal=(goal or detail)[:500],
            detail=detail,
            queries=queries,
            priority=int(item.get("priority") or 1),
            info_type=str(item.get("info_type") or "facts"),
            phase_id=phase_id,
            direction_id=str(item.get("direction_id") or phase_id),
            entities=[str(e) for e in (item.get("entities") or []) if str(e).strip()],
            must_answer=[str(a) for a in (item.get("must_answer") or []) if str(a).strip()],
            budget_weight=int(item.get("budget_weight") or max(1, 7 - int(item.get("priority") or 1))),
        ))

    # Second pass: any remaining bad instruction must be rewritten
    fixed: list[BriefDimension] = []
    for d in dims:
        if _is_good_instruction(d.direction_detail, topic, forbidden=forbidden):
            fixed.append(d)
            continue
        phase = phase_by_id.get(d.phase_id) or {"id": d.phase_id, "goal": d.title}
        instruction = _instruction_from_phase(topic, phase)
        title = _short_title_from_instruction(instruction, d.phase_id or d.title or "方向")
        _mark_fallback(d.direction_id or d.phase_id or title)
        fixed.append(_build_brief_dimension(
            title=title,
            goal=instruction,
            detail=instruction,
            queries=_repair_queries(topic, title, instruction, list(d.queries)),
            priority=d.priority,
            info_type=d.info_type,
            phase_id=d.phase_id,
            direction_id=d.direction_id or d.phase_id,
            entities=list(d.entities or []),
            must_answer=list(d.must_answer or []),
            budget_weight=d.budget_weight,
        ))
    dims = fixed

    # If still mostly bad, full rebuild from checklist
    bad_count = sum(
        1 for d in dims
        if not _is_good_instruction(d.direction_detail, topic, forbidden=forbidden)
    )
    skeletonish = not dims or bad_count >= max(1, (len(dims) + 1) // 2)
    if skeletonish:
        rebuilt: list[BriefDimension] = []
        for i, phase in enumerate((fw.get("phases") or [])[:6]):
            instruction = _instruction_from_phase(topic, phase)
            title = _short_title_from_instruction(instruction, str(phase.get("id") or f"d{i}"))
            _mark_fallback(str(phase.get("id") or title))
            rebuilt.append(_build_brief_dimension(
                title=title,
                goal=instruction,
                detail=instruction,
                queries=_repair_queries(topic, title, instruction, []),
                priority=i + 1,
                phase_id=str(phase.get("id") or ""),
                budget_weight=max(1, 6 - i),
            ))
        if rebuilt:
            dims = rebuilt

    # Cap 4–6
    dims = dims[:6]
    if len(dims) < 4:
        for phase in fw.get("phases") or []:
            if len(dims) >= 5:
                break
            pid = str(phase.get("id") or "")
            if any(d.phase_id == pid for d in dims):
                continue
            instruction = _instruction_from_phase(topic, phase)
            title = _short_title_from_instruction(instruction, pid or "方向")
            _mark_fallback(pid or title)
            dims.append(_build_brief_dimension(
                title=title,
                goal=instruction,
                detail=instruction,
                queries=_repair_queries(topic, title, instruction, []),
                priority=len(dims) + 1,
                phase_id=pid,
                budget_weight=max(1, 6 - len(dims)),
            ))

    phases = raw.get("phases") if isinstance(raw.get("phases"), list) else []
    deps = [str(d).strip() for d in (raw.get("deprioritize") or []) if str(d).strip()]
    fw_deps = [str(d) for d in (fw.get("default_deprioritize") or [])]
    for d in fw_deps:
        if d not in deps:
            deps.append(d)

    # Always rebuild overview from final instructions (Gemini numbered plan)
    overview = "\n".join(
        f"({i}) {d.direction_detail or d.research_goal or d.title}"
        for i, d in enumerate(dims, 1)
    )

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
        overview_markdown=overview,
        fallback_direction_ids=[
            fid for fid in fallback_ids
            if any((d.direction_id or d.phase_id or d.title) == fid for d in dims)
        ],
        confirmed=False,
    )


def _brief_system_prompt(topic: str) -> str:
    return BRIEF_SYSTEM_PROMPT.format(few_shot_examples=few_shot_block(topic))


def _judge_directions(
    dims: list[dict],
    topic: str,
    forbidden: set[str],
) -> list[tuple[int, dict, RubricResult]]:
    """Directions worth a rewrite, with the reasons to hand back to the LLM."""
    out: list[tuple[int, dict, RubricResult]] = []
    for i, item in enumerate(dims):
        result = check_direction(item, topic, forbidden=forbidden)
        if result.reasons:
            out.append((i, item, result))
    return out


async def _rewrite_failed_directions(
    raw: dict,
    *,
    topic: str,
    framework_id: str,
    model: str,
) -> dict:
    """Judge → rewrite only the failing directions → keep the better version."""
    dims = [d for d in (raw.get("dimensions") or []) if isinstance(d, dict)]
    if not dims:
        return raw
    forbidden = framework_forbidden_phrases(framework_id)
    failures = _judge_directions(dims, topic, forbidden)
    if not failures:
        return raw

    lines = []
    for i, item, result in failures[:6]:
        current = str(item.get("direction_detail") or item.get("research_goal") or "")
        lines.append(
            f"- index={i} phase_id={item.get('phase_id') or ''}\n"
            f"  当前：{current[:150]}\n"
            f"  问题：{result.explain_zh()}"
        )
    prompt = BRIEF_REWRITE_PROMPT.format(topic=topic, failures="\n".join(lines))
    try:
        response = await get_openai_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _brief_system_prompt(topic)},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=2500,
        )
    except Exception:
        return raw

    payload = _parse_json_object(response.choices[0].message.content or "")
    rewritten = [
        d for d in (payload.get("dimensions") or []) if isinstance(d, dict)
    ]
    if not rewritten:
        return raw

    by_phase = {
        str(d.get("phase_id") or ""): d
        for d in rewritten
        if str(d.get("phase_id") or "")
    }
    for pos, (index, item, result) in enumerate(failures):
        phase_id = str(item.get("phase_id") or "")
        candidate = by_phase.get(phase_id)
        if candidate is None and pos < len(rewritten) and not by_phase:
            candidate = rewritten[pos]
        if not candidate:
            continue
        merged = {**item, **{k: v for k, v in candidate.items() if v}}
        merged["phase_id"] = phase_id or str(candidate.get("phase_id") or "")
        merged["priority"] = item.get("priority") or pos + 1
        after = check_direction(merged, topic, forbidden=forbidden)
        improved = (after.ok and not result.ok) or len(after.reasons) < len(result.reasons)
        if improved:
            dims[index] = merged

    raw["dimensions"] = dims
    return raw


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
    model = get_brief_model()
    response = await get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _brief_system_prompt(topic)},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=5000,
    )
    raw = _parse_json_object(response.choices[0].message.content or "")
    raw = await _rewrite_failed_directions(
        raw, topic=topic, framework_id=fid, model=model,
    )
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
    model = get_brief_model()
    response = await get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _brief_system_prompt(brief.topic)},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=5000,
    )
    raw = _parse_json_object(response.choices[0].message.content or "")
    if not raw:
        return brief
    raw = await _rewrite_failed_directions(
        raw, topic=brief.topic, framework_id=brief.framework_id, model=model,
    )
    return _parse_brief_payload(
        raw,
        topic=brief.topic,
        framework_id=brief.framework_id,
        answers=brief.clarify_answers,
    )


def brief_seed_queries(brief: ResearchBrief, *, max_queries: int = 18) -> list[str]:
    """Round-robin queries across directions so every direction gets search budget."""
    blocked = _deprioritize_patterns(brief.deprioritize)
    forbidden = framework_forbidden_phrases(brief.framework_id)
    dims = sorted(brief.dimensions, key=lambda d: d.priority)
    per_dim: list[list[str]] = []
    for dim in dims:
        bucket: list[str] = []
        for q in dim.queries:
            q = q.strip()
            if (
                q
                and not _matches_deprioritize(q, blocked)
                and not _weak_query(q, brief.topic, dim.title)
                and q not in bucket
            ):
                bucket.append(q)
        # Never seed with English skeleton title/goal
        for candidate in (dim.direction_detail, dim.research_goal, dim.title):
            tip = (candidate or "").strip().split("。")[0].split(".")[0][:80]
            if not tip or _contains_skeleton_phrase(tip, forbidden):
                continue
            if _topic_is_zh(brief.topic) and not re.search(r"[\u4e00-\u9fff]", tip):
                continue
            # Prefer short keyword from Chinese instruction, not full sentence dump
            words = re.findall(r"[A-Za-z][A-Za-z0-9&.-]{2,}|[\u4e00-\u9fff]{2,6}", tip)
            for w in words[:3]:
                extra = f"{w} Switzerland" if "瑞士" in brief.topic else f"{brief.topic} {w}"
                extra = extra.strip()
                if (
                    extra
                    and extra not in bucket
                    and not _matches_deprioritize(extra, blocked)
                    and not _weak_query(extra, brief.topic, dim.title)
                ):
                    bucket.append(extra)
            break
        if not bucket:
            for q in _seed_queries_for_topic(brief.topic, dim.direction_detail or ""):
                if q not in bucket and not _matches_deprioritize(q, blocked):
                    bucket.append(q)
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
