"""Shared SSE streaming helpers (Step 24)."""
import asyncio
import json
from collections.abc import Awaitable, Callable

from event_log import EventLog
from deploy import deploy_report
from models import ResearchReport

RunPipeline = Callable[[Callable[[str, dict], Awaitable[None]]], Awaitable[ResearchReport]]


def format_sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


async def stream_research(
    topic: str,
    mode: str,
    run_pipeline: RunPipeline,
):
    """Run a research pipeline with SSE streaming + JSONL event log."""
    queue: asyncio.Queue[dict] = asyncio.Queue()
    log = EventLog(topic=topic, mode=mode)

    async def event_callback(event_type: str, data: dict):
        await queue.put(log.record(event_type, data))

    async def event_generator():
        await queue.put(log.record("session_start", {"topic": topic, "mode": mode}))

        task = asyncio.create_task(run_pipeline(event_callback))

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield format_sse(event)
            except asyncio.TimeoutError:
                if task.done():
                    break

        try:
            report = await task
            log.bind_slug(report.slug)
            html_url = await deploy_report(report)
            log_path = log.flush(report.slug)

            yield format_sse(log.record("report_ready", {
                "slug": report.slug,
                "topic": report.topic,
                "html_url": html_url,
                "fact_count": len(report.facts),
                "citation_count": len(report.citations),
                "events_path": str(log_path) if log_path else None,
            }))
            yield format_sse(log.record("report_content", {"markdown": report.markdown}))
            yield "data: [DONE]\n\n"

        except Exception as exc:
            yield format_sse(log.record("error", {"message": str(exc)}))
            if log._slug:
                log.flush()

    return event_generator()
