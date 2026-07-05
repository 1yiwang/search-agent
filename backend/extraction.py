"""LLM-based structured fact extraction."""
import json
from openai import AsyncOpenAI

from config import config
from models import ExtractedFact, SearchResult


client = AsyncOpenAI(
    api_key=config.llm_api_key,
    base_url=config.llm_base_url,
)

EXTRACTION_PROMPT = """You are a research assistant. Extract key facts from the provided sources about the research topic.

Research topic: {topic}

Sources:
{sources_text}

Instructions:
1. Extract ONLY facts directly supported by the provided source text. Do NOT use your own knowledge.
2. For each fact, include the EXACT quoted text from the source that supports it.
3. Rate confidence: "high" (explicitly stated with data), "medium" (stated but without precise data), "low" (implied or vague).
4. Skip facts that are off-topic or advertising/sponsored content.
5. Return a JSON array of objects with these exact keys: fact, source_url, source_title, quoted_text, confidence.

Return ONLY valid JSON, no other text:
```json
[
  {{
    "fact": "...",
    "source_url": "...",
    "source_title": "...",
    "quoted_text": "...",
    "confidence": "high|medium|low"
  }}
]
```"""


def _format_sources(sources: list[SearchResult]) -> str:
    """Format search results into a single text block for the LLM prompt."""
    parts = []
    for i, s in enumerate(sources, 1):
        text = s.full_text or s.snippet
        parts.append(
            f"--- Source {i} ---\n"
            f"Title: {s.title}\n"
            f"URL: {s.url}\n"
            f"Content:\n{text}\n"
        )
    return "\n".join(parts)


async def extract_facts(topic: str, sources: list[SearchResult]) -> list[ExtractedFact]:
    """Extract structured facts from search results using LLM."""
    if not sources:
        return []

    prompt = EXTRACTION_PROMPT.format(
        topic=topic,
        sources_text=_format_sources(sources),
    )

    response = await client.chat.completions.create(
        model=config.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if lines[0].startswith("```") else content
        if content.endswith("```"):
            content = content[:-3]

    try:
        raw_facts = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON array from response
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            raw_facts = json.loads(match.group())
        else:
            raw_facts = []

    facts = []
    for f in raw_facts:
        facts.append(ExtractedFact(
            fact=f.get("fact", ""),
            source_url=f.get("source_url", ""),
            source_title=f.get("source_title", ""),
            quoted_text=f.get("quoted_text", ""),
            confidence=f.get("confidence", "medium"),
        ))
    return facts
