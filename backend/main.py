"""Search Agent — FastAPI backend with SSE streaming."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import config
from models import ResearchRequest, ResearchReport, ResearchPlan
from agent import run_research, run_deep_research
from report_store import load_report
from event_log import load_events
from streaming import stream_research
from planner import create_research_plan
from auth import issue_token, verify_site_password
from middleware_auth import AuthAndKeysMiddleware
from meta import (
    create_session,
    format_human_feedback,
    generate_clarifying_questions,
    get_session,
)

app = FastAPI(title="Search Agent", version="0.1.0")

_cors_origins = [o.strip() for o in config.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://(.*\.)?yiwang\.dev|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthAndKeysMiddleware)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@app.get("/api/health")
async def health():
    return {"status": "ok", "api_auth_required": bool(config.api_auth_secret)}


class AuthLoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=200)


class AuthLoginResponse(BaseModel):
    token: str
    expires_in_seconds: int


@app.post("/api/auth/login", response_model=AuthLoginResponse)
async def auth_login(request: AuthLoginRequest):
    """Exchange site password for API token (used when personal API is running)."""
    if config.site_password and not verify_site_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    if not config.api_auth_secret:
        raise HTTPException(status_code=503, detail="API_AUTH_SECRET not configured on server")
    return AuthLoginResponse(
        token=issue_token(),
        expires_in_seconds=config.api_token_ttl_seconds,
    )


@app.post("/api/research", response_model=ResearchReport)
async def research_sync(request: ResearchRequest):
    """Run research synchronously and return the complete report."""
    from deploy import deploy_report

    report = await run_research(request)
    await deploy_report(report)
    return report


class PlanPreviewRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    max_sections: int = Field(default=5, ge=2, le=8)
    initial_sources: int = Field(default=5, ge=3, le=15)


@app.post("/api/plan/preview", response_model=ResearchPlan)
async def plan_preview(request: PlanPreviewRequest):
    """Broad exploration + dimension plan (Wave 2 / Step 20)."""
    return await create_research_plan(
        topic=request.topic,
        max_sections=request.max_sections,
        initial_sources=request.initial_sources,
    )


class DeepStreamRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    max_sections: int = Field(default=5, ge=2, le=8)
    initial_sources: int = Field(default=5, ge=3, le=15)
    sources_per_query: int = Field(default=3, ge=2, le=10)


@app.post("/api/research/deep/stream")
async def research_deep_stream(request: DeepStreamRequest):
    """Plan dimensions then run parallel deep research with SSE."""

    async def run_pipeline(event_callback):
        plan = await create_research_plan(
            topic=request.topic,
            max_sections=request.max_sections,
            initial_sources=request.initial_sources,
        )
        await event_callback("plan_ready", {
            "title": plan.title,
            "dimensions": [d.model_dump() for d in plan.dimensions],
        })
        return await run_deep_research(
            plan,
            sources_per_query=request.sources_per_query,
            event_callback=event_callback,
        )

    return StreamingResponse(
        stream_research(request.topic, "deep", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


class StreamRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    max_sources: int = Field(default=10, ge=3, le=30)


@app.post("/api/research/stream")
async def research_stream(request: StreamRequest):
    """Run research with SSE streaming progress."""

    async def run_pipeline(event_callback):
        return await run_research(
            ResearchRequest(topic=request.topic, max_sources=request.max_sources),
            event_callback=event_callback,
        )

    return StreamingResponse(
        stream_research(request.topic, "quick", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/research/{slug}", response_model=ResearchReport)
async def get_report(slug: str):
    """Retrieve a previously generated report by slug."""
    report = load_report(slug)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/research/{slug}/events")
async def get_report_events(slug: str):
    """Retrieve JSONL event log for a completed research run."""
    events = load_events(slug)
    if events is None:
        raise HTTPException(status_code=404, detail="Event log not found")
    return {"slug": slug, "events": events}


# --- Meta / human-in-the-loop (Step 25) ---


class MetaClarifyRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)


class MetaClarifyResponse(BaseModel):
    session_id: str
    topic: str
    questions: list[dict]


@app.post("/api/meta/clarify", response_model=MetaClarifyResponse)
async def meta_clarify(request: MetaClarifyRequest):
    """Step 1-2: generate clarifying questions and open a meta session."""
    questions = await generate_clarifying_questions(request.topic)
    session = create_session(request.topic, questions)
    return MetaClarifyResponse(
        session_id=session.session_id,
        topic=session.topic,
        questions=session.questions,
    )


class MetaPlanRequest(BaseModel):
    session_id: str
    answers: dict[str, str] = Field(default_factory=dict)
    feedback: str | None = Field(default=None, max_length=2000)
    max_sections: int = Field(default=5, ge=2, le=8)
    initial_sources: int = Field(default=5, ge=3, le=15)


@app.post("/api/meta/plan", response_model=ResearchPlan)
async def meta_plan(request: MetaPlanRequest):
    """Step 3-4: broad research + dimension plan with human answers/feedback."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    session.answers = request.answers
    human_feedback = format_human_feedback(request.answers, session.questions)
    if request.feedback:
        human_feedback = (human_feedback + "\n\nRevision feedback:\n" + request.feedback).strip()

    plan = await create_research_plan(
        topic=session.topic,
        max_sections=request.max_sections,
        initial_sources=request.initial_sources,
        human_feedback=human_feedback or None,
    )
    session.plan = plan
    return plan


class MetaResearchRequest(BaseModel):
    session_id: str
    sources_per_query: int = Field(default=3, ge=2, le=10)


@app.post("/api/meta/research/stream")
async def meta_research_stream(request: MetaResearchRequest):
    """Step 5: execute approved plan with SSE streaming."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.plan is None:
        raise HTTPException(status_code=400, detail="No plan in session; call /api/meta/plan first")

    plan = session.plan

    async def run_pipeline(event_callback):
        await event_callback("plan_ready", {
            "title": plan.title,
            "dimensions": [d.model_dump() for d in plan.dimensions],
            "session_id": session.session_id,
        })
        return await run_deep_research(
            plan,
            sources_per_query=request.sources_per_query,
            event_callback=event_callback,
        )

    return StreamingResponse(
        stream_research(session.topic, "meta", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
