"""Brief direction rubric (Wave 12h Step 87).

The engine judges; the LLM writes. Instead of rewriting bad directions with
regex, we score them and hand the failure reasons back for a targeted rewrite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from text_tokens import tokens as text_tokens

ENGLISH_SKELETON_TITLES = {
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
}

INSTRUCTION_VERBS_ZH = (
    "调研", "梳理", "评估", "研究", "分析", "对比", "探索", "综合",
    "查找", "绘制", "追踪", "概述", "粗估", "量化", "复盘", "识别",
)
INSTRUCTION_VERBS_EN = (
    "research", "map", "identify", "assess", "analyze", "compare", "survey",
    "evaluate", "explore", "outline", "review", "examine", "quantify",
)

# Verbs and generic nouns that look capitalized but are not named entities
_ENTITY_STOPWORDS = frozenset({
    "research", "researching", "map", "mapping", "analyze", "assess",
    "evaluate", "study", "review", "identify", "compare", "explore",
    "industry", "market", "demand", "segments", "overview", "structure",
    "调研", "梳理", "评估", "研究", "分析", "对比", "探索", "综合", "市场", "行业",
})

REASON_TEXT_ZH = {
    "too_short": "指令过短，不足以直接检索",
    "english_skeleton": "照抄了英文骨架标题或 checklist 的英文 goal",
    "wrong_language": "语言与选题不一致（中文选题必须写中文指令）",
    "no_verb": "没有以动词开头（调研/梳理/评估/研究/分析/对比/探索…）",
    "no_entity": "没有点名任何具名实体（平台/监管/公司/品类/指标）",
    "few_entities": "具名实体少于 2 个，指令还不够具体",
    "goal_equals_detail": "research_goal 与 direction_detail 措辞重复",
    "weak_queries": "queries 缺失或写成「选题 + 英文标题」",
    "no_must_answer": "缺少 must_answer 具体问题",
}

_HARD_REASONS = frozenset({
    "too_short", "english_skeleton", "wrong_language", "no_verb", "no_entity",
})


@dataclass
class RubricResult:
    """Outcome of judging one direction; ``reasons`` feeds the rewrite prompt."""
    ok: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def hard_failures(self) -> list[str]:
        return [r for r in self.reasons if r in _HARD_REASONS]

    def explain_zh(self) -> str:
        return "；".join(REASON_TEXT_ZH.get(r, r) for r in self.reasons)


def topic_is_zh(topic: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", topic or ""))


def contains_skeleton_phrase(text: str, extra: set[str] | None = None) -> bool:
    """True if text embeds a known English framework skeleton label or goal."""
    low = re.sub(r"\s+", " ", (text or "").strip().lower())
    if not low:
        return False
    banned = set(ENGLISH_SKELETON_TITLES)
    if extra:
        banned |= {x.strip().lower() for x in extra if x and len(x.strip()) >= 8}
    return any(s in low for s in banned)


def is_skeleton_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if t in ENGLISH_SKELETON_TITLES:
        return True
    return contains_skeleton_phrase(t)


def harvest_entities(text: str, *, max_n: int = 8) -> list[str]:
    """Named entities in instruction text: capitalized Latin + CJK n-grams."""
    found: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9&.-]{1,40})\b", text or ""):
        w = m.group(1)
        key = w.lower()
        if key in seen or key in _ENTITY_STOPWORDS or len(w) < 2:
            continue
        seen.add(key)
        found.append(w)
        if len(found) >= max_n:
            return found
    for tok in text_tokens(text or "", max_tokens=20):
        if not re.search(r"[\u4e00-\u9fff]", tok):
            continue
        if len(tok) < 2 or tok in seen or tok in _ENTITY_STOPWORDS:
            continue
        seen.add(tok)
        found.append(tok)
        if len(found) >= max_n:
            break
    return found


def _entity_count(text: str, topic: str) -> int:
    """Entities that add information beyond the topic string itself."""
    topic_low = (topic or "").lower()
    count = 0
    for ent in harvest_entities(text, max_n=12):
        if len(ent) < 2:
            continue
        if ent.lower() in topic_low or ent in topic_low:
            continue
        count += 1
    return count


def check_instruction(
    text: str,
    topic: str,
    *,
    forbidden: set[str] | None = None,
) -> RubricResult:
    """Judge one direction_detail: verb-led, concrete, right language."""
    t = (text or "").strip()
    reasons: list[str] = []
    if len(t) < 16:
        return RubricResult(ok=False, reasons=["too_short"])
    if contains_skeleton_phrase(t, forbidden):
        reasons.append("english_skeleton")
    zh_topic = topic_is_zh(topic)
    if zh_topic:
        if not re.search(r"[\u4e00-\u9fff]", t):
            reasons.append("wrong_language")
        elif not any(t.startswith(v) for v in INSTRUCTION_VERBS_ZH):
            reasons.append("no_verb")
        if re.match(
            r"^(who|what|how|why|where|which|order-of-magnitude|market size)\b", t, re.I
        ):
            reasons.append("english_skeleton")
    else:
        low = t.lower()
        if not any(low.startswith(v) for v in INSTRUCTION_VERBS_EN):
            reasons.append("no_verb")

    entities = _entity_count(t, topic)
    if entities == 0:
        reasons.append("no_entity")
    elif entities < 2:
        reasons.append("few_entities")

    # Dedup while preserving order
    ordered: list[str] = []
    for r in reasons:
        if r not in ordered:
            ordered.append(r)
    hard = [r for r in ordered if r in _HARD_REASONS]
    return RubricResult(ok=not hard, reasons=ordered)


def weak_query(q: str, topic: str, title: str) -> bool:
    qn = re.sub(r"\s+", " ", (q or "").strip().lower())
    if not qn or len(qn) < 8:
        return True
    if contains_skeleton_phrase(qn):
        return True
    combo = re.sub(r"\s+", " ", f"{topic} {title}".strip().lower())
    if qn == combo or (title and qn.endswith(title.strip().lower())):
        return True
    if is_skeleton_title(title) and title.lower() in qn:
        return True
    return False


def check_direction(
    item: dict,
    topic: str,
    *,
    forbidden: set[str] | None = None,
) -> RubricResult:
    """Judge a raw LLM direction payload (detail + title + goal + queries)."""
    detail = str(item.get("direction_detail") or item.get("research_goal") or "").strip()
    title = str(item.get("title") or "").strip()
    goal = str(item.get("research_goal") or "").strip()
    result = check_instruction(detail, topic, forbidden=forbidden)
    reasons = list(result.reasons)

    if title and (is_skeleton_title(title) or contains_skeleton_phrase(title, forbidden)):
        if "english_skeleton" not in reasons:
            reasons.append("english_skeleton")
    if goal and detail and goal.strip() == detail.strip():
        reasons.append("goal_equals_detail")

    queries = [str(q).strip() for q in (item.get("queries") or []) if str(q).strip()]
    if not queries or all(weak_query(q, topic, title) for q in queries):
        reasons.append("weak_queries")
    if not [a for a in (item.get("must_answer") or []) if str(a).strip()]:
        reasons.append("no_must_answer")

    hard = [r for r in reasons if r in _HARD_REASONS]
    return RubricResult(ok=not hard, reasons=reasons)
