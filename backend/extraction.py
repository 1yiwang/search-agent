"""LLM-based structured fact extraction."""
import asyncio
import json
import re

from config import config
from llm_context import get_openai_client, get_request_keys
from models import ExtractedFact, SearchResult
from sources.seeds import has_registry_intent

SINGLE_SOURCE_PROMPT = """You are a research assistant. Extract key facts from ONE source about the research topic.

Research topic: {topic}
Recency window: prefer facts from the last {recency_days} days when dates are present.

Source:
Title: {title}
URL: {url}
Content:
{content}

Instructions:
1. Extract ONLY facts directly supported by the source text. Do NOT use your own knowledge.
2. For each fact, include the EXACT quoted text from the source that supports it.
3. Rate confidence: "high" (explicitly stated with data), "medium" (stated but without precise data), "low" (implied or vague).
4. If the source states when an event happened, set event_date (YYYY, YYYY-MM, or YYYY-MM-DD); otherwise use "".
5. Skip facts that are off-topic or advertising/sponsored content.
6. Return a JSON array of objects with keys: fact, quoted_text, confidence, event_date.
   Do NOT invent source_url or source_title — they are fixed for this source.

Return ONLY valid JSON, no other text:
```json
[
  {{
    "fact": "...",
    "quoted_text": "...",
    "confidence": "high|medium|low",
    "event_date": "2026-05 or empty string"
  }}
]
```"""


def _parse_facts_json(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3]

    try:
        raw = json.loads(content)
        return raw if isinstance(raw, list) else []
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            try:
                raw = json.loads(match.group())
                return raw if isinstance(raw, list) else []
            except json.JSONDecodeError:
                return []
        return []


def _to_extracted_facts(
    raw_facts: list[dict],
    source: SearchResult,
) -> list[ExtractedFact]:
    facts = []
    for item in raw_facts:
        fact_text = item.get("fact", "").strip()
        quoted = item.get("quoted_text", "").strip()
        if not fact_text or not quoted:
            continue
        facts.append(
            ExtractedFact(
                fact=fact_text,
                source_url=source.url,
                source_title=source.title,
                quoted_text=quoted,
                event_date=str(item.get("event_date") or "").strip(),
                confidence=item.get("confidence", "medium"),
            )
        )
    return facts


async def extract_facts_from_source(
    topic: str,
    source: SearchResult,
) -> list[ExtractedFact]:
    """Extract facts from a single source via LLM."""
    content = source.full_text or source.snippet
    if not content or content.startswith("[Failed"):
        return []

    recency_days = config.research_recency_days if has_registry_intent(topic) else 365
    prompt = SINGLE_SOURCE_PROMPT.format(
        topic=topic,
        recency_days=recency_days,
        title=source.title,
        url=source.url,
        content=content,
    )

    response = await get_openai_client().chat.completions.create(
        model=get_request_keys().llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2048,
    )

    content_out = response.choices[0].message.content or ""
    raw_facts = _parse_facts_json(content_out)
    return _to_extracted_facts(raw_facts, source)


async def extract_facts(
    topic: str,
    sources: list[SearchResult],
) -> list[ExtractedFact]:
    """Extract facts from each source concurrently (bounded by semaphore)."""
    if not sources:
        return []

    semaphore = asyncio.Semaphore(config.extract_concurrency)

    async def extract_one(source: SearchResult) -> list[ExtractedFact]:
        async with semaphore:
            return await extract_facts_from_source(topic, source)

    batches = await asyncio.gather(*[extract_one(s) for s in sources])
    facts: list[ExtractedFact] = []
    for batch in batches:
        facts.extend(batch)
    return facts
