"""Wave 12h Step 88: bilingual skeleton + thesis gate + sections == directions."""

from models import (
    BriefDimension,
    EvidenceDraft,
    EvidenceDraftSlot,
    ExtractedFact,
    ReportArgument,
    ReportSynthesis,
    ResearchBrief,
)
from report_labels import get_labels, report_language
from report_outlines import slots_from_brief
from report_synthesis import (
    _align_arguments_to_slots,
    _judgment_thesis,
    _sanitize_thesis,
    check_thesis,
    fallback_synthesis,
)
from reporter import generate_report


def _facts(n: int = 3) -> list[ExtractedFact]:
    return [
        ExtractedFact(
            fact=f"Swisscom 在瑞士移动市场占约 {50 + i}% 份额。",
            source_url=f"https://example.com/{i}",
            source_title=f"来源 {i}",
            quoted_text=f"Swisscom held {50 + i}% of the Swiss mobile market",
            confidence="high" if i == 0 else "medium",
        )
        for i in range(n)
    ]


def test_chinese_report_has_no_english_skeleton():
    topic = "中国运营商进入瑞士电信市场的机会"
    assert report_language(topic) == "zh"
    synthesis = ReportSynthesis(
        thesis="就瑞士电信市场，证据支持的判断是 Swisscom 约 55% 份额构成主要壁垒，但 MVNO 批发价仍留有空间。",
        key_takeaways=["Swisscom 份额约 55% [1]"],
        arguments=[ReportArgument(claim="份额高度集中。", body="正文 [1]", heading="市场结构", slot_id="s1")],
        so_what="优先走 MVNO 批发路径验证成本。",
        gaps="监管一节仍缺公开数据。",
        coverage="已检索：瑞士电信份额",
    )
    report = generate_report(topic, _facts(), synthesis=synthesis)
    md = report.markdown
    for english in ("## Conclusion", "## Arguments", "## Limits", "## Sources", "## Coverage"):
        assert english not in md, english
    labels = get_labels(topic)
    assert f"## {labels['conclusion']}" in md
    assert f"## {labels['arguments']}" in md
    assert f"## {labels['so_what']}" in md
    assert f"## {labels['sources']}" in md


def test_header_has_no_process_metrics_and_meta_moves_to_end():
    topic = "Swiss telecom market entry for Chinese carriers"
    synthesis = ReportSynthesis(
        thesis="Swisscom holds roughly 55% of Swiss mobile, so entry needs an MVNO route, though wholesale pricing is unverified.",
        arguments=[ReportArgument(claim="Market is concentrated.", body="Body [1]", heading="Structure", slot_id="s1")],
    )
    report = generate_report(topic, _facts(), synthesis=synthesis)
    head = report.markdown.split("---", 1)[0]
    assert "facts from" not in head
    assert "Generated:" not in head
    labels = get_labels(topic)
    tail = report.markdown.rsplit("---", 3)[-1] + report.markdown
    assert f"## {labels['appendix_meta']}" in report.markdown
    assert f"{labels['fact_count']}: 3" in tail


def test_thesis_gate_flags_meta_and_language():
    zh_topic = "瑞士电信市场进入"
    meta = check_thesis("本报告围绕「瑞士电信」整理了 16 条已验证事实，来自 2 个独立来源。", zh_topic)
    assert not meta.ok and "meta_narrative" in meta.reasons

    mismatch = check_thesis(
        "Swisscom holds roughly 55% of the Swiss mobile market, but wholesale pricing is unclear.",
        zh_topic,
    )
    assert not mismatch.ok and "language_mismatch" in mismatch.reasons

    short = check_thesis("份额集中。", zh_topic)
    assert not short.ok and "too_short" in short.reasons

    soft = check_thesis(
        "瑞士移动市场由三家运营商主导，新进入者只能走批发路线，这一判断依赖公开披露的资费口径。",
        zh_topic,
    )
    assert soft.ok
    assert "no_anchor" in soft.reasons  # soft reason, still passes the gate

    good = check_thesis(
        "Swisscom 以约 55% 份额主导瑞士移动市场，新进入者短期只能走 MVNO 批发路线，但批发资费尚无公开定价可核。",
        zh_topic,
    )
    assert good.ok and not [r for r in good.reasons if r in {"meta_narrative", "too_short"}]


