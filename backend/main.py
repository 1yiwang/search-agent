"""Search Agent — FastAPI backend with SSE streaming."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import config
from models import ResearchRequest, ResearchReport, ResearchPlan, ResearchBrief
from agent import run_research, run_deep_research
from report_store import load_report, list_reports
from event_log import load_events
from streaming import stream_research
from planner import create_research_plan
from auth import issue_token, verify_site_password
from middleware_auth import AuthAndKeysMiddleware
from meta import (
    create_session,
    format_human_feedback,
    get_session,
)
from brief import (
    generate_industry_clarifying_questions,
    generate_research_brief,
    revise_research_brief,
)
from frameworks import select_framework_id
from watchlist.models import WatchCreate, WatchItem, WatchUpdate
from watchlist.store import (
    create_watch,
    delete_watch,
    get_watch,
    list_watches,
    load_latest_delta,
    update_watch,
)
from watchlist.runner import run_watch_item

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
    depth: str = Field(default="standard", pattern="^(fast|standard|deep)$")
    brief_session_id: str | None = None


@app.post("/api/research/stream")
async def research_stream(request: StreamRequest):
    """Run research with SSE streaming progress."""

    async def run_pipeline(event_callback):
        return await run_research(
            ResearchRequest(
                topic=request.topic,
                max_sources=request.max_sources,
                depth=request.depth,
                brief_session_id=request.brief_session_id,
            ),
            event_callback=event_callback,
        )

    return StreamingResponse(
        stream_research(request.topic, "quick", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/api/reports")
async def reports_list(limit: int = 30):
    """List saved research reports (newest first)."""
    return {"reports": list_reports(limit=min(max(limit, 1), 100))}


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
    questions = await generate_industry_clarifying_questions(request.topic)
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


# --- Brief-first industry research (Wave 12a) ---


class BriefClarifyRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)


class BriefClarifyResponse(BaseModel):
    session_id: str
    topic: str
    questions: list[dict]
    suggested_framework_id: str


@app.post("/api/brief/clarify", response_model=BriefClarifyResponse)
async def brief_clarify(request: BriefClarifyRequest):
    """Industry clarifying questions + session (no web search)."""
    questions = await generate_industry_clarifying_questions(request.topic)
    session = create_session(request.topic, questions)
    return BriefClarifyResponse(
        session_id=session.session_id,
        topic=session.topic,
        questions=session.questions,
        suggested_framework_id=select_framework_id(request.topic),
    )


class BriefGenerateRequest(BaseModel):
    session_id: str
    answers: dict[str, str] = Field(default_factory=dict)
    framework_id: str | None = None


@app.post("/api/brief/generate", response_model=ResearchBrief)
async def brief_generate(request: BriefGenerateRequest):
    """Generate ResearchBrief from framework skeleton + answers (no web search)."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    session.answers = request.answers
    brief = await generate_research_brief(
        session.topic,
        answers=request.answers,
        questions=session.questions,
        framework_id=request.framework_id,
    )
    session.brief = brief
    return brief


class BriefReviseRequest(BaseModel):
    session_id: str
    feedback: str = Field(..., min_length=1, max_length=4000)


@app.post("/api/brief/revise", response_model=ResearchBrief)
async def brief_revise(request: BriefReviseRequest):
    """Revise ResearchBrief from human feedback."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.brief is None:
        raise HTTPException(status_code=400, detail="No brief; call /api/brief/generate first")
    brief = await revise_research_brief(session.brief, request.feedback)
    session.brief = brief
    return brief


class BriefConfirmRequest(BaseModel):
    session_id: str


@app.post("/api/brief/confirm", response_model=ResearchBrief)
async def brief_confirm(request: BriefConfirmRequest):
    """Freeze ResearchBrief for execution."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.brief is None:
        raise HTTPException(status_code=400, detail="No brief; call /api/brief/generate first")
    session.brief.confirmed = True
    return session.brief


class BriefResearchRequest(BaseModel):
    session_id: str
    depth: str = Field(default="standard", pattern="^(fast|standard|deep)$")
    max_sources: int | None = Field(default=None, ge=3, le=30)


@app.post("/api/brief/research/stream")
async def brief_research_stream(request: BriefResearchRequest):
    """Execute confirmed brief via coverage-driven research loop (SSE)."""
    session = get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if session.brief is None or not session.brief.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Brief not confirmed; call /api/brief/confirm first",
        )

    async def run_pipeline(event_callback):
        await event_callback("brief_ready", {
            "framework_id": session.brief.framework_id,
            "dimension_count": len(session.brief.dimensions),
            "session_id": session.session_id,
        })
        return await run_research(
            ResearchRequest(
                topic=session.topic,
                depth=request.depth,
                max_sources=request.max_sources or 10,
                brief_session_id=session.session_id,
            ),
            event_callback=event_callback,
        )

    return StreamingResponse(
        stream_research(session.topic, "brief", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


# --- Watchlist (Phase 3 / Step 41) ---


@app.get("/api/watchlist", response_model=list[WatchItem])
async def watchlist_list():
    return list_watches()


@app.post("/api/watchlist", response_model=WatchItem)
async def watchlist_create(payload: WatchCreate):
    return create_watch(payload)


@app.get("/api/watchlist/{watch_id}", response_model=WatchItem)
async def watchlist_get(watch_id: str):
    item = get_watch(watch_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watch not found")
    return item


@app.patch("/api/watchlist/{watch_id}", response_model=WatchItem)
async def watchlist_patch(watch_id: str, payload: WatchUpdate):
    item = update_watch(watch_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Watch not found")
    return item


@app.delete("/api/watchlist/{watch_id}")
async def watchlist_delete(watch_id: str):
    if not delete_watch(watch_id):
        raise HTTPException(status_code=404, detail="Watch not found")
    return {"ok": True, "id": watch_id}


@app.get("/api/watchlist/{watch_id}/delta/latest")
async def watchlist_latest_delta(watch_id: str):
    if get_watch(watch_id) is None:
        raise HTTPException(status_code=404, detail="Watch not found")
    delta = load_latest_delta(watch_id)
    if delta is None:
        raise HTTPException(status_code=404, detail="No delta yet")
    return delta


@app.post("/api/watchlist/{watch_id}/run/stream")
async def watchlist_run_stream(watch_id: str):
    """Run watch research with SSE (research events + delta_ready)."""
    item = get_watch(watch_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Watch not found")
    if not item.enabled:
        raise HTTPException(status_code=400, detail="Watch is disabled")

    async def run_pipeline(event_callback):
        updated, _delta = await run_watch_item(watch_id, event_callback=event_callback)
        # stream_research expects a ResearchReport; load the latest run report.
        from report_store import load_report

        report = load_report(updated.latest_slug)
        if report is None:
            raise RuntimeError("Watch run completed but report missing")
        return report

    return StreamingResponse(
        stream_research(item.topic, "watch", run_pipeline),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
