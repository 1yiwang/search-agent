# Search Agent Phase 1 — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the complete pipeline: "one question → search → structured report with source citations", deployed to `yiwang.dev/research/<slug>/`.

**Architecture:** FastAPI backend (Python 3.12+) handles search execution, LLM extraction, and SSE streaming. Next.js 16 frontend provides the search input UI and report display with citation verification. Backend and frontend communicate via REST + SSE. Reports are rendered as static HTML and deployed via GitHub → Vercel.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, duckduckgo_search, openai (SDK), httpx, markdownify, Next.js 16, React 19, Tailwind CSS v4, TypeScript

## Global Constraints

- Code repository: `D:/Projects/search-agent/` (already exists with `product-description.md`)
- Backend package: `backend/` directory inside the repo root
- Frontend application: `frontend/` directory inside the repo root
- LLM API key: read from environment variable `LLM_API_KEY`, with `LLM_BASE_URL` and `LLM_MODEL` for flexibility
- Search: DuckDuckGo (no API key required, zero barrier)
- Web fetch: httpx + markdownify (no external service dependency)
- Phase 1 is single-user (Monica), no authentication, no database
- Reports deploy to `https://yiwang.dev/research/<slug>/`
- All source citations use `[¹]` `[²]` format, each linked to original URL + quoted text
- Python dependencies in `backend/requirements.txt`, managed with pip
- JavaScript dependencies managed with pnpm

---

### Task 1: Project Scaffolding

**Files:**
- Create: `D:/Projects/search-agent/backend/requirements.txt`
- Create: `D:/Projects/search-agent/backend/main.py`
- Create: `D:/Projects/search-agent/backend/config.py`
- Create: `D:/Projects/search-agent/frontend/` (Next.js app via create-next-app)

**Interfaces:**
- Produces: FastAPI app skeleton on port 8000, Next.js dev server on port 3000

- [ ] **Step 1: Create backend requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.5
duckduckgo_search==7.5.1
openai==1.68.2
httpx==0.28.1
markdownify==1.1.0
sse-starlette==2.2.1
python-dotenv==1.0.1
```

- [ ] **Step 2: Create backend config.py**

```python
"""Configuration from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

    search_max_results: int = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
    report_output_dir: str = os.getenv(
        "REPORT_OUTPUT_DIR",
        os.path.join(os.path.dirname(__file__), "..", "reports"),
    )


config = Config()
```

- [ ] **Step 3: Create backend/main.py (skeleton)**

```python
"""Search Agent — FastAPI backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Search Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yiwang.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: Scaffold Next.js frontend**

Run:
```bash
cd D:/Projects/search-agent
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --use-pnpm
```

- [ ] **Step 5: Verify both servers start**

```bash
# Terminal 1 — backend
cd D:/Projects/search-agent/backend
python main.py
# Expected: Uvicorn running on http://0.0.0.0:8000

# Terminal 2 — frontend
cd D:/Projects/search-agent/frontend
pnpm dev
# Expected: Next.js running on http://localhost:3000
```

- [ ] **Step 6: Test health endpoint**

```bash
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
```

- [ ] **Step 7: Commit**

