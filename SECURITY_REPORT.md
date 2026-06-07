# Security Audit Report — Funding MVP

**Date:** 2026-06-07  
**Auditor:** Automated code review  
**Scope:** All project files (Python backend + HTML/JS frontend)

---

## Checklist

### 1. API Key & Credentials

| Check | Status | Notes |
|---|---|---|
| No hardcoded `sk-ant-…` strings in source | ✅ PASS | Grep found zero matches |
| API key read via `os.getenv("ANTHROPIC_API_KEY")` | ✅ PASS | `profiler.py` line 34 |
| `.env` file exists with real key | ✅ PASS | Local only, never committed |
| `.env` in `.gitignore` | ✅ PASS | Top of `.gitignore` |
| `.env.example` exists | ✅ FIXED | Created during this audit |
| No secrets in HTML/JS comments | ✅ PASS | Audited manually |
| `SEDIA` API key in `calls_fetcher.py` | ℹ️ INFO | Public key, not sensitive |

### 2. Git Repository

| Check | Status | Notes |
|---|---|---|
| Git repository initialized | ⚠️ TODO | No `.git/` directory yet — see instructions below |
| `.env` not tracked by git | ✅ N/A | No repo yet = zero exposure |
| `calls_index.json` in `.gitignore` | ✅ FIXED | Added during audit |
| `calls_live.txt` in `.gitignore` | ✅ FIXED | Added during audit |
| `profiles/` fully excluded | ✅ FIXED | Changed from subdirs-only to root |
| `.DS_Store` excluded | ✅ FIXED | Added during audit |
| `venv/` excluded | ✅ PASS | Already present |
| `logs/` excluded | ✅ PASS | Already present |
| `*.pyc` / `__pycache__/` excluded | ✅ PASS | Already present |

### 3. Environment Variables

| Check | Status | Notes |
|---|---|---|
| `.env.example` template created | ✅ FIXED | `ANTHROPIC_API_KEY=your_key_here` |
| `.env` never goes into git | ✅ PASS | In `.gitignore` |
| Production secrets via platform UI | ✅ READY | Instructions below |

### 4. API Security (`api.py`)

| Check | Status | Notes |
|---|---|---|
| CORS configured | ✅ PASS | `CORSMiddleware` present |
| `allow_origins=["*"]` | ⚠️ ACCEPTABLE | OK for MVP; restrict in prod (see below) |
| API key not hardcoded | ✅ PASS | `os.getenv()` via dotenv |
| `/health` returns minimal info | ✅ PASS | Only `{"status": "ok"}` |
| Error responses don't expose stack traces | ✅ FIXED | Replaced `f"...{exc}"` with generic messages |
| Full errors logged server-side | ✅ FIXED | `exc_info=True` added to logger calls |
| Rate limiting | ⚠️ MISSING | Not critical for MVP; add before public launch |

### 5. Logging (`logger.py`)

| Check | Status | Notes |
|---|---|---|
| No API keys in log output | ✅ PASS | Audited all `logger.*()` calls |
| `logs/` in `.gitignore` | ✅ PASS | Confirmed |
| Log rotation configured | ⚠️ MISSING | `logs/app.log` grows indefinitely; add `RotatingFileHandler` before prod |
| Console level: INFO | ✅ PASS | Only operational events |
| File level: DEBUG | ✅ PASS | Internal detail, not exposed |

### 6. Frontend (`frontend.html`)

| Check | Status | Notes |
|---|---|---|
| No hardcoded API keys | ✅ PASS | None found |
| API URL configurable | ✅ FIXED | `API_BASE` constant with `?api=` override |
| No sensitive data in comments | ✅ PASS | Audited |
| CDN libraries pinned to major version | ⚠️ INFO | React 18, Babel standalone — acceptable for MVP |

### 7. Dependencies (`requirements.txt`)

| Check | Status | Notes |
|---|---|---|
| All versions pinned | ✅ PASS | `==` for all packages |
| `python-dotenv` included | ✅ FIXED | Added `python-dotenv==1.2.2` |
| `anthropic` pinned | ✅ PASS | `anthropic==0.107.0` |
| `fastapi` pinned | ✅ PASS | `fastapi==0.136.3` |

