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
