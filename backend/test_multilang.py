"""Unit tests for multilingual query pivoting (Wave 9b)."""

from multilang import (
    build_multilang_plan,
    detect_market_geo,
    detect_script,
    initial_open_queries,
    pivot_topic_to_english,
)
from coverage import GapHint
from query_expand import expand_queries
from datetime import date


def test_detect_switzerland_geo_from_chinese():
    assert detect_script("中国联通在瑞士市场开拓") == "zh"
    assert detect_market_geo("中国联通在瑞士市场开拓") == "switzerland"
    print("test_detect_switzerland_geo_from_chinese: PASS")


def test_pivot_china_unicom_switzerland():
    pivot = pivot_topic_to_english("中国联通在瑞士市场开拓的可能性与市场份额")
    lower = pivot.lower()
    assert "china unicom" in lower
    assert "switzerland" in lower
    assert "market" in lower
    print("test_pivot_china_unicom_switzerland: PASS")


def test_multilang_seeds_majority_non_chinese():
    plan = build_multilang_plan("中国联通在瑞士市场开拓的可能性", hop=0)
    seeds = plan.open_seeds
    assert len(seeds) >= 3
    non_zh = [s for s in seeds if not any("\u4e00" <= c <= "\u9fff" for c in s)]
    assert len(non_zh) >= len(seeds) // 2
    joined = " ".join(seeds).lower()
    assert "switzerland" in joined or "schweiz" in joined or "suisse" in joined
    print("test_multilang_seeds_majority_non_chinese: PASS")


def test_initial_open_queries_used_for_general():
    qs = initial_open_queries("中国联通瑞士电信市场竞争", hop=0)
    assert qs[0].startswith("中国") or "联通" in qs[0] or "China" in qs[0]
    assert any("Swisscom" in q or "swisscom" in q.lower() or "Schweiz" in q for q in qs)
    print("test_initial_open_queries_used_for_general: PASS")


def test_expand_includes_multilang_seeds():
    hints = [GapHint(dimension="_empty", research_goal="Primary sources")]
    result = expand_queries(
        "中国联通在瑞士市场开拓机会",
        hints,
        candidates=[],
        current_date=date(2026, 7, 30),
        max_queries=8,
    )
    assert result.queries
    assert any(q.template_id == "multilang_seed" for q in result.queries)
    non_zh = [q for q in result.queries if not any("\u4e00" <= c <= "\u9fff" for c in q.query)]
    assert non_zh, "expected non-Chinese open queries"
    print("test_expand_includes_multilang_seeds: PASS")


if __name__ == "__main__":
    test_detect_switzerland_geo_from_chinese()
    test_pivot_china_unicom_switzerland()
    test_multilang_seeds_majority_non_chinese()
    test_initial_open_queries_used_for_general()
    test_expand_includes_multilang_seeds()
    print("All multilang tests passed!")
