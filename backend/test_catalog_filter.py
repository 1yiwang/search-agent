"""Catalog filter behavior for general vs vertical topics."""
from sources.catalog import filter_candidates, intent_labels


def test_general_topic_gets_empty_catalog():
    topic = "European AI short video platform ranking H1 2026"
    # May label as dach_venture via geo keyword alone, but catalog stays empty
    # until venture+geo is strong enough — open-web first.
    assert filter_candidates(topic) == []
    print("test_general_topic_gets_empty_catalog: PASS")


def test_pd_topic_gets_catalog():
    topic = "European corporate direct lending fundraising trends 2026"
    assert "private_debt" in intent_labels(topic)
    assert len(filter_candidates(topic)) > 0
    print("test_pd_topic_gets_catalog: PASS")


if __name__ == "__main__":
    test_general_topic_gets_empty_catalog()
    test_pd_topic_gets_catalog()
    print("All catalog filter tests passed!")