---

## Findings Summary

### Fixed During This Audit (6 items)

1. **`requirements.txt`** — Added missing `python-dotenv==1.2.2`. App would crash on a fresh install without it.
2. **`.gitignore`** — Added `calls_index.json`, `calls_live.txt`, `profiles/`, `.DS_Store`, `.vscode/`, `*.log`.
3. **`.env.example`** — Created template file. Required by all deployment platforms.
4. **`frontend.html`** — Replaced hardcoded `http://localhost:8000` with `API_BASE` constant. Configurable via `?api=` query param or `window.API_BASE`.
5. **`api.py` error messages** — Replaced `detail=f"...{exc}"` with generic messages. Full errors still logged server-side via `exc_info=True`.
6. **`.gitignore` `profiles/`** — Changed from listing `profiles/cache/`, `profiles/raw/`, `profiles/archive/` separately to `profiles/` (covers all subdirectories).

### Acceptable for MVP (3 items)

7. **CORS `allow_origins=["*"]`** — Acceptable for MVP. Restrict before public launch (see below).
8. **No rate limiting** — Acceptable for controlled access. Add `slowapi` before public launch.
9. **Log rotation missing** — `logs/app.log` grows unbounded. Railway/Render auto-restart handles this in practice; add `RotatingFileHandler` for long-term prod.

---

## 🚀 Deployment Instructions

### Step 1 — Initialize Git (do this once)

```bash
cd C:\Users\drako\funding-mvp

git init
git add .
git status          # verify .env is NOT listed
git commit -m "Initial commit — funding MVP"

# Push to GitHub (create a NEW private repo first)
git remote add origin https://github.com/YOUR_USERNAME/funding-mvp.git
git push -u origin main
```

**Before `git add .`, always run `git status` and confirm `.env` is NOT in the list.**

### Step 2 — Deploy to Railway

```bash
# Install Railway CLI
npm i -g @railway/cli
railway login
railway init          # link to new project
railway up
```

Set secrets in Railway dashboard → Variables:
```
ANTHROPIC_API_KEY = sk-ant-api03-...   (your real key)
```

Railway auto-sets `PORT`. Update `uvicorn` start command:
```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

### Step 3 — Deploy to Render (alternative)

1. Connect GitHub repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
4. Environment → Add `ANTHROPIC_API_KEY`

### Step 4 — Point Frontend to Production API

When serving `frontend.html` publicly, either:

**Option A — Query param (no code change needed):**
```
https://yourfrontend.com/index.html?api=https://your-api.railway.app
```

**Option B — Inject at serve time (nginx/static host):**
```html
<script>window.API_BASE = "https://your-api.railway.app";</script>
```
Add this before the `<script type="text/babel">` tag.

### Step 5 — Tighten CORS for Production

In `api.py`, replace:
```python
allow_origins=["*"]
```
with:
```python
allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(",")
```

Then set `ALLOWED_ORIGINS=https://yourfrontend.com` in Railway/Render.

### Pre-Deployment Checklist

```bash
# 1. Verify .env is NOT tracked
git ls-files .env       # should return nothing

# 2. Verify secrets are set in platform
railway variables       # or Render dashboard

# 3. Test health endpoint
curl https://your-api.railway.app/health
# expected: {"status":"ok"}

# 4. Test analyze endpoint
curl -X POST https://your-api.railway.app/analyze \
  -H "Content-Type: application/json" \
  -d '{"url":"https://ging.github.io/"}'
# expected: {"profile":{...},"opportunities":{...}}
```

---

## Status

> **✅ SAFE FOR DEPLOYMENT WITH MINOR CAVEATS**
>
> All critical issues have been fixed. The remaining items (CORS wildcard, no rate limiting, no log rotation) are acceptable for a controlled MVP deployment and are documented above for future hardening.

---

## Required Variables for Production

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | **YES** | Claude API key from console.anthropic.com |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend origins (default: `*`) |
| `PORT` | Auto-set | Set automatically by Railway/Render |
