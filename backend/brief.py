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


BRIEF_GENERATE_PROMPT = """You write a Gemini-style RESEARCH PLAN (搜索概览 / 研究计划) for deep web research.

Topic: {topic}

User clarifying answers (may be empty — state assumed defaults):
{answers_block}

Coverage checklist (use ONLY as angles to cover — NEVER copy these English titles into the plan):
{framework_block}

Output language: SAME as the topic (Chinese topic → Chinese plan).

Write 5–6 numbered research DIRECTIONS. Each direction is a concrete search instruction, like:

Good examples (style to imitate):
- 调研瑞士跨境电商市场规模、消费习惯及对中国商品的总体需求与买家偏好。
- 梳理适合中国商品出口瑞士的高潜力品类，如消费电子、家居用品、户外运动装备和时尚服饰等。
- 评估中国卖家进入瑞士的主要销售渠道，包括本土平台（如 Galaxus）、国际电商平台（如 Temu、AliExpress、Amazon）及 DTC 独立站模式。
- 研究中瑞贸易政策与法规，包括中瑞自贸协定关税优惠、增值税（MWST）及合规认证要求。

Bad examples (FORBIDDEN):
- "Demand segments and use cases"
- "Industry structure and competitive landscape"
- research_goal that only repeats the English checklist
- queries like "{{topic}} Demand segments and use cases"

Hard rules:
1. Stay inside the topic industry/commerce. Deprioritize country GDP/macro unless the user asked.
2. Each direction MUST have:
   - title: short label in the topic language (≤20 chars), e.g. 「运营商格局」「监管准入」
   - direction_detail: ONE full instruction sentence (or two short sentences) naming concrete objects — markets, companies, platforms, regulators, products, metrics. Start with a verb: 调研/梳理/评估/研究/分析/对比…
   - research_goal: what a good answer looks like (one sentence)
   - queries: 2–4 REAL search strings with entities (e.g. "Swisscom Sunrise Salt market share 2024", "BAKOM telecom license Switzerland"). Mix EN/DE when the market is Switzerland/DACH. NEVER use "topic + English phase title".
   - priority (1=highest), info_type, phase_id (may map to checklist ids)
3. overview_markdown: paste the plan as a numbered list of the direction_detail lines (for human review).
4. success_criteria: 3–5 must-answer questions.
5. deprioritize + assumed_defaults as needed.

Return ONLY valid JSON:
```json
{{
  "problem_restatement": "...",
  "framework_id": "{framework_id}",
  "phases": [],
  "dimensions": [
    {{
      "title": "短标题",
      "research_goal": "该方向答完后应得到什么",
      "direction_detail": "调研……（完整可执行指令）",
      "queries": ["entity-rich query 1", "entity-rich query 2"],
      "priority": 1,
      "info_type": "facts",
      "phase_id": "industry_structure"
    }}
  ],
  "deprioritize": ["..."],
  "source_prefs": ["..."],
  "success_criteria": ["..."],
  "assumed_defaults": ["..."],
  "overview_markdown": "(1) …\\n(2) …"
}}
```"""


BRIEF_REVISE_PROMPT = """Revise this research plan based on user feedback.

Keep Gemini-style numbered directions: each direction_detail must be a concrete verb-led instruction
with named entities (markets, firms, platforms, regulators). Do NOT revert to English skeleton titles
like "Demand segments and use cases". Keep 5–6 directions. Same language as the topic.

Current brief JSON:
{brief_json}

User feedback:
{feedback}

Return ONLY valid JSON with the same schema
(problem_restatement, framework_id, phases, dimensions with direction_detail + entity-rich queries,
deprioritize, source_prefs, success_criteria, assumed_defaults, overview_markdown)."""


_ENGLISH_SKELETON_TITLES = {
    "industry structure and competitive landscape",
    "regulation and market access",
    "demand segments and use cases",
    "entrant capabilities and comparable products",
    "commercial opportunities and business models",
    "risks and barriers",
    "rough opportunity sizing",
    "industry overview",
    "market size and drivers",
    "key players",
    "trends and outlook",
    "risks and open questions",
    "player map",
    "shares and ranking",
    "product and offer comparison",
    "competitive dynamics",
    "fundraising",
    "deal volume and deployment",
    "returns and spreads",
    "credit risk",
    "products and evergreen structures",
    "relative value",
}


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


