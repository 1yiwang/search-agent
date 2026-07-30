"""Deterministic multilingual query pivoting (Wave 9b).

Chinese (or other) topics must not collapse search to same-language web only.
For Switzerland / DACH markets, fan out EN + DE + FR (+ IT) open queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Brand / entity aliases (zh → English canonical)
BRAND_ALIASES: list[tuple[str, str]] = [
    ("中国联通", "China Unicom"),
    ("联通", "China Unicom"),
    ("中国移动", "China Mobile"),
    ("中国电信", "China Telecom"),
    ("瑞士电信", "Swisscom"),
    ("瑞讯", "Swisscom"),
]

# Common research terms (zh → en) — longest match first via sorted length
TERM_ALIASES: list[tuple[str, str]] = sorted(
    [
        ("市场份额", "market share"),
        ("市场进入", "market entry"),
        ("市场开拓", "market expansion"),
        ("开拓", "market entry"),
        ("可能性", "opportunity"),
        ("营收", "revenue"),
        ("收入", "revenue"),
        ("利润", "profit"),
        ("竞争", "competition"),
        ("竞争对手", "competitors"),
        ("监管", "regulation"),
        ("牌照", "license"),
        ("虚拟运营商", "MVNO"),
        ("运营商", "telecom operator"),
        ("电信", "telecom"),
        ("宽带", "broadband"),
        ("企业客户", "enterprise customers"),
        ("政企", "enterprise B2B"),
        ("华人", "Chinese diaspora"),
        ("华侨", "Chinese diaspora"),
        ("瑞士", "Switzerland"),
        ("苏黎世", "Zurich"),
        ("日内瓦", "Geneva"),
        ("欧洲", "Europe"),
        ("德国", "Germany"),
        ("法国", "France"),
        ("意大利", "Italy"),
        ("奥地利", "Austria"),
        ("市场", "market"),
        ("调研", "research"),
        ("报告", "report"),
        ("机会", "opportunity"),
        ("风险", "risk"),
        ("规模", "market size"),
        ("增长", "growth"),
        ("销售", "sales"),
        ("业务", "business"),
        ("战略", "strategy"),
    ],
    key=lambda x: len(x[0]),
    reverse=True,
)

GEO_MARKERS: dict[str, tuple[str, ...]] = {
    "switzerland": (
        "switzerland", "swiss", "schweiz", "suisse", "svizzera", "helvetia",
        "zurich", "zürich", "geneva", "genève", "basel", "bern", "lausanne",
        "bakom", "ofcom", "swisscom", "sunrise", "salt",
        "瑞士", "苏黎世", "日内瓦", "巴塞尔", "伯尔尼",
    ),
    "dach": (
        "germany", "deutschland", "austria", "österreich", "osterreich",
        "dach", "berlin", "munich", "wien", "vienna",
        "德国", "奥地利", "慕尼黑", "柏林", "维也纳",
    ),
    "europe": (
        "europe", "european", "eu ", " eu", "eurozone",
        "欧洲", "欧盟",
    ),
}

# Locale labels appended to pivoted English cores
LOCALE_SUFFIXES: dict[str, tuple[str, ...]] = {
    "switzerland": (
        "Switzerland English",
        "Schweiz Deutsch Markt",
        "Suisse marché français",
        "Svizzera mercato",
    ),
    "dach": (
        "Germany Austria Switzerland",
        "DACH Markt Deutsch",
        "marché Europe francophone",
    ),
    "europe": (
        "Europe English",
        "European market",
        "Europe Deutsch",
    ),
    "general": (
        "English sources",
        "international market",
    ),
}


@dataclass(frozen=True)
class MultilangPlan:
    script: str  # zh | latin | mixed
    geo: str  # switzerland | dach | europe | general
    english_pivot: str
    open_seeds: tuple[str, ...]


def detect_script(topic: str) -> str:
    has_zh = bool(re.search(r"[\u4e00-\u9fff]", topic))
    has_latin = bool(re.search(r"[A-Za-z]{2,}", topic))
    if has_zh and has_latin:
        return "mixed"
    if has_zh:
        return "zh"
    return "latin"


def detect_market_geo(topic: str) -> str:
    t = topic.lower()
    for geo, markers in GEO_MARKERS.items():
        if any(m.lower() in t for m in markers):
            return geo
    return "general"


def pivot_topic_to_english(topic: str) -> str:
    """Deterministic zh→en pivot via brand/term maps; keep Latin tokens."""
    text = topic.strip()
    for zh, en in BRAND_ALIASES:
        text = text.replace(zh, f" {en} ")

    # Replace known terms
    remaining = text
    english_parts: list[str] = []
    # Greedy left-to-right longest-term replacement
    i = 0
    buf_latin: list[str] = []
    while i < len(remaining):
        ch = remaining[i]
        if "A" <= ch <= "Z" or "a" <= ch <= "z" or ch.isdigit():
            # consume latin token
            j = i + 1
            while j < len(remaining) and (
                remaining[j].isalnum() or remaining[j] in "-_/."
            ):
                j += 1
            buf_latin.append(remaining[i:j])
            i = j
            continue
        if "\u4e00" <= ch <= "\u9fff":
            if buf_latin:
                english_parts.extend(buf_latin)
                buf_latin = []
            matched = False
            for zh, en in TERM_ALIASES:
                if remaining.startswith(zh, i):
                    english_parts.append(en)
                    i += len(zh)
                    matched = True
                    break
            if not matched:
                i += 1  # skip unmapped CJK char
            continue
        # punctuation / space
        if buf_latin:
            english_parts.extend(buf_latin)
            buf_latin = []
        i += 1
    if buf_latin:
        english_parts.extend(buf_latin)

    # Dedup consecutive / case-insensitive
    seen: set[str] = set()
    out: list[str] = []
    for part in english_parts:
        key = part.lower()
        if key in seen or not part.strip():
            continue
        seen.add(key)
        out.append(part.strip())
    pivoted = " ".join(out).strip()
    return pivoted or topic


def build_multilang_plan(topic: str, *, hop: int = 0) -> MultilangPlan:
    script = detect_script(topic)
    geo = detect_market_geo(topic)
    pivot = pivot_topic_to_english(topic) if script in ("zh", "mixed") else topic.strip()
    if script == "latin" and geo != "general":
        pivot = topic.strip()

    suffixes = LOCALE_SUFFIXES.get(geo, LOCALE_SUFFIXES["general"])
    # Rotate starting suffix by hop so multi-hop diversifies languages
    rotated = suffixes[hop % len(suffixes) :] + suffixes[: hop % len(suffixes)]

    seeds: list[str] = []
    # Always keep original topic as one seed (user intent)
    seeds.append(topic.strip())

    if script in ("zh", "mixed") and pivot and pivot.lower() != topic.strip().lower():
        seeds.append(pivot)

    for suf in rotated:
        core = pivot if pivot else topic.strip()
        # Avoid dumping long Chinese into DE/FR queries
        if script == "zh" and re.search(r"[\u4e00-\u9fff]", core):
            core = pivot or "market research"
        q = f"{core} {suf}".strip()
        if q not in seeds:
            seeds.append(q)

    # Switzerland-specific regulator / operator angles (English)
    if geo == "switzerland":
        for extra in (
            f"{pivot} Swisscom Sunrise Salt MVNO BAKOM",
            f"{pivot} Switzerland telecom market share revenue",
            f"{pivot} Schweiz Telekommunikationsmarkt Wettbewerb",
        ):
            if extra not in seeds and pivot:
                seeds.append(extra)

    # Cap seeds; prefer non-Chinese when topic is Chinese (≥ half non-zh)
    if script in ("zh", "mixed"):
        non_zh = [s for s in seeds if not re.search(r"[\u4e00-\u9fff]", s)]
        zh_only = [s for s in seeds if re.search(r"[\u4e00-\u9fff]", s)]
        # Keep at most 2 Chinese seeds; fill rest with non-zh
        ordered = zh_only[:2] + non_zh
        seeds = ordered

    # Dedup preserve order
    deduped: list[str] = []
    seen_q: set[str] = set()
    for s in seeds:
        key = s.lower()
        if key in seen_q:
            continue
        seen_q.add(key)
        deduped.append(s)

    return MultilangPlan(
        script=script,
        geo=geo,
        english_pivot=pivot,
        open_seeds=tuple(deduped[:8]),
    )


def initial_open_queries(topic: str, *, hop: int = 0) -> list[str]:
    """Open-web queries for hop-0 / force-open when no pending expand yet."""
    return list(build_multilang_plan(topic, hop=hop).open_seeds)
