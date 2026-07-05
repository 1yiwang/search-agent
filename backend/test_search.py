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
