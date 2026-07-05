# Search Agent

> **"Not faster search -- verified, structured, traceable answers."**

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
# -> http://localhost:8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
# -> http://localhost:3000
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
Next.js Frontend (port 3000)  <-->  FastAPI Backend (port 8000)
                                         |
                                   +-----+-----+
                                   |  Agent Loop |
                                   +-------------+
                                   | Search      | -> DuckDuckGo
                                   | Extract     | -> LLM (OpenAI-compatible)
                                   | Dedup       | -> URL + Similarity
                                   | Report      | -> Markdown + HTML
                                   +-------------+
```

## Phase

**Phase 1-alpha** complete — see [ROADMAP.md](ROADMAP.md) for Step 13+ progress.

Quick search mode, single-user, DuckDuckGo + LLM extraction. Wave 1 adds Tavily and reliability fixes.

See `product-description.md` for the full product vision.
