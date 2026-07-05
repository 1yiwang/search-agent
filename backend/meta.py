"""Meta research layer: clarifying questions and session state (Step 25)."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from openai import AsyncOpenAI

from config import config
from models import ResearchPlan

client = AsyncOpenAI(
    api_key=config.llm_api_key,
    base_url=config.llm_base_url,
)

CLARIFY_PROMPT = """You help scope a deep research project before searching the web.

Research topic: {topic}

Generate 2-3 short clarifying questions to narrow scope. Consider:
- target audience and depth (overview vs technical)
- geography or jurisdiction if relevant
- time frame (current state vs history)
- specific angles to include or exclude

Return ONLY valid JSON:
```json
{{
  "questions": [
    {{"id": "q1", "question": "...", "hint": "optional answer hint"}}
  ]
}}
```

Maximum 3 questions. Plain language. No markdown."""


def _parse_json_object(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3].strip()

    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}


async def generate_clarifying_questions(topic: str) -> list[dict]:
    """LLM-generated scope questions (no web search)."""
    response = await client.chat.completions.create(
        model=config.llm_model,
        messages=[{"role": "user", "content": CLARIFY_PROMPT.format(topic=topic)}],
        temperature=0.4,
        max_tokens=512,
    )

    raw = _parse_json_object(response.choices[0].message.content or "")
    questions = []
    for i, item in enumerate(raw.get("questions") or []):
        if isinstance(item, str):
            questions.append({"id": f"q{i + 1}", "question": item, "hint": ""})
            continue
        if not isinstance(item, dict):
            continue
        qid = str(item.get("id") or f"q{i + 1}")
        question = str(item.get("question") or "").strip()
        if question:
            questions.append({
                "id": qid,
                "question": question,
                "hint": str(item.get("hint") or ""),
            })

    if not questions:
        questions = [
            {
                "id": "q1",
                "question": "Who is the primary audience for this report?",
                "hint": "e.g. executives, engineers, students",
            },
            {
                "id": "q2",
                "question": "What depth do you need?",
                "hint": "e.g. executive summary vs detailed analysis",
            },
        ]
    return questions[:3]


def format_human_feedback(answers: dict[str, str], questions: list[dict]) -> str:
    """Turn Q&A into planner human_feedback text."""
    qmap = {q["id"]: q["question"] for q in questions}
    blocks = []
    for qid, answer in answers.items():
        text = (answer or "").strip()
        if text:
            blocks.append(f"Q: {qmap.get(qid, qid)}\nA: {text}")
    return "\n\n".join(blocks)


@dataclass
class MetaSession:
    session_id: str
    topic: str
    questions: list[dict] = field(default_factory=list)
    answers: dict[str, str] = field(default_factory=dict)
    plan: ResearchPlan | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_sessions: dict[str, MetaSession] = {}
_SESSION_TTL = timedelta(hours=2)


def _purge_expired() -> None:
    now = datetime.now(timezone.utc)
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.created_at > _SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]


def create_session(topic: str, questions: list[dict]) -> MetaSession:
    _purge_expired()
    session = MetaSession(
        session_id=str(uuid4()),
        topic=topic,
        questions=questions,
    )
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> MetaSession | None:
    _purge_expired()
    return _sessions.get(session_id)


def clear_sessions() -> None:
    """Clear all sessions (for tests)."""
    _sessions.clear()
