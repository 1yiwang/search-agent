# Search Agent — Deployment

Production layout: **Next.js on Vercel** + **FastAPI on Render/Railway** (or any Docker host).

## 1. Backend (API)

### Option A: Render (recommended)

1. Push repo to GitHub.
2. [Render Dashboard](https://dashboard.render.com) → New → Blueprint → connect repo.
3. Use root `render.yaml` (builds `backend/Dockerfile`).
4. Set secrets in Render: `LLM_API_KEY`, `TAVILY_API_KEY`, optional `JINA_API_KEY`.
5. Set `CORS_ORIGINS` to your Vercel URL(s), e.g.  
   `https://search-agent.vercel.app,https://yiwang.dev`
6. Note the public URL, e.g. `https://search-agent-api.onrender.com`.

### Option B: Docker locally / any host

```bash
cd backend
docker build -t search-agent-api .
docker run -p 8000:8000 --env-file .env -v search-reports:/data/reports search-agent-api
```

Health check: `GET /api/health`

## 2. Frontend (Vercel)

1. [Vercel](https://vercel.com) → Import GitHub repo `1yiwang/search-agent`.
2. **Root Directory**: `frontend`
3. Framework: Next.js (auto-detected)
4. Environment variables:

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_API_URL` | `https://search-agent-api.onrender.com` | **Required for production SSE** (long research streams) |
| `API_URL` | same as above | Fallback for short requests via rewrite |

5. Deploy.

Custom domain (optional): `yiwang.dev` → Vercel project settings.

### Why `NEXT_PUBLIC_API_URL`?

Research SSE can run 3–10 minutes. Calling the backend **directly** avoids Vercel rewrite timeouts. CORS is configured on the backend (`CORS_ORIGINS` + `*.vercel.app`).

## 3. Verify production

```bash
curl https://YOUR-API/api/health
# -> {"status":"ok"}

# Open https://YOUR-VERCEL-APP
# Quick search -> progress stream -> report page
# /plan -> meta wizard
```

## 4. Reports & static HTML

- API persists `reports/<slug>/data.json` and `events.jsonl` on backend disk (Render persistent disk in `render.yaml`).
- Next.js report UI loads via `GET /api/research/{slug}`.
- Static `index.html` is generated at `/research/{slug}/` on the **API host** only; the primary UX is the Next.js `/research/[slug]` page.

## 5. Local development (unchanged)

```bash
# Terminal 1
cd backend && .venv/Scripts/python.exe main.py

# Terminal 2
cd frontend && pnpm dev
```

No `NEXT_PUBLIC_API_URL` needed locally — `next.config.ts` rewrites `/api/*` → `localhost:8000`.

## Environment reference

| Service | Key variables |
|---------|----------------|
| Backend | `LLM_*`, `TAVILY_API_KEY`, `JINA_API_KEY`, `CORS_ORIGINS`, `REPORT_OUTPUT_DIR` |
| Frontend | `NEXT_PUBLIC_API_URL`, `API_URL` |

See `backend/.env.example` and `frontend/.env.example`.