```bash
cd D:/Projects/search-agent
git add backend/requirements.txt backend/config.py backend/main.py frontend/
git commit -m "feat: scaffold FastAPI backend and Next.js frontend

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Pydantic Data Models

**Files:**
- Create: `D:/Projects/search-agent/backend/models.py`

**Interfaces:**
- Produces:
  - `ResearchRequest(topic: str, max_sources: int = 10)`
  - `SearchResult(url: str, title: str, snippet: str, full_text: str = "")`
  - `ExtractedFact(fact: str, source_url: str, source_title: str, quoted_text: str, confidence: str = "medium")`
  - `Citation(index: int, source_name: str, source_url: str, quoted_text: str, highlight_anchor: str)`
  - `ResearchReport(topic: str, slug: str, facts: list[ExtractedFact], citations: list[Citation], markdown: str, metadata: dict)`
  - `SSEEvent(event: str, data: dict)`

- [ ] **Step 1: Write models.py**

```python
"""Pydantic data models for Search Agent."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    """Incoming research request from the frontend."""
    topic: str = Field(..., min_length=3, max_length=500, description="Research topic/question")
    max_sources: int = Field(default=10, ge=3, le=30, description="Maximum sources to fetch")


class SearchResult(BaseModel):
    """A single search result from DuckDuckGo or other engines."""
    url: str
    title: str
    snippet: str
    full_text: str = ""  # populated after web_fetch


class ExtractedFact(BaseModel):
    """A single fact extracted from a source."""
    fact: str = Field(..., description="The fact statement")
    source_url: str
    source_title: str
    quoted_text: str = Field(..., description="The original text supporting this fact")
    confidence: str = Field(default="medium", pattern="^(high|medium|low)$")


class Citation(BaseModel):
    """Citation entry linking report text to source."""
    index: int = Field(..., description="Citation number, e.g. 1 for [¹]")
    source_name: str
    source_url: str
    quoted_text: str
    highlight_anchor: str = Field(
        default="",
        description="Substring to highlight in the source text",
    )


class ReportMetadata(BaseModel):
    """Execution metadata for the report."""
    execution_time_seconds: float
    source_count: int
    topics_searched: list[str]
    started_at: str
    completed_at: str


class ResearchReport(BaseModel):
    """Final research report."""
    topic: str
    slug: str
    facts: list[ExtractedFact] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    markdown: str = ""
    html_url: str = ""
    metadata: Optional[ReportMetadata] = None


class SSEEvent(BaseModel):
    """Server-sent event for streaming progress."""
    event: str
    data: dict = Field(default_factory=dict)
```

- [ ] **Step 2: Verify models import cleanly**

```bash
cd D:/Projects/search-agent/backend
python -c "from models import ResearchRequest, ResearchReport; print('OK')"
# Expected: OK
```

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/search-agent
git add backend/models.py
git commit -m "feat: add Pydantic data models for research pipeline

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: DuckDuckGo Search + Web Fetch Module

**Files:**
- Create: `D:/Projects/search-agent/backend/search.py`

**Interfaces:**
- Consumes: `config.Config`, `models.SearchResult`
- Produces:
  - `async def search_web(query: str, max_results: int = 10) -> list[SearchResult]`
  - `async def fetch_page(url: str) -> str`

- [ ] **Step 1: Write search.py**

```python
"""Web search and page fetching module."""
import asyncio
from duckduckgo_search import DDGS
import httpx
from markdownify import markdownify as md

from config import config
from models import SearchResult


async def search_web(query: str, max_results: int = None) -> list[SearchResult]:
    """Search the web using DuckDuckGo and return structured results."""
    if max_results is None:
        max_results = config.search_max_results

    loop = asyncio.get_event_loop()
    raw_results = await loop.run_in_executor(
        None,
        lambda: list(DDGS().text(query, max_results=max_results)),
    )

    results = []
    for r in raw_results:
        results.append(SearchResult(
            url=r.get("href", ""),
            title=r.get("title", ""),
            snippet=r.get("body", ""),
        ))
    return results


async def fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a webpage and convert HTML to markdown text."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
            text = md(html, heading_style="ATX", strip=["script", "style", "nav", "footer"])
            # Truncate very long pages to ~8000 chars for LLM context
            if len(text) > 8000:
                text = text[:8000] + "\n\n[... content truncated ...]"
            return text.strip()
        except Exception as e:
            return f"[Failed to fetch {url}: {e}]"


async def search_and_fetch(query: str, max_results: int = None) -> list[SearchResult]:
    """Search and immediately fetch full text for all results."""
    results = await search_web(query, max_results)

    async def fetch_one(result: SearchResult) -> SearchResult:
        result.full_text = await fetch_page(result.url)
        return result

    return await asyncio.gather(*[fetch_one(r) for r in results])
```

- [ ] **Step 2: Write a quick smoke test**

Create `D:/Projects/search-agent/backend/test_search.py`:

```python
"""Quick smoke test for search module."""
import asyncio
from search import search_web, fetch_page


async def main():
    print("Testing search_web...")
    results = await search_web("Python FastAPI tutorial", max_results=3)
    for r in results:
        print(f"  {r.title} — {r.url}")
    print(f"  Got {len(results)} results")

    if results:
        print("\nTesting fetch_page...")
        text = await fetch_page(results[0].url)
        print(f"  Fetched {len(text)} chars from {results[0].url[:60]}...")

    print("\nAll tests passed!")

asyncio.run(main())
```

- [ ] **Step 3: Run smoke test**

```bash
cd D:/Projects/search-agent/backend
python test_search.py
# Expected: prints search results and fetched content length
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/search.py backend/test_search.py
git commit -m "feat: add DuckDuckGo search and web fetch module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: LLM Structured Extraction

**Files:**
- Create: `D:/Projects/search-agent/backend/extraction.py`

**Interfaces:**
- Consumes: `config.Config`, `models.ExtractedFact`, `models.SearchResult`
- Produces:
  - `async def extract_facts(topic: str, sources: list[SearchResult]) -> list[ExtractedFact]`

- [ ] **Step 1: Write extraction.py**

```python
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
```

- [ ] **Step 2: Write smoke test**

Create `D:/Projects/search-agent/backend/test_extraction.py`:

```python
"""Quick smoke test for LLM extraction — requires LLM_API_KEY set."""
import asyncio
import os
from extraction import extract_facts
from models import SearchResult


async def main():
    if not os.getenv("LLM_API_KEY"):
        print("SKIP: LLM_API_KEY not set. Set it to test extraction.")
        return

    sources = [
        SearchResult(
            url="https://example.com/test",
            title="Test Source",
            snippet="Python was created by Guido van Rossum in 1991.",
            full_text="Python is a high-level programming language created by Guido van Rossum and first released in 1991. It emphasizes code readability.",
        )
    ]

    facts = await extract_facts("Python programming language history", sources)
    print(f"Extracted {len(facts)} facts:")
    for f in facts:
        print(f"  [{f.confidence}] {f.fact}")
        print(f"    Source: {f.source_title}")
        print(f"    Quote: {f.quoted_text[:80]}...")

asyncio.run(main())
```

- [ ] **Step 3: Run smoke test (set key first)**

```bash
cd D:/Projects/search-agent/backend
$env:LLM_API_KEY="<your-key>"; $env:LLM_BASE_URL="https://api.openai.com/v1"; $env:LLM_MODEL="gpt-4o-mini"; python test_extraction.py
# Expected: prints extracted facts with confidence ratings
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/extraction.py backend/test_extraction.py
git commit -m "feat: add LLM structured fact extraction module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Result Deduplication

**Files:**
- Create: `D:/Projects/search-agent/backend/dedup.py`

**Interfaces:**
- Consumes: `models.ExtractedFact`
- Produces:
  - `def deduplicate_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]`
  - `def deduplicate_search_results(results: list) -> list`

- [ ] **Step 1: Write dedup.py**

```python
"""Deduplication for search results and extracted facts."""
import re
from urllib.parse import urlparse
from difflib import SequenceMatcher

from models import ExtractedFact


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison: remove scheme, www, trailing slash."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    host = host.removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}{parsed.query}"


def deduplicate_search_results(results: list) -> list:
    """Remove duplicate search results by normalized URL."""
    seen = set()
    unique = []
    for r in results:
        norm = _normalize_url(r.url)
        if norm not in seen:
            seen.add(norm)
            unique.append(r)
    return unique


def _similarity(a: str, b: str) -> float:
    """Compute text similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate_facts(
    facts: list[ExtractedFact],
    similarity_threshold: float = 0.85,
) -> list[ExtractedFact]:
    """Deduplicate extracted facts by URL + semantic similarity.

    Strategy:
    1. If two facts come from the same URL and are very similar, keep the
       one with higher confidence.
    2. If two facts from different URLs say nearly the same thing, keep
       both but mark the duplicate with lower confidence — this IS the
       cross-validation signal we want.
    """
    if len(facts) <= 1:
        return facts

    # First pass: same-URL dedup
    by_url: dict[str, list[ExtractedFact]] = {}
    for f in facts:
        norm = _normalize_url(f.source_url)
        by_url.setdefault(norm, []).append(f)

    same_url_deduped = []
    for url_facts in by_url.values():
        if len(url_facts) == 1:
            same_url_deduped.append(url_facts[0])
        else:
            # Keep all from same URL that are sufficiently different
            kept = [url_facts[0]]
            for f in url_facts[1:]:
                is_dup = any(
                    _similarity(f.fact, k.fact) > similarity_threshold
                    for k in kept
                )
                if not is_dup:
                    kept.append(f)
                # If duplicate, keep the one with higher confidence
                elif f.confidence == "high" and kept[0].confidence != "high":
                    kept = [f] + kept[1:]
            same_url_deduped.extend(kept)

    return same_url_deduped
