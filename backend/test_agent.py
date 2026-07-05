"""Integration test for the full research pipeline -- requires LLM_API_KEY."""
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
