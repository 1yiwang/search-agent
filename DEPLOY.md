# Search Agent — Deployment

Production layout: **Next.js on Vercel** + **FastAPI on Render** (or Docker).

## Live URLs (2026-07-05)

| Service | URL | Status |
|---------|-----|--------|
| **Frontend (Vercel)** | https://search-agent-seven.vercel.app | Deployed |
| **Vercel Dashboard** | https://vercel.com/yiwangmax-6207s-projects/search-agent | Connected |
| **GitHub** | https://github.com/1yiwang/search-agent | Source |
| **API (temp)** | localtunnel → your machine Docker | Dev only — **replace with Render** |

> **Important:** Production Vercel env currently points to a temporary tunnel for smoke testing. Deploy the API on Render (button below), then update `NEXT_PUBLIC_API_URL` to the Render URL.

## Quick deploy backend (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/1yiwang/search-agent)

After deploy:

1. In Render dashboard, set secrets: `LLM_API_KEY`, `TAVILY_API_KEY`, optional `JINA_API_KEY`
2. Set `CORS_ORIGINS` to:
   ```
   https://search-agent-seven.vercel.app,https://yiwang.dev,http://localhost:3000
   ```
3. Copy the Render service URL (e.g. `https://search-agent-api.onrender.com`)
4. In [Vercel env settings](https://vercel.com/yiwangmax-6207s-projects/search-agent/settings/environment-variables), set:
   - `NEXT_PUBLIC_API_URL` = your Render API URL
   - `API_URL` = same
5. Redeploy frontend: `cd frontend && vercel deploy --prod`

## 1. Backend (API)

### Option A: Render (recommended)

Uses root [`render.yaml`](render.yaml) → builds [`backend/Dockerfile`](backend/Dockerfile).

### Option B: Docker locally

```bash
cd backend
docker build -t search-agent-api .
docker run -p 8000:8000 --env-file .env \
  -e CORS_ORIGINS=https://search-agent-seven.vercel.app,http://localhost:3000 \
  -v search-agent-reports:/data/reports search-agent-api
```

Health check: `GET /api/health` → `{"status":"ok"}`

### Option C: GHCR image (after CI push)

```bash
docker pull ghcr.io/1yiwang/search-agent-api:latest
```

Image is built automatically on push to `master` via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## 2. Frontend (Vercel)

Already deployed. To redeploy from CLI:

```bash
cd frontend
vercel link          # project: search-agent
vercel deploy --prod
```

**Root Directory** (if re-importing): `frontend`

| Variable | Production value |
|----------|------------------|
| `NEXT_PUBLIC_API_URL` | `https://YOUR-RENDER-API.onrender.com` |
| `API_URL` | same |

### Why direct `NEXT_PUBLIC_API_URL`?

Research SSE runs 3–10 minutes. Calling the backend directly avoids Vercel rewrite timeouts.

## 3. Verify production

```bash
curl https://YOUR-API.onrender.com/api/health
# -> {"status":"ok"}

# Open https://search-agent-seven.vercel.app
# Quick search / Deep research /plan wizard
```

## 4. Reports & event logs

- API persists `reports/<slug>/data.json` and `events.jsonl` on backend disk (Render persistent disk in `render.yaml`).
- Next.js report UI: `/research/[slug]` via `GET /api/research/{slug}`.
- Event log API: `GET /api/research/{slug}/events`

## 5. Local development

```bash
# Terminal 1
cd backend && .venv/Scripts/python.exe main.py

# Terminal 2
cd frontend && pnpm dev
```

No `NEXT_PUBLIC_API_URL` needed — `next.config.ts` rewrites `/api/*` → `localhost:8000`.

## Environment reference

| Service | Key variables |
|---------|----------------|
| Backend | `LLM_*`, `TAVILY_API_KEY`, `JINA_API_KEY`, `CORS_ORIGINS`, `REPORT_OUTPUT_DIR` |
| Frontend | `NEXT_PUBLIC_API_URL`, `API_URL` |

See `backend/.env.example`.