```

- [ ] **Step 2: Write smoke test**

Create `D:/Projects/search-agent/backend/test_dedup.py`:

```python
"""Smoke test for deduplication."""
from dedup import deduplicate_facts, deduplicate_search_results
from models import ExtractedFact, SearchResult


def test_url_dedup():
    results = [
        SearchResult(url="https://www.example.com/page", title="A", snippet="x"),
        SearchResult(url="https://example.com/page/", title="A", snippet="x"),
        SearchResult(url="https://other.com/page", title="B", snippet="y"),
    ]
    deduped = deduplicate_search_results(results)
    assert len(deduped) == 2, f"Expected 2, got {len(deduped)}"
    print("test_url_dedup: PASS")


def test_fact_dedup():
    facts = [
        ExtractedFact(
            fact="Python was created in 1991",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="created in 1991",
            confidence="high",
        ),
        ExtractedFact(
            fact="Python was created in 1991 by Guido",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="created in 1991 by Guido",
            confidence="medium",
        ),
        ExtractedFact(
            fact="Python emphasizes readability",
            source_url="https://a.com/1",
            source_title="A",
            quoted_text="emphasizes readability",
            confidence="high",
        ),
    ]
    deduped = deduplicate_facts(facts)
    # First two are similar (same URL), third is different
    assert len(deduped) == 2, f"Expected 2, got {len(deduped)}"
    print("test_fact_dedup: PASS")


if __name__ == "__main__":
    test_url_dedup()
    test_fact_dedup()
    print("All dedup tests passed!")
```

- [ ] **Step 3: Run smoke test**

```bash
cd D:/Projects/search-agent/backend
python test_dedup.py
# Expected: All dedup tests passed!
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/dedup.py backend/test_dedup.py
git commit -m "feat: add result deduplication module

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Markdown Report Generation with Citations

**Files:**
- Create: `D:/Projects/search-agent/backend/reporter.py`

**Interfaces:**
- Consumes: `models.ExtractedFact`, `models.Citation`, `models.ResearchReport`, `config.Config`
- Produces:
  - `def generate_report(topic: str, facts: list[ExtractedFact]) -> ResearchReport`

- [ ] **Step 1: Write reporter.py**

```python
"""Report generation: assemble facts into structured Markdown with citations."""
import re
import os
from datetime import datetime, timezone

from models import ExtractedFact, Citation, ResearchReport, ReportMetadata
from config import config


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


def _build_citations(facts: list[ExtractedFact]) -> list[Citation]:
    """Build citation index from extracted facts."""
    citations = []
    for i, fact in enumerate(facts, 1):
        # Extract a highlight anchor: use a short key phrase from the quoted text
        highlight = fact.quoted_text[:100] if fact.quoted_text else fact.fact[:100]
        citations.append(Citation(
            index=i,
            source_name=fact.source_title,
            source_url=fact.source_url,
            quoted_text=fact.quoted_text,
            highlight_anchor=highlight.strip(),
        ))
    return citations


def _generate_markdown(
    topic: str,
    facts: list[ExtractedFact],
    citations: list[Citation],
    started_at: datetime,
    completed_at: datetime,
) -> str:
    """Generate structured Markdown report with citation markers."""

    # Group facts by confidence
    high = [f for f in facts if f.confidence == "high"]
    medium = [f for f in facts if f.confidence == "medium"]
    low = [f for f in facts if f.confidence == "low"]

    lines = [
        f"# Research Report: {topic}",
        "",
        f"*Generated: {completed_at.strftime('%Y-%m-%d %H:%M UTC')}*",
        f"*Sources: {len(facts)} facts from {len(set(f.source_url for f in facts))} unique URLs*",
        "",
        "---",
        "",
        "## Key Findings",
        "",
    ]

    # High confidence first
    if high:
        lines.append("### ✅ High Confidence (multi-source or official data)")
        lines.append("")
        for fact in high:
            idx = facts.index(fact) + 1
            lines.append(f"- {fact.fact} [^{idx}]")
        lines.append("")

    if medium:
        lines.append("### 📋 Medium Confidence")
        lines.append("")
        for fact in medium:
            idx = facts.index(fact) + 1
            lines.append(f"- {fact.fact} [^{idx}]")
        lines.append("")

    if low:
        lines.append("### ⚠️ Low Confidence (single source or implied)")
        lines.append("")
        for fact in low:
            idx = facts.index(fact) + 1
            lines.append(f"- {fact.fact} [^{idx}]")
        lines.append("")

    # Sources section
    lines.extend([
        "---",
        "",
        "## Sources",
        "",
    ])
    for c in citations:
        lines.append(f"[^{c.index}]: [{c.source_name}]({c.source_url}) — *\"{c.quoted_text[:120]}{'...' if len(c.quoted_text) > 120 else ''}\"*")
        lines.append("")

    lines.extend([
        "---",
        "",
        "*This report was generated by Search Agent. Verify important claims against original sources.*",
    ])

    return "\n".join(lines)


def generate_report(
    topic: str,
    facts: list[ExtractedFact],
    started_at: datetime = None,
) -> ResearchReport:
    """Generate a complete ResearchReport from extracted facts."""
    now = datetime.now(timezone.utc)
    if started_at is None:
        started_at = now

    slug = _slugify(topic)
    if not slug:
        slug = f"research-{now.strftime('%Y%m%d-%H%M%S')}"

    citations = _build_citations(facts)
    markdown = _generate_markdown(topic, facts, citations, started_at, now)

    unique_urls = set(f.source_url for f in facts)
    metadata = ReportMetadata(
        execution_time_seconds=(now - started_at).total_seconds(),
        source_count=len(unique_urls),
        topics_searched=[topic],
        started_at=started_at.isoformat(),
        completed_at=now.isoformat(),
    )

    return ResearchReport(
        topic=topic,
        slug=slug,
        facts=facts,
        citations=citations,
        markdown=markdown,
        metadata=metadata,
    )
```

