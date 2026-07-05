# Search Agent — Deployment Plan

> **Default model (approved):** Mode B — local API on demand, $0, no Render required.  
> Render / GHCR remain **optional** for later.

## Target experience

| What you want | How it works |
|---------------|--------------|
| Open a URL and use the app | `https://search.yiwang.dev` (password) |
| Edit LLM model / API key in the UI | Settings panel; stored in **your browser** (localStorage), personal use |
| LLM actually runs | Only when you run **one terminal command** on your PC |
| Turn off LLM / API | Stop that terminal command (Ctrl+C) — website still opens, research disabled |
| Public showcase | `https://search-demo.yiwang.dev` — static reports, no API |

**Important:** The website is always viewable (with password). Settings are always editable.  
**Research calls fail gracefully** when the local API is not running — no LLM spend, no abuse.

---

## Domains (yiwang.dev)

| Domain | Role | API needed? |
|--------|------|-------------|
| `search-demo.yiwang.dev` | Static demo gallery (2–3 golden cases) | No |
| `search.yiwang.dev` | Full app (search, deep, `/plan`) + settings | Only for research |
| `api.search.yiwang.dev` | Cloudflare Tunnel → your PC `:8000` | Only when script is running |

DNS (one-time):

- `search-demo` → Vercel (CNAME)
- `search` → Vercel (CNAME)
- `api.search` → Cloudflare Tunnel (created when you set up tunnel)

Vercel env (production):

```
NEXT_PUBLIC_API_URL=https://api.search.yiwang.dev
SITE_PASSWORD=<your site password>          # server-side only
API_AUTH_SECRET=<same random string as backend .env>
API_TOKEN_TTL_SECONDS=86400                 # optional
```

Remove any temporary `localtunnel` URLs from Vercel env.

### Cloudflare named tunnel (one-time)

1. Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. `cloudflared tunnel login` → pick `yiwang.dev`
3. `cloudflared tunnel create search-agent`
4. Add DNS: `api.search` CNAME → `<tunnel-id>.cfargotunnel.com`
5. Create `%USERPROFILE%\.cloudflared\config.yml`:

```yaml
tunnel: search-agent
credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: api.search.yiwang.dev
    service: http://localhost:8000
  - service: http_status:404
```

6. `.\scripts\start-personal.ps1` will run `cloudflared tunnel run search-agent`

---

## Daily workflow (self-use)

```powershell
# 1. When you want to research — one command
.\scripts\start-personal.ps1
#    → starts FastAPI on localhost:8000
#    → starts Cloudflare Tunnel (api.search.yiwang.dev → :8000)

# 2. Browser
#    https://search.yiwang.dev  → enter password
#    Settings → set LLM API Key, Base URL, Model (saved in browser)

# 3. Run research as usual

# 4. Done — Ctrl+C in terminal
#    → API offline; site still loads; settings still editable; search shows "API offline"
```

You do **not** need to open `localhost:3000` for normal use.  
The start script does **not** need to launch the Next.js dev server — the live UI is on Vercel.

---

## What “question 1” meant (clarified)

Previously we asked whether the start script should also run `pnpm dev` (local frontend).

| Option | Meaning | Your choice |
|--------|---------|-------------|
| Script = API + tunnel only | You use **search.yiwang.dev** on Vercel | **Yes — this one** |
| Script = API + tunnel + `pnpm dev` | You use **localhost:3000** instead | No (dev fallback only) |

---

## Security

| Layer | Protection |
|-------|------------|
| Site | Password on `search.yiwang.dev` (like jobs) |
| API | HMAC bearer token after site login (same secret on Vercel + backend) |
| LLM / Tavily keys | **BYOK in browser** — never on Vercel; sent per request to **your** local API |
| Demo | No API, no keys — static JSON only |

When your PC is off or script stopped: tunnel down → nobody can call your LLM, even if they know URLs.

---

## BYOK settings (Step 32 — done)

Frontend settings (localStorage, personal):

- LLM API Key
- LLM Base URL (e.g. DeepSeek, OpenAI)
- LLM Model
- Tavily API Key (optional)

Each research request sends `X-LLM-*` / `X-Tavily-API-Key` headers to your local backend.  
Backend `.env` keys remain optional fallback for local dev without BYOK.

---

## Implementation steps

| Step | Task | Status |
|------|------|--------|
| 29 | `scripts/start-personal.ps1` — API + Cloudflare Tunnel | Done |
| 30 | Password middleware on `search.yiwang.dev` | Done |
| 31 | API token after login | Done |
| 32 | Settings UI + per-request LLM BYOK | Done |
| 33 | `search-demo` static gallery | Done |
| 34 | DNS + Vercel domain aliases; remove tunnel env junk | Manual |

---

## Optional: Render / Docker (not default)

Use only if you later want 24/7 API without running your PC.

- [Deploy to Render](https://render.com/deploy?repo=https://github.com/1yiwang/search-agent) — free tier sleeps after 15 min idle
- [`backend/Dockerfile`](backend/Dockerfile) — for Docker / GHCR / Render

Current Vercel deployment (interim): https://search-agent-seven.vercel.app  
Will alias to `search.yiwang.dev` after DNS Step 34.

---

## Local development (unchanged)

```powershell
# Terminal 1
cd backend
.\.venv\Scripts\python.exe main.py

# Terminal 2
cd frontend
pnpm dev
# → http://localhost:3000  (rewrites /api → :8000, no tunnel needed)
```

---

## Environment reference

| Where | Variables |
|-------|-----------|
| Vercel | `SITE_PASSWORD`, `API_AUTH_SECRET`, `NEXT_PUBLIC_API_URL=https://api.search.yiwang.dev` |
| Browser (localStorage) | LLM key, base URL, model — **you edit in UI** |
| `backend/.env` | Optional defaults for local dev; Tavily/Jina if not BYOK yet |
| Cloudflare | Tunnel token for `api.search.yiwang.dev` |

See [`backend/.env.example`](backend/.env.example).
