"""Search Agent — FastAPI backend with SSE streaming."""
import json
import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import config
from models import ResearchRequest, ResearchReport
from agent import run_research
from deploy import deploy_report
from report_store import load_report

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


@app.post("/api/research", response_model=ResearchReport)
async def research_sync(request: ResearchRequest):
    """Run research synchronously and return the complete report."""
    report = await run_research(request)
    await deploy_report(report)
    return report


class StreamRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    max_sources: int = Field(default=10, ge=3, le=30)


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
            html_url = await deploy_report(report)

            # Send the report data as the final event
            final_event = {
                "event": "report_ready",
                "data": {
                    "slug": report.slug,
                    "topic": report.topic,
                    "html_url": html_url,
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
    report = load_report(slug)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
