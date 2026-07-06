"""Research planner: broad exploration then dimension breakdown (GPT Researcher pattern)."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import config
from llm_context import get_openai_client, get_request_keys
from models import ResearchDimension, ResearchPlan, SearchResult
from search import search_topic_with_seeds

_SOP_PATH = Path(__file__).parent / "prompts" / "research_sop.md"

INITIAL_RESEARCH_PROMPT = """You are a research assistant. Summarize what the provided sources say about the topic.

Research topic: {topic}

Sources:
{sources_text}

Instructions:
1. Use ONLY information from the sources. Do not add outside knowledge.
2. Write 3-6 short paragraphs covering: landscape, key themes, open questions.
3. Note which areas need deeper investigation in follow-up searches.
4. Plain text only, no JSON."""

PLAN_SECTIONS_PROMPT = """You are a research editor planning a deep research project.

Today's date: {date}
Research topic: {topic}

Initial research summary:
{initial_research}

Methodology (DeerFlow / GPT Researcher SOP):
- Broad exploration is done (above).
- Now define dimensions for deep dive: each dimension needs 2-3 targeted search queries.
- Cover diverse angles: facts/data, examples/cases, challenges/criticism where relevant.
- Do NOT include introduction, conclusion, or references as dimensions.

Return ONLY valid JSON:
```json
{{
  "title": "research report title",
  "date": "{date}",
  "dimensions": [
    {{
      "title": "dimension heading",
      "queries": ["search query 1", "search query 2"],
      "priority": 1,
      "info_type": "facts"
    }}
  ]
}}
```

Rules:
- Maximum {max_sections} dimensions.
- Each dimension must have 2-3 queries.
- info_type is one of: facts, cases, criticism, trends
- priority 1 = highest"""


def _load_sop() -> str:
    if _SOP_PATH.is_file():
        return _SOP_PATH.read_text(encoding="utf-8")
    return ""


def _format_sources(sources: list[SearchResult]) -> str:
    parts = []
    for i, source in enumerate(sources, 1):
        text = source.full_text or source.snippet
        parts.append(
            f"--- Source {i} ---\n"
            f"Title: {source.title}\n"
            f"URL: {source.url}\n"
            f"Content:\n{text[:4000]}\n"
        )
    return "\n".join(parts)


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


async def run_initial_research(
    topic: str,
    max_sources: int | None = None,
) -> tuple[str, list[SearchResult]]:
    """Broad exploration: search, fetch, and LLM summary of findings."""
    if max_sources is None:
        max_sources = config.planner_initial_sources

    results, _ = await search_topic_with_seeds(topic, max_sources)
    usable = [
        r for r in results
        if (r.full_text and not r.full_text.startswith("[Failed")) or r.snippet
    ]
    if not usable:
        usable = results

    if not usable:
        return f"No sources found for topic: {topic}", []

    prompt = INITIAL_RESEARCH_PROMPT.format(
        topic=topic,
        sources_text=_format_sources(usable),
    )

    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )

    summary = (response.choices[0].message.content or "").strip()
    if not summary:
        summary = _format_sources(usable)[:6000]
    return summary, usable


async def plan_sections(
    topic: str,
    initial_research: str,
    max_sections: int | None = None,
    human_feedback: str | None = None,
) -> ResearchPlan:
    """Generate dimension breakdown with targeted queries (GPT Researcher editor.plan_research)."""
    if max_sections is None:
        max_sections = config.planner_max_sections

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sop = _load_sop()
    feedback_block = ""
    if human_feedback:
        feedback_block = f"\nHuman feedback to incorporate:\n{human_feedback}\n"

    user_prompt = PLAN_SECTIONS_PROMPT.format(
        date=today,
        topic=topic,
        initial_research=initial_research,
        max_sections=max_sections,
    )
    if feedback_block:
        user_prompt += feedback_block

    system_parts = [
        "You plan structured deep research dimensions with search queries.",
    ]
    if sop:
        system_parts.append(f"Research SOP reference:\n{sop[:2000]}")

    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[
            {"role": "system", "content": "\n".join(system_parts)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=2048,
    )

    raw = _parse_json_object(response.choices[0].message.content or "")
    dimensions: list[ResearchDimension] = []

    for item in raw.get("dimensions") or raw.get("sections") or []:
        if isinstance(item, str):
            dimensions.append(
                ResearchDimension(
                    title=item,
                    queries=[f"{topic} {item}"],
                    priority=len(dimensions) + 1,
                )
            )
            continue
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        queries = [q.strip() for q in (item.get("queries") or []) if q and str(q).strip()]
        if not title:
            continue
        if not queries:
            queries = [f"{topic} {title}"]
        dimensions.append(
            ResearchDimension(
                title=title,
                queries=queries[:3],
                priority=int(item.get("priority") or len(dimensions) + 1),
                info_type=str(item.get("info_type") or "facts"),
            )
        )

    dimensions = dimensions[:max_sections]

    return ResearchPlan(
        topic=topic,
        title=str(raw.get("title") or topic),
        date=str(raw.get("date") or today),
        initial_research_summary=initial_research,
        dimensions=dimensions,
        max_sections=max_sections,
    )


async def create_research_plan(
    topic: str,
    max_sections: int | None = None,
    initial_sources: int | None = None,
    human_feedback: str | None = None,
) -> ResearchPlan:
    """Full Step 20 flow: initial research then section planning."""
    summary, _ = await run_initial_research(topic, max_sources=initial_sources)
    return await plan_sections(
        topic,
        summary,
        max_sections=max_sections,
        human_feedback=human_feedback,
    )