- [ ] **Step 2: Write smoke test**

Create `D:/Projects/search-agent/backend/test_reporter.py`:

```python
"""Smoke test for report generation."""
from models import ExtractedFact
from reporter import generate_report, _slugify


def test_slugify():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("Python: FastAPI & LLMs!") == "python-fastapi-llms"
    print("test_slugify: PASS")


def test_generate_report():
    facts = [
        ExtractedFact(
            fact="Python was created in 1991",
            source_url="https://python.org/history",
            source_title="Python History",
            quoted_text="first released in 1991 by Guido van Rossum",
            confidence="high",
        ),
        ExtractedFact(
            fact="FastAPI is built on Starlette",
            source_url="https://fastapi.tiangolo.com",
            source_title="FastAPI Docs",
            quoted_text="FastAPI is a modern, fast web framework for building APIs with Python",
            confidence="high",
        ),
    ]
    report = generate_report("Python web frameworks", facts)
    assert report.slug == "python-web-frameworks"
    assert len(report.citations) == 2
    assert "[^1]" in report.markdown
    assert "[^2]" in report.markdown
    print("test_generate_report: PASS")
    print(f"\nGenerated Markdown preview:\n{report.markdown[:500]}...")


if __name__ == "__main__":
    test_slugify()
    test_generate_report()
    print("All reporter tests passed!")
```

- [ ] **Step 3: Run smoke test**

```bash
cd D:/Projects/search-agent/backend
python test_reporter.py
# Expected: All reporter tests passed! + Markdown preview
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/reporter.py backend/test_reporter.py
git commit -m "feat: add Markdown report generation with citation index

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Search Agent Orchestration Loop

**Files:**
- Create: `D:/Projects/search-agent/backend/agent.py`

**Interfaces:**
- Consumes: `models.ResearchRequest`, `models.ResearchReport`, `search.search_and_fetch`, `extraction.extract_facts`, `dedup.deduplicate_facts`, `dedup.deduplicate_search_results`, `reporter.generate_report`
- Produces:
  - `async def run_research(request: ResearchRequest, event_callback=None) -> ResearchReport`

- [ ] **Step 1: Write agent.py**

```python
"""Search Agent orchestration: coordinates search → extract → dedup → report."""
import asyncio
from datetime import datetime, timezone

from models import ResearchRequest, ResearchReport
from search import search_and_fetch
from extraction import extract_facts
from dedup import deduplicate_facts, deduplicate_search_results
from reporter import generate_report


async def run_research(
    request: ResearchRequest,
    event_callback=None,
) -> ResearchReport:
    """Execute the complete research pipeline.

    Args:
        request: The research topic and parameters.
        event_callback: Optional async callback(event_type, data) for SSE streaming.

    Returns:
        ResearchReport with facts, citations, and markdown.
    """
    started_at = datetime.now(timezone.utc)

    async def emit(event_type: str, data: dict):
        if event_callback:
            await event_callback(event_type, data)

    await emit("search_start", {"topic": request.topic, "max_sources": request.max_sources})

    # Phase 1: Search
    raw_results = await search_and_fetch(request.topic, request.max_sources)
    await emit("search_complete", {"results_found": len(raw_results)})

    # Dedup search results
    unique_results = deduplicate_search_results(raw_results)
    await emit("dedup_complete", {
        "before": len(raw_results),
        "after": len(unique_results),
        "removed": len(raw_results) - len(unique_results),
    })

    # Phase 2: Extract facts
    successful_fetches = [r for r in unique_results if r.full_text and not r.full_text.startswith("[Failed")]
    await emit("extraction_start", {"sources_with_content": len(successful_fetches)})

    facts = await extract_facts(request.topic, successful_fetches)
    await emit("extraction_complete", {"facts_extracted": len(facts)})

    # Phase 3: Dedup facts
    unique_facts = deduplicate_facts(facts)
    await emit("fact_dedup_complete", {
        "before": len(facts),
        "after": len(unique_facts),
    })

    # Phase 4: Generate report
    await emit("report_start", {"fact_count": len(unique_facts)})
    report = generate_report(request.topic, unique_facts, started_at)
    await emit("report_complete", {
        "slug": report.slug,
        "citation_count": len(report.citations),
    })

    return report
```

- [ ] **Step 2: Write smoke test**

Create `D:/Projects/search-agent/backend/test_agent.py`:

```python
"""Integration test for the full research pipeline — requires LLM_API_KEY."""
import asyncio
import os
from agent import run_research
from models import ResearchRequest


async def main():
    if not os.getenv("LLM_API_KEY"):
        print("SKIP: LLM_API_KEY not set.")
        return

    events = []

    async def capture(event_type: str, data: dict):
        events.append((event_type, data))
        print(f"  [{event_type}] {data}")

    print("Running research on: 'FastAPI vs Flask comparison'")
    report = await run_research(
        ResearchRequest(topic="FastAPI vs Flask comparison", max_sources=5),
        event_callback=capture,
    )

    print(f"\nReport: {report.slug}")
    print(f"Facts: {len(report.facts)}")
    print(f"Citations: {len(report.citations)}")
    print(f"Events: {len(events)}")
    print(f"Markdown preview:\n{report.markdown[:400]}...")

asyncio.run(main())
```

- [ ] **Step 3: Run smoke test**

```bash
cd D:/Projects/search-agent/backend
$env:LLM_API_KEY="<your-key>"; python test_agent.py
# Expected: full pipeline runs, prints report slug, facts, citations, events
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/agent.py backend/test_agent.py
git commit -m "feat: add search agent orchestration loop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: SSE Streaming + FastAPI Endpoints

**Files:**
- Modify: `D:/Projects/search-agent/backend/main.py`

