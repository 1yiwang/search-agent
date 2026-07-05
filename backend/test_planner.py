"""Unit tests for research planner (mocked LLM)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from models import ResearchDimension
from planner import _parse_json_object, plan_sections, create_research_plan


def test_parse_json_object_strips_fences():
    raw = '```json\n{"title": "T", "dimensions": []}\n```'
    data = _parse_json_object(raw)
    assert data["title"] == "T"


async def _test_plan_sections_parses_dimensions():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""
                {
                  "title": "EU AI Act Overview",
                  "date": "2026-07-05",
                  "dimensions": [
                    {
                      "title": "Regulatory scope",
                      "queries": ["EU AI Act scope requirements", "AI Act high risk systems"],
                      "priority": 1,
                      "info_type": "facts"
                    },
                    {
                      "title": "Industry impact",
                      "queries": ["EU AI Act compliance cost", "AI Act startup impact"],
                      "priority": 2,
                      "info_type": "cases"
                    }
                  ]
                }
                """
            )
        )
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("planner.get_openai_client", return_value=mock_client):
        plan = await plan_sections(
            "EU AI Act",
            "Initial summary about the EU AI Act regulation.",
            max_sections=5,
        )

    assert plan.title == "EU AI Act Overview"
    assert len(plan.dimensions) == 2
    assert all(len(d.queries) >= 1 for d in plan.dimensions)
    assert isinstance(plan.dimensions[0], ResearchDimension)


async def _test_create_research_plan_pipeline():
    with (
        patch("planner.run_initial_research", new_callable=AsyncMock) as mock_initial,
        patch("planner.plan_sections", new_callable=AsyncMock) as mock_plan,
    ):
        mock_initial.return_value = ("summary text", [])
        mock_plan.return_value = MagicMock(
            topic="FastAPI",
            title="FastAPI Guide",
            date="2026-07-05",
            dimensions=[],
            max_sections=5,
            initial_research_summary="summary text",
        )
        await create_research_plan("FastAPI", max_sections=3)

    mock_initial.assert_awaited_once()
    mock_plan.assert_awaited_once()


if __name__ == "__main__":
    test_parse_json_object_strips_fences()
    asyncio.run(_test_plan_sections_parses_dimensions())
    asyncio.run(_test_create_research_plan_pipeline())
    print("test_planner: PASS")
