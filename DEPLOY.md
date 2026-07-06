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

Also enable **Git auto-deploy**: Vercel → Settings → Git → connected repo `1yiwang/search-agent`, branch `master`, **Root Directory = `frontend`**.

---

## Step 34 — 实操清单（按顺序做）

### A. Vercel：同一个项目绑两个前端域名

**可以，而且应该这样做** — `search.yiwang.dev` 和 `search-demo.yiwang.dev` 都加在**同一个** Vercel 项目里。

1. 打开 [Vercel Dashboard](https://vercel.com) → 项目 **search-agent** → **Settings** → **Domains**
2. 点 **Add**，依次添加：
   - `search.yiwang.dev`（自用，有密码门）
   - `search-demo.yiwang.dev`（公开 demo，代码会自动只显示 `/demo`）
3. Vercel 会显示每条域名需要的 DNS 记录（通常是 **CNAME** → `cname.vercel-dns.com` 或项目专属地址）
4. 到 **Cloudflare** → `yiwang.dev` → **DNS** → **Add record**：

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `search` | Vercel 提示的目标 | DNS only（灰云）推荐 |
| CNAME | `search-demo` | 同上 | DNS only（灰云）推荐 |

5. 回到 Vercel Domains 页，等状态变 **Valid**

**当前状态（2026-07-06）：**

- `search.yiwang.dev` — 已在 search-agent 项目，**可访问**（密码门正常）
- `search-demo.yiwang.dev` — 已加到 Vercel，需在 Cloudflare 加 DNS：

| Type | Name | Value | Proxy |
|------|------|-------|-------|
| A | `search-demo` | `76.76.21.21` | DNS only（灰云） |

（Vercel 也可能显示 CNAME 到 `cname.vercel-dns.com`，以 Domains 页提示为准。）

6. **Settings → Git**：Root Directory = **`frontend`**，确保以后 `git push` 自动部署

代码里 `proxy.ts` 已按域名分流：

- `search.yiwang.dev` → 完整 App + 密码
- `search-demo.yiwang.dev` → 自动跳转 `/demo`，无需密码、无需 API

---

### B. Settings（LLM Key）怎么用

| 问题 | 答案 |
|------|------|
| 每次都要填吗？ | **不用**。填一次 → 点 **Save settings** → 存在浏览器 `localStorage` |
| 下次打开还在吗？ | **在**（同一浏览器、未清缓存） |
| 能改吗？ | 随时打开 Settings 修改 → 再 Save |
| 能删吗？ | 点 **Clear all keys** 清空 |
| 换电脑/浏览器？ | 需要重新填（故意设计：Key 不上传 Vercel） |

研究时：网站把 Key 通过请求头发给你本机 API（`api.search.yiwang.dev`），不经第三方服务器存储。

---

### C. Cloudflare Tunnel：`api.search.yiwang.dev` → 你电脑 `:8000`

**原理：** 你电脑上跑 FastAPI（8000 端口）+ `cloudflared` 客户端。Cloudflare 把公网域名 `api.search.yiwang.dev` 的流量，通过加密隧道转到你本机。**脚本关掉 = 隧道断 = 外人调不了你的 LLM。**

#### 会不会影响 yiwang.dev 上其他网站？

**不会动到其他站点**，原因：

| 操作 | 实际影响范围 |
|------|----------------|
| `tunnel login` | 授权本机管理隧道（选 zone 时只勾选 `yiwang.dev`） |
| `tunnel create` | 新建一条隧道，不改现有 DNS |
| `tunnel route dns` | **只加一条** `api.search` 的 CNAME |
| `config.yml` ingress | **只转发** `api.search.yiwang.dev` → `:8000`，其余 hostname 走 `http_status:404` |

`search.yiwang.dev` / `search-demo.yiwang.dev` / 你其他子站 **走 Vercel 或各自配置**，与隧道无关。

若仍不放心自动改 DNS，默认已是 **手动模式**（推荐）：

```powershell
.\scripts\setup-cloudflare-tunnel.ps1
# 只创建隧道 + config.yml；DNS 自己在 Cloudflare 加一条 api.search CNAME

# 若你明确想用自动 DNS：
.\scripts\setup-cloudflare-tunnel.ps1 -AutoDns
```

| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `api.search` | `<tunnel-uuid>.cfargotunnel.com` | 灰云 |

`<tunnel-uuid>` 用 `cloudflared tunnel info search-agent` 查看。

#### SEO / 收录策略（已实现）

| 域名 | robots | 说明 |
|------|--------|------|
| `search.yiwang.dev` | `noindex` | 私密站，可搜到登录页但不被收录 |
| `search-demo.yiwang.dev` | 允许 `/demo` | 公开展示 demo |
| `api.search.yiwang.dev` | 无页面 | 仅 API，隧道按需开 |

#### 不想在 yiwang.dev 上开任何 Tunnel？

可选替代（按隔离程度从高到低）：

| 方案 | 说明 |
|------|------|
| **A. 仅本机** | `pnpm dev` + 本机 API，不暴露公网 API；`search.yiwang.dev` 只能看页面，研究在本机做 |
| **B. Tailscale** | API 只在你的设备 mesh 内可达，公网无 `api.search` 记录 |
| **C. 单独子域** | 保持 `api.search.yiwang.dev`（只一条 DNS，与主站逻辑隔离） |
| **D. 当前 Tunnel** | 按需开关，关脚本即断 |

对个人自用，**C + 按需开关** 或 **B** 通常足够；A 最简单但无法在外用手机调 API。

#### 方式 1：一键脚本

```powershell
winget install Cloudflare.cloudflared
.\scripts\setup-cloudflare-tunnel.ps1
.\scripts\start-personal.ps1
```

#### 方式 2：手动步骤

1. **安装** [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)  
   Windows: `winget install Cloudflare.cloudflared`

2. **登录**（浏览器会打开，选 `yiwang.dev`）  
   ```powershell
   cloudflared tunnel login
   ```

3. **创建隧道**  
   ```powershell
   cloudflared tunnel create search-agent
   ```
   记下 `%USERPROFILE%\.cloudflared\` 下新生成的 `<uuid>.json` 文件名。

4. **自动添加 DNS**（比手填 CNAME 省事）  
   ```powershell
   cloudflared tunnel route dns search-agent api.search.yiwang.dev
   ```
   这会在 Cloudflare DNS 里创建 `api.search` → `<tunnel-id>.cfargotunnel.com`。

5. **写配置文件** `%USERPROFILE%\.cloudflared\config.yml`（可参考 [`scripts/cloudflared.config.example.yml`](scripts/cloudflared.config.example.yml)）：

   ```yaml
   tunnel: search-agent
   credentials-file: C:\Users\<你>\.cloudflared\<uuid>.json

   ingress:
     - hostname: api.search.yiwang.dev
       service: http://localhost:8000
     - service: http_status:404
   ```

6. **验证**  
   ```powershell
   .\scripts\start-personal.ps1
   # 另一个终端：
   curl https://api.search.yiwang.dev/api/health
   ```
   应返回 `{"status":"ok",...}`。

#### 常见问题

| 现象 | 处理 |
|------|------|
| `connection refused` | 先确认本机 `http://localhost:8000/api/health` 正常 |
| DNS 未生效 | `api.search` CNAME 在 Cloudflare 设为 **DNS only**（灰云） |
| 隧道起不来 | 检查 `config.yml` 里 `credentials-file` 路径是否正确 |
| 没 config 时 | `start-personal.ps1` 会退化为 quick tunnel（随机 URL，仅临时测试用） |

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
| 34 | DNS aliases + Vercel cleanup (remove temp tunnel env) | In progress |

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
