"""Tests for private debt source registry and seed query builder."""
from sources.pd_registry import (
    build_pd_seed_queries,
    clear_pd_registry_cache,
    has_private_debt_intent,
    load_pd_sources,
    private_debt_intent_score,
)
from sources.seeds import build_combined_seed_queries, has_registry_intent


def test_load_pd_sources():
    clear_pd_registry_cache()
    sources = load_pd_sources()
    assert len(sources) >= 6
    assert any(s.domain == "stepstonegroup.com" for s in sources)
    print("test_load_pd_sources: PASS")


def test_private_debt_intent_european_direct_lending():
    topic = "European corporate direct lending fundraising and deployment trends H1 2026"
    assert private_debt_intent_score(topic) >= 3
    assert has_private_debt_intent(topic)
    print("test_private_debt_intent_european_direct_lending: PASS")


def test_no_pd_intent_generic_topic():
    topic = "Python FastAPI tutorial"
    assert not has_private_debt_intent(topic)
    assert build_pd_seed_queries(topic) == []
    print("test_no_pd_intent_generic_topic: PASS")


def test_build_pd_seed_queries_site_prefix():
    clear_pd_registry_cache()
    topic = "European private debt direct lending fundraising 2026"
    seeds = build_pd_seed_queries(topic, max_seeds=4)
    assert len(seeds) == 4
    assert all("site:" in q for q in seeds)
    assert any("stepstonegroup" in q or "finews" in q or "privateequityinternational" in q for q in seeds)
    print("test_build_pd_seed_queries_site_prefix: PASS")


def test_combined_seeds_private_debt_topic():
    clear_pd_registry_cache()
    topic = "European corporate direct lending market trends 2026"
    seeds = build_combined_seed_queries(topic, max_seeds=5)
    assert len(seeds) >= 3
    assert has_registry_intent(topic)
    print("test_combined_seeds_private_debt_topic: PASS")


if __name__ == "__main__":
    test_load_pd_sources()
    test_private_debt_intent_european_direct_lending()
    test_no_pd_intent_generic_topic()
    test_build_pd_seed_queries_site_prefix()
    test_combined_seeds_private_debt_topic()
    print("All private debt registry tests passed!")
