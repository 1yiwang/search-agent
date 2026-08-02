"""Research-plan direction quality (Gemini-style instructions)."""

from brief import (
    _parse_brief_payload,
    _is_skeleton_title,
    _is_good_instruction,
    _instruction_from_phase,
)


def test_skeleton_titles_detected():
    assert _is_skeleton_title("Demand segments and use cases")
    assert _is_skeleton_title("Industry structure and competitive landscape")
    assert not _is_skeleton_title("运营商格局")
    assert not _is_good_instruction(
        "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
        "中国联通进入瑞士电信市场的机会",
    )


def test_parse_rebuilds_skeleton_dump():
    raw = {
        "problem_restatement": "中国联通进入瑞士电信市场的机会",
        "dimensions": [
            {
                "title": "Demand segments and use cases",
                "research_goal": "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
                "direction_detail": "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
                "queries": ["中国联通进入瑞士电信市场的机会 Demand segments and use cases"],
                "phase_id": "demand_segments",
            },
            {
                "title": "Industry structure and competitive landscape",
                "research_goal": "Market size",
                "direction_detail": "Market size, growth, player map",
                "queries": ["中国联通进入瑞士电信市场的机会 Industry structure and competitive landscape"],
                "phase_id": "industry_structure",
            },
        ],
        "deprioritize": [],
    }
    brief = _parse_brief_payload(
        raw,
        topic="中国联通进入瑞士电信市场的机会",
        framework_id="market_entry",
        answers={},
    )
    assert len(brief.dimensions) >= 4
    for d in brief.dimensions:
        assert not _is_skeleton_title(d.title)
        assert "Demand segments" not in d.direction_detail
        assert "Industry structure and competitive" not in d.direction_detail
        assert _is_good_instruction(d.direction_detail, brief.topic)
        blob = " ".join(d.queries)
        assert "Demand segments and use cases" not in blob
        assert "Industry structure and competitive landscape" not in blob
        assert d.direction_detail.startswith(("调研", "梳理", "评估", "研究", "分析", "对比"))
    assert "(1)" in brief.overview_markdown
    assert "Who buys what" not in brief.overview_markdown


def test_instruction_template_mentions_topic():
    text = _instruction_from_phase(
        "中国联通进入瑞士电信市场的机会",
        {"id": "regulation", "goal": "licenses"},
    )
    assert "BAKOM" in text or "瑞士" in text
    assert text.startswith("研究")


def test_ecommerce_style_plan_when_skeleton():
    raw = {
        "dimensions": [
            {
                "title": "Demand segments and use cases",
                "direction_detail": "Demand segments and use cases",
                "queries": ["中国商品卖到瑞士的跨境电商机会 Demand segments and use cases"],
                "phase_id": "demand_segments",
            },
            {
                "title": "Industry structure and competitive landscape",
                "direction_detail": "Industry structure and competitive landscape",
                "queries": ["x Industry structure and competitive landscape"],
                "phase_id": "industry_structure",
            },
        ],
    }
    brief = _parse_brief_payload(
        raw,
        topic="中国商品卖到瑞士的跨境电商机会",
        framework_id="market_entry",
        answers={},
    )
    blob = "\n".join(d.direction_detail for d in brief.dimensions)
    assert "Galaxus" in blob or "高潜力品类" in blob or "跨境电商市场规模" in blob
    assert "Demand segments" not in blob


if __name__ == "__main__":
    test_skeleton_titles_detected()
    test_parse_rebuilds_skeleton_dump()
    test_instruction_template_mentions_topic()
    test_ecommerce_style_plan_when_skeleton()
    print("direction quality tests: PASS")
