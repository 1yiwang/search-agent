# -*- coding: utf-8 -*-
"""Wave 12h Step 87: rubric + YAML examples + targeted regenerate."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from brief import _parse_brief_payload, _rewrite_failed_directions
from brief_rubric import check_direction, check_instruction
from frameworks import example_instruction, few_shot_block, load_all_examples

_ZH_TOPIC = "中国联通进入瑞士电信市场的机会"


def test_rubric_reports_reasons_not_just_bool():
    bad = check_instruction(
        "Who buys what — B2B, consumer, diaspora, wholesale, MVNO, etc.", _ZH_TOPIC
    )
    assert not bad.ok
    assert "wrong_language" in bad.reasons or "english_skeleton" in bad.reasons
    assert bad.explain_zh()

    good = check_instruction(
        "调研瑞士电信市场规模与竞争格局，梳理 Swisscom、Sunrise、Salt 的市占与 ARPU。",
        _ZH_TOPIC,
    )
    assert good.ok, good.reasons
    assert "no_entity" not in good.reasons
    print("test_rubric_reports_reasons_not_just_bool: PASS")


def test_rubric_flags_soft_issues_without_failing():
    result = check_direction(
        {
            "title": "竞争格局",
            "direction_detail": "调研瑞士电信市场中 Swisscom 与 Sunrise 的市占与资费结构。",
            "research_goal": "调研瑞士电信市场中 Swisscom 与 Sunrise 的市占与资费结构。",
            "queries": ["Swisscom Sunrise market share 2026"],
        },
        _ZH_TOPIC,
    )
    assert result.ok
    assert "goal_equals_detail" in result.reasons
    assert "no_must_answer" in result.reasons
    print("test_rubric_flags_soft_issues_without_failing: PASS")


def test_examples_yaml_replaces_hardcoded_templates():
    examples = load_all_examples()
    assert "swiss_telecom_zh" in examples
    assert "swiss_ecommerce_zh" in examples

    telecom = example_instruction(_ZH_TOPIC, "industry_structure")
    assert telecom and "Swisscom" in telecom

    ecom = example_instruction("中国商品卖到瑞士的跨境电商机会", "opportunities")
    assert ecom and "Galaxus" in ecom

    # Unrelated topic must not borrow Swiss wording
    assert example_instruction("日本便利店供应链数字化", "industry_structure") is None

    source = Path("brief.py").read_text(encoding="utf-8")
    for marker in ("Swisscom", "Galaxus", "TWINT", "BAKOM"):
        assert marker not in source, f"{marker} should live in YAML, not brief.py"
    print("test_examples_yaml_replaces_hardcoded_templates: PASS")


def test_few_shot_block_matches_topic_domain():
    telecom_block = few_shot_block(_ZH_TOPIC)
    assert "Swisscom" in telecom_block
    fallback_block = few_shot_block("日本便利店供应链数字化")
    assert fallback_block  # gold standard still provides a style example
    print("test_few_shot_block_matches_topic_domain: PASS")


async def _test_targeted_rewrite_replaces_only_failures():
    raw = {
        "dimensions": [
            {
                "title": "竞争格局",
                "direction_detail": (
                    "调研瑞士电信市场规模与竞争格局，梳理 Swisscom、Sunrise、Salt 的市占与 ARPU。"
                ),
                "research_goal": "得到三大运营商的份额对比表",
                "entities": ["Swisscom", "Sunrise"],
                "must_answer": ["三家份额各是多少？"],
                "queries": ["Swisscom Sunrise Salt market share 2026"],
                "phase_id": "industry_structure",
                "priority": 1,
            },
            {
                "title": "Demand segments and use cases",
                "direction_detail": "Who buys what — B2B, consumer, diaspora, wholesale.",
                "research_goal": "Who buys what",
                "queries": ["中国联通进入瑞士电信市场的机会 Demand segments and use cases"],
                "phase_id": "demand_segments",
                "priority": 2,
            },
        ]
    }

    rewritten = {
        "dimensions": [
            {
                "title": "需求细分",
                "direction_detail": (
                    "梳理瑞士电信需求细分：消费移动、B2B 政企、华人漫游与 MVNO 批发，"
                    "判断哪些细分对中国联通最有价值。"
                ),
                "research_goal": "得到细分优先级排序与理由",
                "entities": ["MVNO", "B2B"],
                "must_answer": ["哪个细分门槛最低？"],
                "queries": ["Switzerland MVNO wholesale segment demand"],
                "phase_id": "demand_segments",
                "priority": 2,
            }
        ]
    }

    response = MagicMock()
    response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(rewritten, ensure_ascii=False)))
    ]
    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with patch("brief.get_openai_client", return_value=client):
        out = await _rewrite_failed_directions(
            raw, topic=_ZH_TOPIC, framework_id="market_entry", model="test-model"
        )

    assert client.chat.completions.create.await_count == 1
    first, second = out["dimensions"]
    assert "Swisscom" in first["direction_detail"], "passing direction must be untouched"
    assert second["direction_detail"].startswith("梳理")
    assert second["phase_id"] == "demand_segments"
    print("test_targeted_rewrite_replaces_only_failures: PASS")


def test_fallback_directions_are_reported():
    raw = {
        "problem_restatement": _ZH_TOPIC,
        "dimensions": [
            {
                "title": "Demand segments and use cases",
                "research_goal": "Who buys what",
                "direction_detail": "Who buys what — B2B, consumer, diaspora, wholesale.",
                "queries": [f"{_ZH_TOPIC} Demand segments and use cases"],
                "phase_id": "demand_segments",
            }
        ],
        "deprioritize": [],
    }
    brief = _parse_brief_payload(
        raw, topic=_ZH_TOPIC, framework_id="market_entry", answers={}
    )
    assert brief.fallback_direction_ids, "template rewrite must be reported"
    known = {d.direction_id or d.phase_id or d.title for d in brief.dimensions}
    assert set(brief.fallback_direction_ids) <= known
    print("test_fallback_directions_are_reported: PASS")


if __name__ == "__main__":
    test_rubric_reports_reasons_not_just_bool()
    test_rubric_flags_soft_issues_without_failing()
    test_examples_yaml_replaces_hardcoded_templates()
    test_few_shot_block_matches_topic_domain()
    test_fallback_directions_are_reported()
    asyncio.run(_test_targeted_rewrite_replaces_only_failures())
    print("ALL PASS")