**Interfaces:**
- Consumes: `agent.run_research`, `models.ResearchRequest`, `models.ResearchReport`
- Produces:
  - `POST /api/research` — synchronous research endpoint (returns JSON)
  - `POST /api/research/stream` — SSE streaming research endpoint
  - `GET /api/research/{slug}` — retrieve a completed report

- [ ] **Step 1: Rewrite main.py with full endpoints**

```python
"""Search Agent — FastAPI backend with SSE streaming."""
import json
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import config
from models import ResearchRequest, ResearchReport
from agent import run_research

app = FastAPI(title="Search Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://yiwang.dev"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory report store (Phase 1: no database)
_reports: dict[str, ResearchReport] = {}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/research", response_model=ResearchReport)
async def research_sync(request: ResearchRequest):
    """Run research synchronously and return the complete report."""
    report = await run_research(request)
    _reports[report.slug] = report
    return report


class StreamRequest(BaseModel):
    topic: str
    max_sources: int = 10


@app.post("/api/research/stream")
async def research_stream(request: StreamRequest):
    """Run research with SSE streaming progress."""
    queue = asyncio.Queue()

    async def event_callback(event_type: str, data: dict):
        await queue.put({"event": event_type, "data": data})

    async def event_generator():
        # Run research in background task
        task = asyncio.create_task(
            run_research(
                ResearchRequest(topic=request.topic, max_sources=request.max_sources),
                event_callback=event_callback,
            )
        )

        # Stream events as they come
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    break

        # Get final report and send as last event
        try:
            report = await task
            _reports[report.slug] = report

            # Send the report data as the final event
            final_event = {
                "event": "report_ready",
                "data": {
                    "slug": report.slug,
                    "topic": report.topic,
                    "fact_count": len(report.facts),
                    "citation_count": len(report.citations),
                },
            }
            yield f"data: {json.dumps(final_event)}\n\n"

            # Send the full markdown
            yield f"data: {json.dumps({'event': 'report_content', 'data': {'markdown': report.markdown}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/research/{slug}", response_model=ResearchReport)
async def get_report(slug: str):
    """Retrieve a previously generated report by slug."""
    if slug not in _reports:
        raise HTTPException(status_code=404, detail="Report not found")
    return _reports[slug]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 2: Create a .env file**

Create `D:/Projects/search-agent/backend/.env`:

```
LLM_API_KEY=your-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

- [ ] **Step 3: Test the sync endpoint**

```bash
# Start backend
cd D:/Projects/search-agent/backend
python main.py

# In another terminal:
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "Python async programming", "max_sources": 3}'
# Expected: JSON report with facts, citations, markdown
```

- [ ] **Step 4: Test the SSE streaming endpoint**

```bash
curl -N -X POST http://localhost:8000/api/research/stream \
  -H "Content-Type: application/json" \
  -d '{"topic": "FastAPI vs Flask", "max_sources": 3}'
# Expected: SSE event stream with search_start, extraction_complete, report_ready, report_content
```

- [ ] **Step 5: Commit**

```bash
cd D:/Projects/search-agent
git add backend/main.py backend/.env
echo ".env" >> backend/.gitignore
git add backend/.gitignore
git commit -m "feat: add SSE streaming and REST API endpoints

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Next.js Frontend — Search Page

**Files:**
- Modify: `D:/Projects/search-agent/frontend/app/page.tsx`
- Modify: `D:/Projects/search-agent/frontend/app/layout.tsx`
- Create: `D:/Projects/search-agent/frontend/app/globals.css` (Tailwind setup)
- Create: `D:/Projects/search-agent/frontend/lib/api.ts`

**Interfaces:**
- Consumes: FastAPI backend on `http://localhost:8000`
- Produces: Search input UI with mode toggle (quick/deep, deep disabled for Phase 1), SSE progress display

- [ ] **Step 1: Write API client lib**

```typescript
// D:/Projects/search-agent/frontend/lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface ResearchRequest {
  topic: string;
  max_sources?: number;
}

export interface Citation {
  index: number;
  source_name: string;
  source_url: string;
  quoted_text: string;
  highlight_anchor: string;
}

export interface ExtractedFact {
  fact: string;
  source_url: string;
  source_title: string;
  quoted_text: string;
  confidence: "high" | "medium" | "low";
}

export interface ResearchReport {
  topic: string;
  slug: string;
  facts: ExtractedFact[];
  citations: Citation[];
  markdown: string;
  html_url: string;
  metadata?: {
    execution_time_seconds: number;
    source_count: number;
  };
}

export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

export async function* streamResearch(
  request: ResearchRequest
): AsyncGenerator<SSEEvent> {
  const response = await fetch(`${API_BASE}/api/research/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Research failed: ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ") && line !== "data: [DONE]") {
        try {
          const event: SSEEvent = JSON.parse(line.slice(6));
          yield event;
        } catch {
          // skip parse errors
        }
      }
    }
  }
}