def test_thesis_fallback_is_judgment_not_concatenation():
    topic = "瑞士电信市场进入"
    out = _sanitize_thesis(
        "本报告围绕「瑞士电信」整理了 16 条已验证事实。", topic, "中国运营商进入瑞士", _facts(), set(),
    )
    assert "整理了" not in out
    assert out.startswith("就「")
    assert "判断" in out
    verdict = check_thesis(out, topic)
    assert verdict.ok

    empty = _judgment_thesis(topic, "中国运营商进入瑞士", [], set())
    assert "证据不足" in empty


def test_sections_equal_directions_with_honest_empty_slot():
    brief = ResearchBrief(
        topic="中国运营商进入瑞士电信市场",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title=f"方向{i}",
                direction_detail=f"调研 Swisscom 在方向{i}的表现",
                phase_id=f"p{i}",
                direction_id=f"p{i}",
                queries=["Swisscom market share 2026"],
                priority=i,
            )
            for i in range(1, 7)
        ],
    )
    slots = slots_from_brief(brief)
    assert len(slots) == 6
    assert all(s["required"] for s in slots), "approved directions must not be optional"

    draft = EvidenceDraft(
        topic_restatement=brief.topic,
        outline_id="market_entry",
        slots=[
            EvidenceDraftSlot(
                slot_id=s["id"], title=s["title"], writing_goal=s["writing_goal"], required=True,
            )
            for s in slots
        ],
    )
    written = [
        ReportArgument(claim="有证据。", body="正文 [1]", heading="方向1", slot_id="p1"),
        ReportArgument(claim="也有证据。", body="正文 [2]", heading="方向2", slot_id="p2"),
    ]
    aligned = _align_arguments_to_slots(
        written, draft, ["Swisscom market share 2026", "BAKOM spectrum 2026"], brief.topic,
    )
    assert len(aligned) == 6
    assert [a.slot_id for a in aligned] == [f"p{i}" for i in range(1, 7)]
    empty = aligned[5]
    assert "未获得可引用证据" in empty.claim
    assert "已执行检索" in empty.body
    assert "建议补充信源" in empty.body
    assert empty.citation_indices == []


def test_fallback_synthesis_keeps_every_direction():
    brief = ResearchBrief(
        topic="中国运营商进入瑞士电信市场",
        framework_id="market_entry",
        dimensions=[
            BriefDimension(
                title=f"方向{i}",
                direction_detail=f"调研 Swisscom 在方向{i}的表现",
                phase_id=f"p{i}",
                direction_id=f"p{i}",
                priority=i,
            )
            for i in range(1, 8)
        ],
    )
    syn = fallback_synthesis(brief.topic, _facts(2), ["Swisscom share"], brief=brief)
    assert len(syn.arguments) == 7
    assert check_thesis(syn.thesis, brief.topic).ok


def test_slot_writing_goal_not_duplicated():
    brief = ResearchBrief(
        topic="瑞士跨境电商",
        dimensions=[
            BriefDimension(
                title="市场结构",
                research_goal="调研瑞士跨境电商市场规模",
                direction_detail="调研瑞士跨境电商市场规模",
                must_answer=["市场规模多大？"],
                phase_id="industry_structure",
            ),
        ],
    )
    goal = slots_from_brief(brief)[0]["writing_goal"]
    assert goal.count("调研瑞士跨境电商市场规模") == 1
    assert "必须回答" in goal


if __name__ == "__main__":
    test_chinese_report_has_no_english_skeleton()
    test_header_has_no_process_metrics_and_meta_moves_to_end()
    test_thesis_gate_flags_meta_and_language()
    test_thesis_fallback_is_judgment_not_concatenation()
    test_sections_equal_directions_with_honest_empty_slot()
    test_fallback_synthesis_keeps_every_direction()
    test_slot_writing_goal_not_duplicated()
    print("Wave 12h Step 88 report contract: PASS")
