"""Wave 12h Step 89: citation integrity gate + strong model + visible degradation."""

import asyncio

from citation_integrity import enforce_citation_integrity
from config import config
from llm_context import RequestKeys, get_strong_model, set_request_keys
from models import (
    BriefDimension,
    EvidenceDraft,
    EvidenceDraftSlot,
    ExtractedFact,
    ReportArgument,
    ResearchBrief,
)
from report_synthesis import fallback_synthesis, write_from_draft


def _facts() -> list[ExtractedFact]:
    return [
        ExtractedFact(
            fact="Swisscom 在瑞士移动市场约占 55% 份额。",
            source_url="https://example.com/1",
            source_title="份额",
            quoted_text="Swisscom held about 55% of the Swiss mobile market",
            confidence="high",
        ),
        ExtractedFact(
            fact="瑞士 MVNO 批发资费每 GB 2 至 4 瑞郎。",
            source_url="https://example.com/2",
            source_title="批发",
            quoted_text="wholesale rates range from CHF 2 to 4 per GB",
            confidence="medium",
        ),
    ]


def _draft(fact_indices: list[int]) -> EvidenceDraft:
    return EvidenceDraft(
        topic_restatement="中国运营商进入瑞士电信市场",
        outline_id="market_entry",
        slots=[
            EvidenceDraftSlot(
                slot_id="industry_structure",
                title="市场结构",
                fact_indices=fact_indices,
                required=True,
            ),
        ],
    )


def test_out_of_slot_citation_is_stripped():
    arg = ReportArgument(
        claim="Swisscom 领先。",
        body="份额约 55% [1]，另有越界引用 [2]。",
        slot_id="industry_structure",
    )
    result = enforce_citation_integrity([arg], _draft([1]), _facts(), lang="zh")
    assert [i.kind for i in result.issues] == ["out_of_slot"]
    assert result.arguments[0].citation_indices == [1]
    assert "[2]" not in result.arguments[0].body


def test_missing_citation_is_never_backfilled():
    arg = ReportArgument(
        claim="Swisscom 领先。",
        body="这一段完全没有引用标记。",
        slot_id="industry_structure",
        confidence="high",
    )
    result = enforce_citation_integrity([arg], _draft([1, 2]), _facts(), lang="zh")
    assert [i.kind for i in result.issues] == ["no_citation"]
    assert result.arguments[0].citation_indices == []
    assert result.arguments[0].confidence == "low"


def test_number_must_appear_in_cited_source():
    backed = ReportArgument(
        claim="份额领先。", body="Swisscom 约占 55% [1]。", slot_id="industry_structure",
    )
    clean = enforce_citation_integrity([backed], _draft([1]), _facts(), lang="zh")
    assert clean.issues == []

    invented = ReportArgument(
        claim="份额领先。", body="Swisscom 约占 87% [1]。", slot_id="industry_structure",
    )
    flagged = enforce_citation_integrity([invented], _draft([1]), _facts(), lang="zh")
    assert [i.kind for i in flagged.issues] == ["unbacked_number"]
    assert flagged.arguments[0].confidence == "low"


def test_empty_slot_section_is_not_flagged():
    arg = ReportArgument(
        claim="「市场结构」未获得可引用证据。",
        body="已执行检索：Swisscom market share。",
        slot_id="industry_structure",
    )
    result = enforce_citation_integrity([arg], _draft([]), _facts(), lang="zh")
    assert result.issues == []


def test_gate_summary_reaches_limits_section():
    brief = ResearchBrief(
        topic="中国运营商进入瑞士电信市场",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title="市场结构",
                direction_detail="调研 Swisscom 与 Sunrise 的移动份额。",
                phase_id="industry_structure",
                direction_id="industry_structure",
            ),
        ],
    )
    syn = fallback_synthesis(brief.topic, _facts(), ["Swisscom share"], brief=brief)
    # The deterministic writer cites inline, so it must pass its own gate
    assert syn.citation_issues == []
    assert all("[" in a.body for a in syn.arguments if a.citation_indices)


def test_degraded_synthesis_is_visible():
    set_request_keys(RequestKeys(llm_api_key="", llm_base_url="", llm_model=""))
    try:
        syn = asyncio.run(write_from_draft(
            "中国运营商进入瑞士电信市场", _facts(), _draft([1]), ["Swisscom share"],
        ))
    finally:
        set_request_keys(None)
    assert syn.degraded_reason == "no_llm_key"


def test_strong_model_upgrades_weak_alias():
    original_model, original_brief = config.llm_model, config.llm_brief_model
    config.llm_model, config.llm_brief_model = "deepseek-v4-pro", ""
    set_request_keys(RequestKeys(
        llm_api_key="k", llm_base_url="https://x", llm_model="gpt-4o-mini",
    ))
    try:
        assert get_strong_model() == "deepseek-v4-pro"
        set_request_keys(RequestKeys(
            llm_api_key="k", llm_base_url="https://x", llm_model="claude-opus-4",
        ))
        assert get_strong_model() == "claude-opus-4"
    finally:
        set_request_keys(None)
        config.llm_model, config.llm_brief_model = original_model, original_brief


if __name__ == "__main__":
    test_out_of_slot_citation_is_stripped()
    test_missing_citation_is_never_backfilled()
    test_number_must_appear_in_cited_source()
    test_empty_slot_section_is_not_flagged()
    test_gate_summary_reaches_limits_section()
    test_degraded_synthesis_is_visible()
    test_strong_model_upgrades_weak_alias()
    print("Wave 12h Step 89 citation gate: PASS")
