"""Unit tests for meta clarifying questions."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from meta import (
    clear_sessions,
    create_session,
    format_human_feedback,
    generate_clarifying_questions,
    get_session,
)


async def _test_generate_clarifying_questions():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="""
        {
          "questions": [
            {"id": "q1", "question": "Which EU member states?", "hint": "all or specific"},
            {"id": "q2", "question": "Focus on compliance or impact?", "hint": ""}
          ]
        }
        """))
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("meta.get_openai_client", return_value=mock_client):
        questions = await generate_clarifying_questions("EU AI Act")

    assert len(questions) == 2
    assert questions[0]["id"] == "q1"


def test_format_human_feedback():
    questions = [{"id": "q1", "question": "Audience?"}]
    text = format_human_feedback({"q1": "Engineers"}, questions)
    assert "Engineers" in text
    assert "Audience?" in text


def test_session_lifecycle():
    clear_sessions()
    session = create_session("FastAPI", [{"id": "q1", "question": "Depth?"}])
    loaded = get_session(session.session_id)
    assert loaded is not None
    assert loaded.topic == "FastAPI"
    clear_sessions()


if __name__ == "__main__":
    asyncio.run(_test_generate_clarifying_questions())
    test_format_human_feedback()
    test_session_lifecycle()
    print("test_meta: PASS")
