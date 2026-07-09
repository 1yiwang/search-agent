"""Tests for unified source catalog."""
from sources.catalog import clear_catalog_cache, filter_candidates, load_catalog


def test_load_catalog_count():
    clear_catalog_cache()
    catalog = load_catalog()
    assert len(catalog) >= 30
    assert any(s.id == "stepstone_insights" for s in catalog)
    assert any(s.id == "startupticker" for s in catalog)
    assert any(s.id == "finma" for s in catalog)
    print("test_load_catalog_count: PASS")


def test_filter_private_debt_topic():
    clear_catalog_cache()
    topic = "European corporate direct lending fundraising trends 2026"
    candidates = filter_candidates(topic, max_candidates=10)
    assert len(candidates) >= 5
    ids = {c.id for c in candidates}
    assert "stepstone_insights" in ids or "pei" in ids
    print("test_filter_private_debt_topic: PASS")


if __name__ == "__main__":
    test_load_catalog_count()
    test_filter_private_debt_topic()
    print("All catalog tests passed!")
