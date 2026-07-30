"""Tests for Wave 10 Step 62 depth profiles."""

from depth_profile import (
    depth_overrides,
    get_depth_profile,
    resolve_request,
)
from models import ResearchRequest
from config import config


def test_fast_profile_smaller_than_deep():
    fast = get_depth_profile("fast")
    deep = get_depth_profile("deep")
    assert fast.max_sources < deep.max_sources
    assert fast.max_hops < deep.max_hops
    assert fast.open_max_queries < deep.open_max_queries
    print("test_fast_profile_smaller_than_deep: PASS")


def test_resolve_request_applies_max_sources():
    req = ResearchRequest(topic="China Unicom Switzerland market", depth="fast")
    resolved, profile = resolve_request(req)
    assert profile.name == "fast"
    assert resolved.max_sources == 8
    assert resolved.depth == "fast"
    print("test_resolve_request_applies_max_sources: PASS")


def test_depth_overrides_restore_config():
    before = config.research_max_hops
    profile = get_depth_profile("fast")
    with depth_overrides(profile):
        assert config.research_max_hops == profile.max_hops
        assert config.open_max_queries_per_hop == profile.open_max_queries
    assert config.research_max_hops == before
    print("test_depth_overrides_restore_config: PASS")


if __name__ == "__main__":
    test_fast_profile_smaller_than_deep()
    test_resolve_request_applies_max_sources()
    test_depth_overrides_restore_config()
    print("All depth profile tests passed!")
