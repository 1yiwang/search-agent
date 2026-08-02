"""Wave 12a: ResearchBrief frameworks, deprioritize, Unicom/CH anti-GDP."""

from brief import (
    brief_seed_queries,
    filter_queries_by_deprioritize,
    _parse_brief_payload,
)
from frameworks import load_all_frameworks, select_framework_id
from models import BriefDimension, ResearchBrief


def test_select_framework_market_entry_unicom():
    assert select_framework_id(
        "中国联通进入瑞士电信市场的机会与障碍"
    ) == "market_entry"
    assert select_framework_id(
        "China Unicom Switzerland telecom market entry"
    ) == "market_entry"


def test_select_framework_investor():
    topic = "European corporate direct lending fundraising and deployment trends"
    assert select_framework_id(topic) == "investor_brief"


def test_frameworks_loaded():
    fws = load_all_frameworks()
    assert "market_entry" in fws
    assert "general_industry" in fws
    assert "competitive_landscape" in fws
    assert "investor_brief" in fws
    phases = fws["market_entry"]["phases"]
    assert any("industry" in str(p.get("title", "")).lower() or p.get("id") == "industry_structure" for p in phases)
    deps = " ".join(fws["market_entry"].get("default_deprioritize") or []).lower()
    assert "gdp" in deps or "macro" in deps


def test_deprioritize_filters_gdp_queries():
    deps = [
        "country GDP and general macroeconomy unless explicitly requested",
    ]
    queries = [
        "Switzerland telecom market share Swisscom Sunrise Salt",
        "Switzerland GDP growth 2024 2025",
        "BAKOM OFCOM Switzerland telecom regulation",
        "Swiss macroeconomic outlook GDP",
    ]
    kept = filter_queries_by_deprioritize(queries, deps)
    assert "Switzerland telecom market share Swisscom Sunrise Salt" in kept
    assert "BAKOM OFCOM Switzerland telecom regulation" in kept
    assert all("gdp" not in q.lower() for q in kept)


def test_brief_seed_queries_prefer_telecom_not_gdp():
    brief = ResearchBrief(
        topic="China Unicom Switzerland market entry",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title="Industry structure",
                research_goal="Swiss mobile market shares",
                queries=[
                    "Switzerland mobile market share Swisscom Sunrise Salt",
                    "Switzerland GDP overview",
                ],
                phase_id="industry_structure",
            ),
            BriefDimension(
                title="Regulation",
                research_goal="Telecom licenses BAKOM",
                queries=["Switzerland telecom license BAKOM foreign operator"],
                phase_id="regulation",
            ),
        ],
        deprioritize=["country GDP and general macroeconomy"],
    )
    seeds = brief_seed_queries(brief)
    assert seeds
    assert all("gdp" not in q.lower() for q in seeds)
    blob = " ".join(seeds).lower()
    assert "telecom" in blob or "swisscom" in blob or "bakom" in blob


def test_parse_brief_payload_merges_framework_deprioritize():
    raw = {
        "problem_restatement": "Unicom CH telecom opportunity",
        "dimensions": [
            {
                "title": "Industry structure",
                "research_goal": "Market shares",
                "queries": ["Swiss telecom market share"],
                "phase_id": "industry_structure",
            }
        ],
        "deprioritize": [],
        "overview_markdown": "Test",
    }
    brief = _parse_brief_payload(
        raw,
        topic="China Unicom Switzerland",
        framework_id="market_entry",
        answers={"q1": "Industry only"},
    )
    assert brief.framework_id == "market_entry"
    assert any("gdp" in d.lower() or "macro" in d.lower() for d in brief.deprioritize)
    assert brief.dimensions[0].phase_id == "industry_structure"
    assert brief.dimensions[0].direction_id == "industry_structure"
    assert brief.dimensions[0].direction_detail
