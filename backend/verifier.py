"""Cross-source verification and LLM fact review (Step 22)."""
import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

from openai import AsyncOpenAI

from config import config
from models import ExtractedFact

client = AsyncOpenAI(
    api_key=config.llm_api_key,
    base_url=config.llm_base_url,
)

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}

REVIEW_PROMPT = """You review extracted research facts for quality before report generation.

Research topic: {topic}

Facts (array index is the fact index):
{facts_json}

Instructions:
1. Flag facts to REMOVE only if they are off-topic, promotional, or clearly unsupported by their quoted_text.
2. Do NOT remove facts solely because confidence is low.
3. Suggest at most 2 follow-up search queries only for critical information gaps.

Return ONLY valid JSON:
```json
{{
  "remove_indices": [],
  "notes": "brief review summary",
  "follow_up_queries": []
}}
```"""


@dataclass
class VerificationStats:
    total: int = 0
    corroborated: int = 0
    boosted: int = 0
    demoted: int = 0
    removed_by_review: int = 0
    follow_up_queries: list[str] = field(default_factory=list)
    review_notes: str = ""


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    host = host.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}{parsed.query}"


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _max_confidence(a: str, b: str) -> str:
    return a if CONFIDENCE_RANK[a] >= CONFIDENCE_RANK[b] else b


def _parse_review_json(content: str) -> dict:
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


def verify_cross_source(
    facts: list[ExtractedFact],
    similarity_threshold: float | None = None,
) -> tuple[list[ExtractedFact], VerificationStats]:
    """Boost or demote confidence based on independent source corroboration."""
    if similarity_threshold is None:
        similarity_threshold = config.verifier_similarity_threshold

    stats = VerificationStats(total=len(facts))
    if not facts:
        return facts, stats

    if len(facts) == 1:
        fact = facts[0]
        if fact.confidence == "high":
            stats.demoted = 1
            return [fact.model_copy(update={"confidence": "medium"})], stats
        return facts, stats

    clusters: list[list[ExtractedFact]] = []
    for fact in facts:
        placed = False
        for cluster in clusters:
            if any(
                _similarity(fact.fact, member.fact) >= similarity_threshold
                for member in cluster
            ):
                cluster.append(fact)
                placed = True
                break
        if not placed:
            clusters.append([fact])

    verified: list[ExtractedFact] = []
    for cluster in clusters:
        unique_urls = {_normalize_url(f.source_url) for f in cluster}
        corroborated = len(unique_urls) >= 2

        if corroborated:
            stats.corroborated += len(cluster)
            target = "high" if any(f.confidence in ("medium", "high") for f in cluster) else "medium"
        else:
            target = None

        for fact in cluster:
            new_confidence = fact.confidence
            if corroborated:
                new_confidence = _max_confidence(fact.confidence, target or "medium")
                if CONFIDENCE_RANK[new_confidence] > CONFIDENCE_RANK[fact.confidence]:
                    stats.boosted += 1
            elif fact.confidence == "high":
                new_confidence = "medium"
                stats.demoted += 1

            if new_confidence != fact.confidence:
                verified.append(fact.model_copy(update={"confidence": new_confidence}))
            else:
                verified.append(fact)

    return verified, stats


async def review_facts(
    topic: str,
    facts: list[ExtractedFact],
) -> dict:
    """LLM review: flag weak facts and optional follow-up queries."""
    if not facts:
        return {"remove_indices": [], "notes": "", "follow_up_queries": []}

    facts_payload = [
        {
            "index": i,
            "fact": f.fact,
            "confidence": f.confidence,
            "source_url": f.source_url,
            "quoted_text": f.quoted_text[:300],
        }
        for i, f in enumerate(facts)
    ]

    response = await client.chat.completions.create(
        model=config.llm_model,
        messages=[{
            "role": "user",
            "content": REVIEW_PROMPT.format(
                topic=topic,
                facts_json=json.dumps(facts_payload, ensure_ascii=False, indent=2),
            ),
        }],
        temperature=0.2,
        max_tokens=1024,
    )

    raw = _parse_review_json(response.choices[0].message.content or "")
    remove_indices = [
        int(i) for i in (raw.get("remove_indices") or [])
        if isinstance(i, int) or (isinstance(i, str) and str(i).isdigit())
    ]
    follow_up = [
        str(q).strip()
        for q in (raw.get("follow_up_queries") or [])
        if q and str(q).strip()
    ][:2]

    return {
        "remove_indices": remove_indices,
        "notes": str(raw.get("notes") or "").strip(),
        "follow_up_queries": follow_up,
    }


def apply_review(
    facts: list[ExtractedFact],
    remove_indices: list[int],
) -> list[ExtractedFact]:
    """Drop facts flagged by the reviewer."""
    drop = set(remove_indices)
    return [f for i, f in enumerate(facts) if i not in drop]


async def verify_and_review(
    topic: str,
    facts: list[ExtractedFact],
    max_revisions: int | None = None,
) -> tuple[list[ExtractedFact], VerificationStats]:
    """Cross-source verify then one or more LLM review passes."""
    if max_revisions is None:
        max_revisions = config.verifier_max_revisions

    verified, stats = verify_cross_source(facts)
    current = verified

    for _ in range(max(0, max_revisions)):
        review = await review_facts(topic, current)
        stats.review_notes = review.get("notes") or stats.review_notes
        stats.follow_up_queries = review.get("follow_up_queries") or []

        remove_indices = review.get("remove_indices") or []
        if not remove_indices:
            break

        before = len(current)
        current = apply_review(current, remove_indices)
        stats.removed_by_review += before - len(current)

    stats.total = len(current)
    return current, stats
