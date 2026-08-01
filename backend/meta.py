"""Meta research layer: clarifying questions and session state (Step 25)."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from llm_context import get_openai_client, get_request_keys
from models import ResearchBrief, ResearchPlan

# Legacy meta clarify — prefer brief.generate_industry_clarifying_questions for Wave 12a.
CLARIFY_PROMPT = """You help scope an INDUSTRY RESEARCH project before searching the web.

Research topic: {topic}

Generate 2-4 short clarifying questions covering when relevant:
- boundary (include/exclude — e.g. avoid GDP/macro unless asked)
- breadth (sub-sectors / product lines)
- depth (overview vs commercial opportunities)
- audience, geo/time, must-include questions

Return ONLY valid JSON:
```json
{{
  "questions": [
    {{
      "id": "q1",
      "category": "boundary",
      "question": "...",
      "hint": "optional answer hint",
      "options": []
    }}
  ]
}}
```

Maximum 4 questions. Plain language. No markdown."""


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
    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
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
            opts = item.get("options") or []
            if not isinstance(opts, list):
                opts = []
            questions.append({
                "id": qid,
                "category": str(item.get("category") or "boundary"),
                "question": question,
                "hint": str(item.get("hint") or ""),
                "options": [str(o) for o in opts if str(o).strip()][:6],
            })

    if not questions:
        questions = [
            {
                "id": "q1",
                "category": "audience",
                "question": "Who is the primary audience for this report?",
                "hint": "e.g. executives, engineers, students",
                "options": [],
            },
            {
                "id": "q2",
                "category": "depth",
                "question": "What depth do you need?",
                "hint": "e.g. executive summary vs detailed analysis",
                "options": [],
            },
            {
                "id": "q3",
                "category": "boundary",
                "question": "Should we stay inside the industry and deprioritize general macro/GDP?",
                "hint": "Usually yes for market-entry topics",
                "options": [],
            },
        ]
    return questions[:4]


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
    brief: ResearchBrief | None = None
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