export async function getReport(slug: string): Promise<ResearchReport> {
  const response = await fetch(`${API_BASE}/api/research/${slug}`);
  if (!response.ok) {
    throw new Error(`Report not found: ${slug}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Write layout.tsx**

```tsx
// D:/Projects/search-agent/frontend/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Search Agent",
  description: "Controllable, verifiable deep research agent",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased">
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Write globals.css**

```css
/* D:/Projects/search-agent/frontend/app/globals.css */
@import "tailwindcss";

body {
  font-family: system-ui, -apple-system, sans-serif;
}
```

- [ ] **Step 4: Write the search page**

```tsx
// D:/Projects/search-agent/frontend/app/page.tsx
"use client";

import { useState } from "react";
import { streamResearch, type SSEEvent } from "@/lib/api";

type Mode = "quick" | "deep";

export default function SearchPage() {
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<Mode>("quick");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<{
    slug: string;
    markdown: string;
    fact_count: number;
  } | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    setLoading(true);
    setProgress([]);
    setResult(null);

    const events: SSEEvent[] = [];
    try {
      for await (const event of streamResearch({
        topic: topic.trim(),
        max_sources: 10,
      })) {
        events.push(event);
        const label = EVENT_LABELS[event.event] || event.event;
        setProgress((prev) => [...prev, `${label}: ${JSON.stringify(event.data)}`]);

        if (event.event === "report_ready" && event.data) {
          // Don't set result yet, wait for report_content
        }
        if (event.event === "report_content" && event.data) {
          const data = event.data as { markdown: string };
          const readyEvent = events.find((e) => e.event === "report_ready");
          const readyData = (readyEvent?.data || {}) as {
            slug: string;
            fact_count: number;
          };
          setResult({
            slug: readyData.slug || "unknown",
            markdown: data.markdown || "",
            fact_count: readyData.fact_count || 0,
          });
        }
      }
    } catch (err) {
      setProgress((prev) => [
        ...prev,
        `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-20">
      <h1 className="mb-2 text-center text-3xl font-bold tracking-tight">
        🔍 Search Agent
      </h1>
      <p className="mb-8 text-center text-zinc-400">
        Controllable, verifiable deep research — you keep thinking, we execute.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="What do you want to research?"
          className="w-full rounded-xl border border-zinc-700 bg-zinc-900 px-5 py-4 text-lg
                     placeholder:text-zinc-500 focus:border-zinc-500 focus:outline-none"
          disabled={loading}
        />

        <div className="flex items-center justify-center gap-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="mode"
              value="quick"
              checked={mode === "quick"}
              onChange={() => setMode("quick")}
              className="accent-zinc-400"
            />
            <span>⚡ Quick Search</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer opacity-50">
            <input
              type="radio"
              name="mode"
              value="deep"
              disabled
              className="accent-zinc-400"
            />
            <span>🧠 Deep Planning (Phase 2)</span>
          </label>
        </div>

        <div className="text-center">
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="rounded-xl bg-zinc-100 px-8 py-3 font-semibold text-zinc-900
                       hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed
                       transition-colors"
          >
            {loading ? "Researching..." : "Start Research"}
          </button>
        </div>
      </form>

      {progress.length > 0 && (
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <h2 className="mb-2 font-semibold text-zinc-300">Progress</h2>
          <div className="max-h-48 overflow-y-auto space-y-1 text-sm text-zinc-500">
            {progress.map((p, i) => (
              <div key={i}>{p}</div>
            ))}
          </div>
        </div>
      )}

      {result && (
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">Research Complete</h2>
            <span className="text-sm text-zinc-500">
              {result.fact_count} facts ·{" "}
              <a
                href={`/research/${result.slug}`}
                className="text-blue-400 hover:underline"
              >
                View report →
              </a>
            </span>
          </div>
          <div className="prose prose-invert prose-zinc max-w-none">
            <pre className="whitespace-pre-wrap text-sm text-zinc-400 font-mono">
              {result.markdown.slice(0, 2000)}
              {result.markdown.length > 2000 && "\n\n... (truncated preview)"}
            </pre>
          </div>
        </div>
      )}
    </main>
  );
}

const EVENT_LABELS: Record<string, string> = {
  search_start: "🔍 Searching",
  search_complete: "✅ Search done",
  dedup_complete: "🔄 Deduplication",
  extraction_start: "🧠 Extracting facts",
  extraction_complete: "✅ Extraction done",
  fact_dedup_complete: "🔄 Fact dedup",
  report_start: "📝 Generating report",
  report_complete: "✅ Report ready",
  report_ready: "📄 Report ready",
  report_content: "📄 Report content",
};
```

- [ ] **Step 5: Test frontend**

```bash
cd D:/Projects/search-agent/frontend
pnpm dev
# Open http://localhost:3000
# Enter a topic, click "Start Research"
# Expected: progress events appear, then report preview
```

- [ ] **Step 6: Commit**

```bash
cd D:/Projects/search-agent
git add frontend/lib/api.ts frontend/app/layout.tsx frontend/app/globals.css frontend/app/page.tsx
git commit -m "feat: add search page with SSE streaming progress

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Next.js Frontend — Report Page

**Files:**
- Create: `D:/Projects/search-agent/frontend/app/research/[slug]/page.tsx`

**Interfaces:**
- Consumes: FastAPI `GET /api/research/{slug}`
- Produces: Full report display with citation verification (click [ⁿ] to see source details)

- [ ] **Step 1: Write report page**

```tsx
// D:/Projects/search-agent/frontend/app/research/[slug]/page.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getReport, type ResearchReport, type Citation } from "@/lib/api";

export default function ReportPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    getReport(slug)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [slug]);

  const renderMarkdown = useCallback((markdown: string) => {
    // Convert footnote-style citations [^1] to clickable links
    let html = markdown
      // Convert citation markers [^1] to clickable spans
      .replace(
        /\[\^(\d+)\]/g,
        (_, num) =>
          `<sup><span class="citation-link" data-index="${num}" style="cursor:pointer;color:#60a5fa;font-weight:600;">[${num}]</span></sup>`
      )
      // Convert markdown headers
      .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-6 mb-2">$1</h3>')
      .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold mt-8 mb-3">$1</h2>')
      .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>')
      // Convert markdown links
      .replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener" class="text-blue-400 hover:underline">$1</a>'
      )
      // Convert bold
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // Convert italic
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      // Convert list items
      .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
      // Convert paragraphs (double newlines)
      .replace(/\n\n/g, "</p><p class='my-2'>")
      // Convert single newlines
      .replace(/\n/g, "<br/>")
      // Convert horizontal rules
      .replace(/^---$/gm, '<hr class="my-6 border-zinc-700"/>');

    html = `<p class='my-2'>${html}</p>`;
    return html;
  }, []);

  // Handle citation clicks
  useEffect(() => {
    if (!report) return;

    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains("citation-link")) {
        const index = parseInt(target.dataset.index || "0", 10);
        const citation = report.citations.find((c) => c.index === index);
        if (citation) {
          setActiveCitation(citation);
        }
      }
    };

    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [report]);

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-20 text-center text-zinc-400">
        Loading report...
      </main>
    );
  }

  if (error || !report) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-20 text-center text-red-400">
        {error || "Report not found"}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-12">
      <div className="flex gap-8">
        {/* Report content */}
        <article className="flex-1 min-w-0">
          <a href="/" className="text-sm text-zinc-500 hover:text-zinc-300 mb-4 inline-block">
            ← New search
          </a>

          {/* Trust signals */}
          {report.metadata && (
            <div className="mb-8 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-sm text-zinc-500 space-y-1">
              <div>⏱ {(report.metadata.execution_time_seconds).toFixed(1)}s · 🔗 {report.metadata.source_count} sources</div>
            </div>
          )}

          <div
            className="prose prose-invert prose-zinc max-w-none"
            dangerouslySetInnerHTML={{
              __html: renderMarkdown(report.markdown),
            }}
          />
        </article>

        {/* Citation sidebar */}
        {activeCitation && (
          <aside className="w-96 flex-shrink-0 sticky top-4 self-start">
            <div className="rounded-xl border border-zinc-700 bg-zinc-900 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">
                  📎 [{activeCitation.index}] {activeCitation.source_name}
                </h3>
                <button
                  onClick={() => setActiveCitation(null)}
                  className="text-zinc-500 hover:text-zinc-300"
                >
                  ✕
                </button>
              </div>
              <blockquote className="border-l-2 border-zinc-600 pl-3 text-sm text-zinc-400 italic mb-3">
                &ldquo;{activeCitation.quoted_text}&rdquo;
              </blockquote>
              <a
                href={activeCitation.source_url}
                target="_blank"
                rel="noopener"
                className="text-sm text-blue-400 hover:underline"
              >
                Open source in new tab →
              </a>
            </div>
          </aside>
        )}
      </div>

      {/* Source list at bottom */}
      <section className="mt-12 border-t border-zinc-800 pt-8">
        <h2 className="text-lg font-semibold mb-4">📚 Sources</h2>
        <ol className="space-y-2 text-sm text-zinc-400">
          {report.citations.map((c) => (
            <li key={c.index} id={`source-${c.index}`}>
              <span className="text-blue-400 font-semibold">[{c.index}]</span>{" "}
              <a
                href={c.source_url}
                target="_blank"
                rel="noopener"
                className="text-zinc-300 hover:underline"
              >
                {c.source_name}
              </a>
              <span className="text-zinc-600">
                {" "}— &ldquo;{c.quoted_text.slice(0, 150)}
                {c.quoted_text.length > 150 ? "..." : ""}&rdquo;
              </span>
            </li>
          ))}
        </ol>
      </section>

      {/* Show hint when no citation selected */}
      {!activeCitation && (
        <div className="fixed bottom-4 right-4 text-xs text-zinc-600 bg-zinc-900 px-3 py-2 rounded-lg border border-zinc-800">
          Click [ⁿ] citations to verify sources
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Test report page**

```bash
cd D:/Projects/search-agent/frontend
pnpm dev
# 1. Go to http://localhost:3000
# 2. Run a search (topic: "Python async programming")
# 3. Click "View report →"
# 4. Verify: report renders, click [¹] to see source sidebar
```

- [ ] **Step 3: Commit**

```bash
cd D:/Projects/search-agent
git add frontend/app/research/
git commit -m "feat: add report page with citation verification sidebar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: HTML Deployment Pipeline

**Files:**
- Create: `D:/Projects/search-agent/backend/deploy.py`

**Interfaces:**
- Consumes: `models.ResearchReport`, `config.Config`
- Produces:
  - `async def deploy_report(report: ResearchReport) -> str` — returns deployed URL

- [ ] **Step 1: Write deploy.py**

```python
"""Deploy research report as static HTML to the reports directory."""
import os
import json
from pathlib import Path
from datetime import datetime

from models import ResearchReport
from config import config


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Search Agent</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #09090b;
    color: #f4f4f5;
    line-height: 1.7;
  }}
  .container {{ max-width: 800px; margin: 0 auto; padding: 3rem 1.5rem; }}
  h1 {{ font-size: 2rem; font-weight: 700; margin-bottom: 0.75rem; }}
  h2 {{ font-size: 1.4rem; font-weight: 600; margin-top: 2.5rem; margin-bottom: 0.75rem; }}
  h3 {{ font-size: 1.1rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem; }}
  p {{ margin: 0.75rem 0; }}
  .meta {{ color: #71717a; font-size: 0.875rem; margin-bottom: 2rem; }}
  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  sup a {{ font-weight: 600; }}
  hr {{ border: none; border-top: 1px solid #27272a; margin: 2rem 0; }}
  ul {{ padding-left: 1.5rem; }}
  li {{ margin: 0.3rem 0; }}
  blockquote {{
    border-left: 3px solid #3f3f46;
    padding-left: 1rem;
    color: #a1a1aa;
    font-style: italic;
    margin: 1rem 0;
  }}
  strong {{ color: #e4e4e7; }}
  .sources {{ margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #27272a; }}
  .sources ol {{ padding-left: 1.2rem; font-size: 0.875rem; color: #a1a1aa; }}
  .sources li {{ margin: 0.5rem 0; }}
  .back-link {{ display: inline-block; margin-bottom: 2rem; font-size: 0.875rem; color: #71717a; }}
  .trust-signals {{
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 0.5rem;
    padding: 1rem 1.25rem;
    margin-bottom: 2rem;
    font-size: 0.875rem;
    color: #a1a1aa;
  }}
</style>
</head>
<body>
<div class="container">
  <a href="/" class="back-link">← Search Agent</a>
  <h1>{title}</h1>
  <div class="trust-signals">
    ⏱ {execution_time}s · 🔗 {source_count} sources · 📅 {date}
  </div>
  {body}
  <div class="sources">
    <h2>📚 Sources</h2>
    <ol>
      {sources}
    </ol>
  </div>
</div>
</body>
</html>"""


def _markdown_to_html(md: str) -> str:
    """Convert report markdown to HTML."""
    import re

    html = md

    # Citation markers: [^1] → clickable superscript
    html = re.sub(
        r"\[\^(\d+)\](?!:)",
        r'<sup><a href="#source-\1" id="cite-\1">[\1]</a></sup>',
        html,
    )

    # Source footnotes: [^1]: text → anchor + remove
    html = re.sub(
        r"\[\^(\d+)\]: (.+)",
        r'',
        html,
    )

    # Headers
    html = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Inline links
    html = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        html,
    )

    # Horizontal rules
    html = re.sub(r"^---$", r"<hr>", html, flags=re.MULTILINE)

    # List items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)

    # Paragraphs: double newline
    html = re.sub(r"\n\n", r"</p><p>", html)
    html = re.sub(r"\n", r"<br>", html)
    html = f"<p>{html}</p>"

    return html


def _build_sources_html(citations: list) -> str:
    """Build the sources list HTML from citations."""
    items = []
    for c in citations:
        items.append(
            f'<li id="source-{c.index}">'
            f'<strong>[{c.index}]</strong> '
            f'<a href="{c.source_url}" target="_blank" rel="noopener">{c.source_name}</a>'
            f' — &ldquo;{c.quoted_text[:200]}{"..." if len(c.quoted_text) > 200 else ""}&rdquo;'
            f' <a href="#cite-{c.index}" style="font-size:0.75rem;color:#71717a;">↑ back</a>'
            f'</li>'
        )
    return "\n".join(items)


async def deploy_report(report: ResearchReport) -> str:
    """Generate a static HTML file for the report and return its relative URL."""
    output_dir = Path(config.report_output_dir)
    report_dir = output_dir / report.slug
    report_dir.mkdir(parents=True, exist_ok=True)

    body_html = _markdown_to_html(report.markdown)
    sources_html = _build_sources_html(report.citations)

    metadata = report.metadata
    exec_time = f"{metadata.execution_time_seconds:.1f}" if metadata else "?"
    source_count = metadata.source_count if metadata else len(report.citations)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    html = HTML_TEMPLATE.format(
        title=report.topic,
        execution_time=exec_time,
        source_count=source_count,
        date=date_str,
        body=body_html,
        sources=sources_html,
    )

    index_path = report_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # Save JSON data alongside for programmatic access
    json_path = report_dir / "data.json"
    json_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return f"/research/{report.slug}/"
```

- [ ] **Step 2: Add deploy call to main.py**

Add to the end of `research_sync` and `research_stream` functions in `D:/Projects/search-agent/backend/main.py`, after `_reports[report.slug] = report`:

```python
from deploy import deploy_report

# In research_sync, before return:
html_url = await deploy_report(report)
report.html_url = html_url

# In research_stream, after task completes:
html_url = await deploy_report(report)
report.html_url = html_url
```

Also add `html_url` to the final SSE event data.

- [ ] **Step 3: Test deployment**

```bash
cd D:/Projects/search-agent/backend
# Run a research request
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "quantum computing basics", "max_sources": 3}'

# Check that reports/<slug>/index.html was created
ls ../reports/
# Expected: a directory with index.html and data.json
```

- [ ] **Step 4: Commit**

```bash
cd D:/Projects/search-agent
git add backend/deploy.py backend/main.py
git commit -m "feat: add static HTML report deployment pipeline

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: End-to-End Integration & README

**Files:**
- Create: `D:/Projects/search-agent/backend/.env.example`
- Create: `D:/Projects/search-agent/README.md`

**Interfaces:**
- Produces: Working end-to-end pipeline, tested manually

- [ ] **Step 1: Create .env.example**

```
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

- [ ] **Step 2: Write README.md**

````markdown
# Search Agent

> **"Not faster search — verified, structured, traceable answers."**

A controllable deep research agent. You design the research plan, the agent executes it. Every claim is cited with a verifiable source.

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- pnpm

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your LLM API key
pip install -r requirements.txt
python main.py
# → http://localhost:8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
# → http://localhost:3000
```

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/research` | POST | Run research (sync) |
| `/api/research/stream` | POST | Run research (SSE stream) |
| `/api/research/{slug}` | GET | Get a completed report |

## Architecture

```
Next.js Frontend (port 3000)  ←→  FastAPI Backend (port 8000)
                                         │
                                   ┌─────┴─────┐
                                   │  Agent Loop │
                                   ├─────────────┤
                                   │ Search      │ → DuckDuckGo
                                   │ Extract     │ → LLM (OpenAI-compatible)
                                   │ Dedup       │ → URL + Similarity
                                   │ Report      │ → Markdown + HTML
                                   └─────────────┘
```

## Phase

Currently **Phase 1 (MVP)**: Quick search mode, single-user, DuckDuckGo + LLM extraction.

See `product-description.md` for the full product vision and roadmap.
````

- [ ] **Step 3: Full end-to-end manual test**

```bash
# Terminal 1: Backend
cd D:/Projects/search-agent/backend
python main.py

# Terminal 2: Frontend
cd D:/Projects/search-agent/frontend
pnpm dev

# Browser: http://localhost:3000
# 1. Enter topic: "History of the Python programming language"
# 2. Click "Start Research"
# 3. Watch progress events stream in
# 4. Click "View report →"
# 5. Verify: report renders, click [¹] to see source sidebar with quoted text
# 6. Check D:/Projects/search-agent/reports/<slug>/index.html exists
```

- [ ] **Step 4: Final commit**

```bash
cd D:/Projects/search-agent
git add backend/.env.example README.md
git commit -m "docs: add README and .env.example, finalize Phase 1 MVP

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Summary

**12 tasks, ~60 steps.** Each task is independently testable and commit-worthy.

| Task | Component | Deliverable |
|------|-----------|-------------|
| 1 | Scaffolding | Running FastAPI + Next.js |
| 2 | Data models | Pydantic schemas |
| 3 | Search | DuckDuckGo search + web fetch |
| 4 | Extraction | LLM fact extraction |
| 5 | Dedup | URL + similarity dedup |
| 6 | Reporter | Markdown with [ⁿ] citations |
| 7 | Agent loop | End-to-end orchestration |
| 8 | API | REST + SSE endpoints |
| 9 | Search UI | Input + progress display |
| 10 | Report UI | Citation verification sidebar |
| 11 | Deploy | Static HTML generation |
| 12 | Polish | README, .env.example, E2E test |

**What's NOT in Phase 1 (deferred to Phase 2+):**
- Meta layer (5-step planning wizard)
- Multi-hop search
- Browser-Use / Playwright anti-bot
- Cross-validation / confidence scoring (beyond basic LLM self-rating)
- Information source preset library
- Personal knowledge base integration
- User authentication
- Database persistence
- PDF export
- Vercel auto-deploy (currently manual git push)
