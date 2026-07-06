"""Tests for DACH source registry and seed query builder."""
from sources.registry import (
    build_seed_queries,
    clear_registry_cache,
    dach_intent_score,
    has_dach_intent,
    load_sources,
)


def test_load_sources():
    clear_registry_cache()
    sources = load_sources()
    assert len(sources) >= 10
    assert any(s.domain == "startupticker.ch" for s in sources)
    print("test_load_sources: PASS")


def test_dach_intent_swiss_robotics():
    topic = "找到瑞士2026年5月到7月被投资的机器人初创公司和投资机构名单"
    assert dach_intent_score(topic) >= 3
    assert has_dach_intent(topic)
    print("test_dach_intent_swiss_robotics: PASS")


def test_no_intent_generic_topic():
    topic = "Python FastAPI tutorial"
    assert not has_dach_intent(topic)
    assert build_seed_queries(topic) == []
    print("test_no_intent_generic_topic: PASS")


def test_build_seed_queries_site_prefix():
    clear_registry_cache()
    topic = "Swiss robotics startup funding Zurich 2026"
    seeds = build_seed_queries(topic, max_seeds=4)
    assert len(seeds) == 4
    assert all("site:" in q for q in seeds)
    assert any(
        domain in q
        for q in seeds
        for domain in ("startupticker", "swissfundraising", "venturelab", "swissnex", "sifted")
    )
    print("test_build_seed_queries_site_prefix: PASS")


if __name__ == "__main__":
    test_load_sources()
    test_dach_intent_swiss_robotics()
    test_no_intent_generic_topic()
    test_build_seed_queries_site_prefix()
    print("All dach registry tests passed!")
