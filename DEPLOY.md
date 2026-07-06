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
| `api-search.yiwang.dev` | Cloudflare Tunnel → your PC `:8000` | Only when script is running |

DNS (one-time):

- `search-demo` → Vercel (CNAME)
- `search` → Vercel (CNAME)
- `api-search` → Cloudflare Tunnel (created when you set up tunnel)

Vercel env (production):

```
NEXT_PUBLIC_API_URL=https://api-search.yiwang.dev
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

研究时：网站把 Key 通过请求头发给你本机 API（`api-search.yiwang.dev`），不经第三方服务器存储。

---

### C. Cloudflare Tunnel：`api-search.yiwang.dev` → 你电脑 `:8000`

**DNS 你已经加好的话，不要再跑 `setup-cloudflare-tunnel.ps1`**（它会打开「授权 zone」的浏览器链接）。

改用下面 **Dashboard 方式** — 不动其他 DNS、不需要 CLI `tunnel login`：

#### 推荐：Cloudflare 控制台创建隧道（无需 CLI 授权主域）

1. 打开 [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → **Create a tunnel**
2. 名称：`search-agent` → 下一步
3. **Public Hostname**（若你 DNS 已手动指好，这里也要填一致）：
   - Subdomain: `api-search` / Domain: `yiwang.dev`
   - **Type: HTTP**（不是 HTTPS）
   - URL: `localhost:8000`

   > 若误选 **HTTPS**，隧道会连 `https://localhost:8000`，本机 FastAPI 是 HTTP，外网会一直超时。
4. 在 **Install connector** 页面二选一：

**方式 A — Run token（最简单）**

复制那一长串 token，保存到：

```
%USERPROFILE%\.cloudflared\token.txt
```

（文件里只有一行 token，无引号）

然后：

```powershell
.\scripts\start-personal.ps1
```

**方式 B — 凭证 JSON**

把下载的 `<uuid>.json` 放到 `%USERPROFILE%\.cloudflared\`，再运行：

```powershell
.\scripts\write-tunnel-config.ps1
.\scripts\start-personal.ps1
```

全程 **不会** 再弹出「授权 yiwang.dev zone」的 CLI 链接。

#### `tunnel login` 那个链接到底是什么？

只有跑 **CLI** `cloudflared tunnel login` 时才会出现。它授权的是「本机命令行创建隧道」，**不是**把主域交给别人管，也**不会**改你现有 DNS。

你已自己加好 DNS → **跳过 CLI 登录**，用上面 Dashboard 流程即可。

#### 旧方式（仅当 Dashboard 搞不定时）

```powershell
.\scripts\setup-cloudflare-tunnel.ps1   # 会触发 tunnel login，不推荐你已加 DNS 时用
```

#### SEO / 收录策略（已实现）

| 域名 | robots | 说明 |
|------|--------|------|
| `search.yiwang.dev` | `noindex` | 私密站，可搜到登录页但不被收录 |
| `search-demo.yiwang.dev` | 允许 `/demo` | 公开展示 demo |
| `api-search.yiwang.dev` | 无页面 | 仅 API，隧道按需开 |

#### 不想在 yiwang.dev 上开任何 Tunnel？

可选替代（按隔离程度从高到低）：

| 方案 | 说明 |
|------|------|
| **A. 仅本机** | `pnpm dev` + 本机 API，不暴露公网 API；`search.yiwang.dev` 只能看页面，研究在本机做 |
| **B. Tailscale** | API 只在你的设备 mesh 内可达，公网无 `api-search` 记录 |
| **C. 单独子域** | 保持 `api-search.yiwang.dev`（只一条 DNS，与主站逻辑隔离） |
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
   cloudflared tunnel route dns search-agent api-search.yiwang.dev
   ```
   这会在 Cloudflare DNS 里创建 `api-search` → `<tunnel-id>.cfargotunnel.com`。

5. **写配置文件** `%USERPROFILE%\.cloudflared\config.yml`（可参考 [`scripts/cloudflared.config.example.yml`](scripts/cloudflared.config.example.yml)）：

   ```yaml
   tunnel: search-agent
   credentials-file: C:\Users\<你>\.cloudflared\<uuid>.json

   ingress:
     - hostname: api-search.yiwang.dev
       service: http://localhost:8000
     - service: http_status:404
   ```

6. **验证**  
   ```powershell
   .\scripts\start-personal.ps1
   # 另一个终端：
   curl https://api-search.yiwang.dev/api/health
   ```
   应返回 `{"status":"ok",...}`。

#### 常见问题

| 现象 | 处理 |
|------|------|
| `connection refused` | 先确认本机 `http://localhost:8000/api/health` 正常 |
| DNS 未生效 / curl 超时 | `api-search` CNAME 必须 **橙云 Proxied**；灰云会解析到内部 `fd10:` 地址，外网连不上 |
| HTTPS 握手失败 (curl 35) | 不要用 `api.search`（三级子域），免费 SSL 不覆盖；改用 **`api-search.yiwang.dev`** |
| 隧道起不来 | 检查 `config.yml` 里 `credentials-file` 路径是否正确 |
| 没 config 时 | `start-personal.ps1` 会退化为 quick tunnel（随机 URL，仅临时测试用） |

---

## Daily workflow (self-use)

```powershell
# 1. When you want to research — one command
.\scripts\start-personal.ps1
#    → starts FastAPI on localhost:8000
#    → starts Cloudflare Tunnel (api-search.yiwang.dev → :8000)

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
| Vercel | `SITE_PASSWORD`, `API_AUTH_SECRET`, `NEXT_PUBLIC_API_URL=https://api-search.yiwang.dev` |
| Browser (localStorage) | LLM key, base URL, model — **you edit in UI** |
| `backend/.env` | Optional defaults for local dev; Tavily/Jina if not BYOK yet |
| Cloudflare | Tunnel token for `api-search.yiwang.dev` |

See [`backend/.env.example`](backend/.env.example).
