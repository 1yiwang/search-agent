"""Wave 12c: evidence draft + outline selection."""

from models import ExtractedFact, ResearchBrief, BriefDimension
from report_outlines import resolve_slots, select_outline_id
from report_synthesis import _heuristic_draft, fallback_synthesis


def test_outline_market_entry_for_unicom():
    assert select_outline_id("中国联通进入瑞士电信市场机会") == "market_entry"
    oid, slots, hint = resolve_slots("中国联通瑞士市场")
    assert oid == "market_entry"
    assert any(s["id"] == "industry_structure" for s in slots)
    assert "gdp" in hint.lower() or "macro" in hint.lower()


def test_brief_dimensions_drive_slots():
    brief = ResearchBrief(
        topic="China Unicom Switzerland",
        framework_id="market_entry",
        problem_restatement="联通进入瑞士电信业的机会与障碍",
        dimensions=[
            BriefDimension(title="竞争格局", research_goal="Swisscom Sunrise Salt", phase_id="industry_structure"),
            BriefDimension(title="监管", research_goal="BAKOM", phase_id="regulation"),
        ],
        deprioritize=["GDP macro"],
    )
    oid, slots, _ = resolve_slots(brief.topic, brief)
    assert oid == "market_entry"
    assert [s["id"] for s in slots] == ["industry_structure", "regulation"]


def test_heuristic_quarantines_gdp():
    facts = [
        ExtractedFact(
            fact="Swisscom holds about 60% mobile share.",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="market share",
            confidence="high",
        ),
        ExtractedFact(
            fact="Switzerland GDP grew 1.2% in 2024.",
            source_url="https://a.com/2",
            source_title="B",
            quoted_text="GDP growth",
            confidence="medium",
        ),
    ]
    oid, slots, dep = resolve_slots("中国联通进入瑞士电信市场")
    draft = _heuristic_draft(
        "中国联通进入瑞士电信市场",
        facts,
        slots,
        oid,
        dep,
        "联通进入瑞士电信市场的机会",
    )
    q_idx = {q.fact_index for q in draft.quarantine}
    assert 2 in q_idx
    assert 1 not in q_idx
    filled = [s for s in draft.slots if s.fact_indices]
    assert filled
    assert all(2 not in s.fact_indices for s in draft.slots)


def test_fallback_synthesis_has_headed_arguments():
    facts = [
        ExtractedFact(
            fact="BAKOM regulates Swiss telecom licenses.",
            source_url="https://bakom.ch",
            source_title="BAKOM",
            quoted_text="regulator",
            confidence="high",
        ),
    ]
    syn = fallback_synthesis("中国联通瑞士电信机会", facts, ["q1"])
    assert syn.thesis
    assert syn.arguments
    assert any(a.heading for a in syn.arguments)


if __name__ == "__main__":
    test_outline_market_entry_for_unicom()
    test_brief_dimensions_drive_slots()
    test_heuristic_quarantines_gdp()
    test_fallback_synthesis_has_headed_arguments()
    print("All Wave 12c draft tests passed!")
