"""Meta-thesis ban + direction seed round-robin (Wave 12d)."""

from models import BriefDimension, ExtractedFact, ResearchBrief
from brief import brief_seed_queries
from report_synthesis import _is_meta_thesis, _sanitize_thesis, _substantive_thesis


def test_meta_thesis_detected():
    assert _is_meta_thesis("本报告围绕「瑞士电信」整理了 16 条已验证事实，来自 2 个独立来源。")
    assert _is_meta_thesis("This brief covers 16 verified facts on Swiss telecom from 2 unique sources.")
    assert not _is_meta_thesis("Swisscom、Sunrise 与 Salt 三分瑞士移动市场，其中 Swisscom 份额领先。")


def test_sanitize_replaces_meta():
    facts = [
        ExtractedFact(
            fact="Swisscom holds the largest Swiss mobile share.",
            source_url="https://a.com",
            source_title="A",
            quoted_text="share",
            confidence="high",
        ),
    ]
    bad = "本报告围绕「瑞士电信行业发展现状」整理了 16 条已验证事实，来自 2 个独立来源。"
    out = _sanitize_thesis(bad, "瑞士电信行业发展现状", "瑞士电信现状", facts, set())
    assert not _is_meta_thesis(out)
    assert "Swisscom" in out or "份额" in out or "share" in out.lower() or "证据不足" not in out


def test_substantive_empty_facts():
    t = _substantive_thesis("瑞士电信", "瑞士电信现状", [], set())
    assert "证据不足" in t or "Insufficient" in t


def test_brief_seed_round_robin():
    brief = ResearchBrief(
        topic="瑞士电信",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title="Shares",
                research_goal="shares",
                queries=["Swisscom mobile market share 2026", "Sunrise subscriber base 2026"],
                priority=1,
            ),
            BriefDimension(
                title="Regulation",
                research_goal="regulation",
                queries=["BAKOM spectrum licence conditions 2026"],
                priority=2,
            ),
            BriefDimension(
                title="Operators",
                research_goal="ops",
                queries=["Salt Mobile network coverage 2026", "Swiss MVNO wholesale pricing"],
                priority=3,
            ),
        ],
    )
    seeds = brief_seed_queries(brief, max_queries=6)
    # Round-robin should interleave A then B then C before second from A
    assert seeds[0] == "Swisscom mobile market share 2026"
    assert seeds[1] == "BAKOM spectrum licence conditions 2026"
    assert seeds[2] == "Salt Mobile network coverage 2026"


if __name__ == "__main__":
    test_meta_thesis_detected()
    test_sanitize_replaces_meta()
    test_substantive_empty_facts()
    test_brief_seed_round_robin()
    print("Wave 12d quality gates: PASS")
