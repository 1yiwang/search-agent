"""Tests for Step 61 authority templates + Wave 11 Swiss telecom catalog."""

from coverage import GapHint
from datetime import date
from query_expand import expand_queries
from sources.catalog import clear_catalog_cache, filter_candidates, intent_labels
from sources.telecom_intent import has_swiss_telecom_intent, telecom_intent_score


def test_swiss_telecom_intent_for_unicom():
    topic = "中国联通在瑞士市场开拓的可能性与市场份额"
    assert has_swiss_telecom_intent(topic)
    assert telecom_intent_score(topic) >= 4
    print("test_swiss_telecom_intent_for_unicom: PASS")


def test_swiss_telecom_catalog_filter():
    clear_catalog_cache()
    topic = "中国联通在瑞士市场开拓机会"
    labels = intent_labels(topic)
    assert "swiss_telecom" in labels
    cands = filter_candidates(topic)
    assert cands, "expected swiss telecom catalog entries"
    assert all("telecom" in e.tags for e in cands)
    ids = {e.id for e in cands}
    assert "bakom" in ids or "swisscom_ir" in ids
    print("test_swiss_telecom_catalog_filter: PASS")


def test_ai_topic_still_empty_catalog():
    clear_catalog_cache()
    topic = "European AI short video platform ranking H1 2026"
    assert filter_candidates(topic) == []
    print("test_ai_topic_still_empty_catalog: PASS")


def test_authority_templates_in_expand():
    hints = [GapHint(dimension="_empty", research_goal="Primary sources")]
    result = expand_queries(
        "China Unicom Switzerland market entry",
        hints,
        candidates=[],
        current_date=date(2026, 7, 30),
        max_queries=10,
    )
    ids = [q.template_id for q in result.queries]
    assert any(t.startswith("authority_") for t in ids)
    joined = " ".join(q.query.lower() for q in result.queries)
    assert "report" in joined or "bakom" in joined or "case study" in joined or "limitation" in joined
    print("test_authority_templates_in_expand: PASS")


if __name__ == "__main__":
    test_swiss_telecom_intent_for_unicom()
    test_swiss_telecom_catalog_filter()
    test_ai_topic_still_empty_catalog()
    test_authority_templates_in_expand()
    print("All Step 61 / Wave 11 tests passed!")
