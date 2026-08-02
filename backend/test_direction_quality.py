# -*- coding: utf-8 -*-
"""Research-plan direction quality (Gemini-style instructions)."""

from brief import (
    _INSTRUCTION_VERBS_ZH,
    _instruction_from_phase,
    _is_good_instruction,
    _is_skeleton_title,
    _parse_brief_payload,
)


def test_skeleton_titles_detected():
    assert _is_skeleton_title("Demand segments and use cases")
    assert _is_skeleton_title("Industry structure and competitive landscape")
    assert not _is_skeleton_title("x")
    assert not _is_good_instruction(
        "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
        "中国联通进入瑞士电信市场的机会",
    )


def test_parse_rebuilds_skeleton_dump():
    topic = "中国联通进入瑞士电信市场的机会"
    raw = {
        "problem_restatement": topic,
        "dimensions": [
            {
                "title": "Demand segments and use cases",
                "research_goal": "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
                "direction_detail": "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.",
                "queries": [f"{topic} Demand segments and use cases"],
                "phase_id": "demand_segments",
            },
            {
                "title": "Industry structure and competitive landscape",
                "research_goal": "Market size",
                "direction_detail": "Market size, growth, player map",
                "queries": [f"{topic} Industry structure and competitive landscape"],
                "phase_id": "industry_structure",
            },
        ],
        "deprioritize": [],
    }
    brief = _parse_brief_payload(
        raw,
        topic=topic,
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
        assert any(d.direction_detail.startswith(v) for v in _INSTRUCTION_VERBS_ZH)
    assert "(1)" in brief.overview_markdown
    assert "Who buys what" not in brief.overview_markdown


def test_instruction_template_mentions_topic():
    text = _instruction_from_phase(
        "中国联通进入瑞士电信市场的机会",
        {"id": "regulation", "goal": "licenses"},
    )
    assert "BAKOM" in text or "\u745e\u58eb" in text  # 瑞士
    assert any(text.startswith(v) for v in _INSTRUCTION_VERBS_ZH)


def test_ecommerce_style_plan_when_skeleton():
    topic = "中国商品卖到瑞士的跨境电商机会"
    raw = {
        "dimensions": [
            {
                "title": "Demand segments and use cases",
                "direction_detail": "Demand segments and use cases",
                "queries": [f"{topic} Demand segments and use cases"],
                "phase_id": "demand_segments",
            },
            {
                "title": "Industry structure and competitive landscape",
                "direction_detail": "Industry structure and competitive landscape",
                "queries": ["x Industry structure and competitive landscape"],
                "phase_id": "industry_structure",
            },
            {
                "title": "Rough opportunity sizing",
                "research_goal": (
                    "Order-of-magnitude revenue/TAM only if data exists — label uncertainty"
                ),
                "direction_detail": (
                    "Order-of-magnitude revenue/TAM only if data exists — label uncertainty"
                ),
                "queries": [f"{topic} Rough opportunity sizing"],
                "phase_id": "sizing",
            },
        ],
    }
    brief = _parse_brief_payload(
        raw,
        topic=topic,
        framework_id="market_entry",
        answers={},
    )
    blob = "\n".join(d.direction_detail for d in brief.dimensions)
    assert (
        "Galaxus" in blob
        or "\u9ad8\u6f5c\u529b\u54c1\u7c7b" in blob  # 高潜力品类
        or "\u8de8\u5883\u7535\u5546\u5e02\u573a\u89c4\u6a21" in blob  # 跨境电商市场规模
    )
    assert "Demand segments" not in blob
    assert "Order-of-magnitude" not in blob
    assert "Rough opportunity" not in blob
    for d in brief.dimensions:
        assert "Rough opportunity sizing" not in " ".join(d.queries)
        assert any(d.direction_detail.startswith(v) for v in _INSTRUCTION_VERBS_ZH)
        assert _is_good_instruction(d.direction_detail, brief.topic)


def test_framework_block_has_no_english_goals():
    from frameworks import clear_frameworks_cache, framework_prompt_block

    clear_frameworks_cache()
    block = framework_prompt_block("market_entry")
    assert "Order-of-magnitude" not in block
    assert "Demand segments and use cases" not in block
    assert "angle_id=demand_segments" in block
    assert "\u9700\u6c42\u7ec6\u5206" in block  # 需求细分


def test_brief_model_upgrades_weak_byok():
    from unittest.mock import patch

    from brief import get_brief_model
    from llm_context import RequestKeys, set_request_keys

    set_request_keys(
        RequestKeys(
            llm_api_key="sk-test",
            llm_base_url="https://api.deepseek.com",
            llm_model="deepseek-chat",
        )
    )
    try:
        with patch("brief.config") as cfg:
            cfg.llm_brief_model = ""
            cfg.llm_model = "deepseek-v4-pro"
            assert get_brief_model() == "deepseek-v4-pro"
    finally:
        set_request_keys(None)


if __name__ == "__main__":
    test_skeleton_titles_detected()
    test_parse_rebuilds_skeleton_dump()
    test_instruction_template_mentions_topic()
    test_ecommerce_style_plan_when_skeleton()
    test_framework_block_has_no_english_goals()
    test_brief_model_upgrades_weak_byok()
    print("direction quality tests: PASS")