def _topic_is_zh(topic: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", topic))


def _is_skeleton_title(title: str) -> bool:
    t = title.strip().lower()
    if t in _ENGLISH_SKELETON_TITLES:
        return True
    return _contains_skeleton_phrase(t)


def _contains_skeleton_phrase(text: str) -> bool:
    """True if text embeds a known English framework skeleton label."""
    low = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not low:
        return False
    return any(s in low for s in _ENGLISH_SKELETON_TITLES)


_INSTRUCTION_VERBS_ZH = ("调研", "梳理", "评估", "研究", "分析", "对比", "探索", "综合", "查找", "绘制", "追踪", "概述")
_INSTRUCTION_VERBS_EN = (
    "research", "map", "identify", "assess", "analyze", "compare", "survey",
    "evaluate", "explore", "outline", "review", "examine",
)


def _is_good_instruction(text: str, topic: str) -> bool:
    """Gemini-style plan line: verb-led, concrete, not an English skeleton dump."""
    t = (text or "").strip()
    if len(t) < 16:
        return False
    if _contains_skeleton_phrase(t) or t.strip().lower() in _ENGLISH_SKELETON_TITLES:
        return False
    # English goal fragments like "Who buys what — B2B..."
    if re.match(r"^(who|what|how|why|where|which)\b", t, re.I) and not _topic_is_zh(t):
        if _topic_is_zh(topic):
            return False
    if _topic_is_zh(topic):
        # Chinese topic → instruction should be mostly Chinese + start with a verb
        if not re.search(r"[\u4e00-\u9fff]", t):
            return False
        if not any(t.startswith(v) for v in _INSTRUCTION_VERBS_ZH):
            return False
        return True
    low = t.lower()
    return any(low.startswith(v) for v in _INSTRUCTION_VERBS_EN)


def _weak_query(q: str, topic: str, title: str) -> bool:
    qn = re.sub(r"\s+", " ", q.strip().lower())
    if not qn or len(qn) < 8:
        return True
    if _contains_skeleton_phrase(qn):
        return True
    # "topic + English title" pattern
    combo = re.sub(r"\s+", " ", f"{topic} {title}".strip().lower())
    if qn == combo or (title and qn.endswith(title.strip().lower())):
        return True
    if _is_skeleton_title(title) and title.lower() in qn:
        return True
    return False


def _topic_hints(topic: str) -> dict[str, bool]:
    t = topic.lower()
    return {
        "telecom": any(k in topic or k in t for k in (
            "电信", "运营商", "联通", "移动", "电信", "swisscom", "sunrise", "salt",
            "telecom", "mvno", "5g", "mobile",
        )),
        "swiss": any(k in topic or k in t for k in ("瑞士", "switzerland", "swiss", "zürich", "zurich")),
        "china": any(k in topic or k in t for k in ("中国", "china", "联通", "中资", "出海")),
        "ecommerce": any(k in topic or k in t for k in (
            "跨境", "电商", "ecommerce", "e-commerce", "temu", "galaxus", "amazon",
        )),
    }


def _instruction_from_phase(topic: str, phase: dict) -> str:
    """Deterministic verb-led instruction when LLM dumps skeleton text."""
    pid = str(phase.get("id") or "")
    goal = str(phase.get("goal") or phase.get("title") or "")
    zh = _topic_is_zh(topic)
    hints = _topic_hints(topic)

    # Domain-specific Gemini-style plans (preferred over generic templates)
    if zh and hints["telecom"] and hints["swiss"]:
        telecom_zh = {
            "industry_structure": (
                "调研瑞士电信市场的规模、增速与竞争格局，梳理 Swisscom、Sunrise、Salt 等主要运营商"
                "的市占、用户数与收入结构（不含瑞士宏观经济/GDP）。"
            ),
            "regulation": (
                "研究瑞士电信监管与市场准入：BAKOM/ComCom 职责、频谱与牌照、MVNO/批发规则，"
                "以及外资或新进入者的合规门槛（围绕「{topic}」）。"
            ).format(topic=topic),
            "demand_segments": (
                "梳理瑞士电信需求细分与使用场景：消费移动、B2B/政企、华人/侨民漫游、批发/MVNO、"
                "固网宽带与 ICT/云，并判断哪些细分对「{topic}」最有商业价值。"
            ).format(topic=topic),
            "own_capabilities": (
                "对比中国联通（或进入方）可输出的产品能力与瑞士在位运营商/MVNO 的可比套餐、"
                "国际漫游、政企与跨境连接服务，找出可对标与差异化点。"
            ),
            "opportunities": (
                "评估「{topic}」的具体进入路径与商业模式：批发/漫游合作、MVNO、政企专线、"
                "华人市场 niche、与本地运营商/渠道伙伴的合作方式。"
            ).format(topic=topic),
            "risks": (
                "分析进入瑞士电信市场的主要风险：在位者竞争、监管与频谱门槛、渠道与品牌、"
                "资本强度与本地化运营要求。"
            ),
            "sizing": (
                "在有公开数据的前提下，粗估与「{topic}」相关的机会数量级（用户/收入区间），"
                "并明确标注数据缺口与不确定性。"
            ).format(topic=topic),
        }
        if pid in telecom_zh:
            return telecom_zh[pid]

    if zh and hints["ecommerce"] and hints["swiss"]:
        ecom_zh = {
            "industry_structure": (
                "调研瑞士跨境电商市场规模、消费习惯及对中国商品的总体需求与买家偏好。"
            ),
            "demand_segments": (
                "梳理适合中国商品出口瑞士的高潜力品类，如消费电子、家居用品、户外运动装备和时尚服饰等。"
            ),
            "opportunities": (
                "评估中国卖家进入瑞士的主要销售渠道，包括本土平台（如 Galaxus）、国际电商平台"
                "（如 Temu、AliExpress、Amazon）及 DTC 独立站模式。"
            ),
            "regulation": (
                "研究中瑞贸易政策与法规，包括中瑞自贸协定关税优惠、瑞士工业品关税政策、"
                "增值税（MWST）及合规认证要求。"
            ),
            "own_capabilities": (
                "探索跨境物流与交付方案，分析最后一公里配送、退换货流程及瑞士本土主流支付方式"
                "（如 TWINT、账单支付）。"
            ),
            "risks": (
                "综合分析中国商品在瑞士市场的核心竞争优势、潜在风险（如高标准服务需求、多语言运营）"
                "及落地建议。"
            ),
        }
        if pid in ecom_zh:
            return ecom_zh[pid]

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
    hints = _topic_hints(topic)
    seeds: list[str] = []
    if hints["telecom"] and hints["swiss"]:
        seeds.extend([
            "Swisscom Sunrise Salt market share Switzerland 2024",
            "BAKOM ComCom telecom license Switzerland MVNO",
            "Switzerland mobile subscribers ARPU B2B enterprise",
            "China Unicom Switzerland roaming wholesale partnership",
        ])
    elif hints["ecommerce"] and hints["swiss"]:
        seeds.extend([
            "Switzerland cross-border e-commerce market size China",
            "Galaxus Temu AliExpress Switzerland Chinese sellers",
            "Switzerland MWST import VAT China FTA customs",
            "TWINT Switzerland online payment last mile delivery",
        ])
    # Pull Latin / Chinese entity tokens from the instruction
    for token in re.findall(
        r"[A-Za-z][A-Za-z0-9&.-]{2,}|[\u4e00-\u9fff]{2,8}", detail or ""
    ):
        if token.lower() in {"the", "and", "for", "with", "from", "that", "this"}:
            continue
        tip = f"{token} {topic}".strip() if hints["swiss"] else f"{topic} {token}".strip()
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


def _parse_brief_payload(
    raw: dict,
    *,
    topic: str,
    framework_id: str,
    answers: dict[str, str],
) -> ResearchBrief:
    fw = get_framework(framework_id)
    phase_by_id = {
        str(p.get("id") or ""): p for p in (fw.get("phases") or []) if isinstance(p, dict)
    }

    dims: list[BriefDimension] = []
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
        if not _is_good_instruction(detail, topic):
            phase = phase_by_id.get(phase_id) or {"id": phase_id, "goal": goal or title}
            detail = _instruction_from_phase(topic, phase)
            title = _short_title_from_instruction(detail, phase_id or "方向")
            goal = detail
        elif _is_skeleton_title(title) or not title:
            title = _short_title_from_instruction(detail, phase_id or title or "方向")

        queries = [
            str(q).strip() for q in (item.get("queries") or [])
            if str(q).strip()
        ][:8]
        queries = _repair_queries(topic, title, detail, queries)
        dims.append(BriefDimension(
            title=title[:200] or "方向",
            research_goal=goal or detail[:200],
            direction_detail=detail,
            queries=queries,
            priority=int(item.get("priority") or 1),
            info_type=str(item.get("info_type") or "facts"),
            phase_id=phase_id,
        ))

    # If still mostly bad, full rebuild from checklist
    bad_count = sum(1 for d in dims if not _is_good_instruction(d.direction_detail, topic))
    skeletonish = not dims or bad_count >= max(2, (len(dims) + 1) // 2)
    if skeletonish:
        rebuilt: list[BriefDimension] = []
        for i, phase in enumerate((fw.get("phases") or [])[:6]):
            instruction = _instruction_from_phase(topic, phase)
            title = _short_title_from_instruction(instruction, str(phase.get("id") or f"d{i}"))
            rebuilt.append(BriefDimension(
                title=title,
                research_goal=instruction,
                direction_detail=instruction,
                queries=_repair_queries(topic, title, instruction, []),
                priority=i + 1,
                phase_id=str(phase.get("id") or ""),
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
            dims.append(BriefDimension(
                title=title,
                research_goal=instruction,
                direction_detail=instruction,
                queries=_repair_queries(topic, title, instruction, []),
                priority=len(dims) + 1,
                phase_id=pid,
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
