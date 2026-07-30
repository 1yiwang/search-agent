"""Swiss / telecom market intent detection (Wave 11)."""

from __future__ import annotations

import re

from multilang import detect_market_geo

_TELECOM_MARKERS: tuple[str, ...] = (
    "telecom", "telecommunications", "telco", "mvno", "mobile network",
    "broadband", "5g", "4g", "fiber", "fibre", "operator", "carriers",
    "swisscom", "sunrise", "salt mobile", " bakom", "ofcom", "comcom",
    "china unicom", "china mobile", "china telecom",
    "电信", "联通", "运营商", "虚拟运营商", "宽带", "移动网络", "牌照",
    "通讯", "通信", "手机套餐", "政企专线",
)

_SWISS_GEO_MARKERS: tuple[str, ...] = (
    "switzerland", "swiss", "schweiz", "suisse", "svizzera",
    "zurich", "geneva", "basel", "bern",
    "瑞士", "苏黎世", "日内瓦",
)


def telecom_intent_score(topic: str) -> int:
    """Higher = stronger Swiss/telecom research intent."""
    t = topic.lower()
    score = 0
    if any(m.lower() in t if m.isascii() else m in topic for m in _TELECOM_MARKERS):
        score += 3
    geo = detect_market_geo(topic)
    if geo == "switzerland" or any(m in t for m in _SWISS_GEO_MARKERS) or "瑞士" in topic:
        score += 2
    if "unicom" in t or "联通" in topic:
        score += 1
    return score


def has_swiss_telecom_intent(topic: str, min_score: int = 4) -> bool:
    """True when topic is about telecom AND Switzerland (or Unicom+CH)."""
    return telecom_intent_score(topic) >= min_score
