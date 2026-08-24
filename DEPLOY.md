# Deploying MATF

The app has two parts that deploy to **two different places**:

| Part | What it is | Host |
|---|---|---|
| `frontend/` | React + Vite static SPA | **Vercel** ✅ |
| `backend/` | FastAPI + SQLAlchemy + long-running experiment jobs | **Render / Railway / Fly.io** (not Vercel) |

**Why the backend can't go on Vercel:** Vercel runs short-lived serverless functions with an ephemeral, read-only filesystem. This backend needs a **persistent database** (SQLite/Postgres) and runs **experiment jobs that take minutes** — both of which serverless kills or resets. Put it on a host with a real disk and no hard request-time limit.

Deploy the **backend first** (you need its URL for the frontend).

---

## 1. Backend → Render (free tier works)

1. Push this repo to GitHub (see the last section).
2. On [render.com](https://render.com): **New → Web Service**, connect the repo.
3. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     (this is also in `backend/Procfile`)
4. **Database:** Render → **New → PostgreSQL** (free), copy its *Internal Database URL*.
   - Add `psycopg2-binary` to `backend/requirements.txt` first (the Postgres driver — not needed for local SQLite).
   - SQLite also "works" but resets whenever the instance restarts, so use Postgres for anything real.
5. **Environment variables** (Render → the web service → Environment):
   ```
   DATABASE_URL=postgresql://…            # the Render Postgres URL (leave unset to use throwaway SQLite)
   JWT_SECRET=<a long random string>
   CORS_ORIGINS=https://<your-vercel-app>.vercel.app
   LLM_PROVIDER=mock                       # 'mock' = free/offline. Use 'gemini' for real runs.
   GEMINI_API_KEY=<only if LLM_PROVIDER=gemini>
   ```
6. Deploy. Note the public URL, e.g. `https://matf-api.onrender.com`.

> **Python version:** this repo was developed on Python 3.14. If your host doesn't offer it yet, pin a supported one (e.g. add `backend/runtime.txt` containing `python-3.12.x`); the code runs on 3.11+.

## 2. Frontend → Vercel

1. On [vercel.com](https://vercel.com): **Add New → Project**, import the same repo.
2. Settings:
   - **Root Directory:** `frontend`
   - Framework preset **Vite** is auto-detected (config is in `frontend/vercel.json`).
3. **Environment variable:**
   ```
   VITE_API_URL=https://matf-api.onrender.com    # your backend URL from step 1
   ```
4. Deploy. You'll get `https://<your-app>.vercel.app`.
5. **Back on the backend**, set `CORS_ORIGINS` to that exact Vercel URL and redeploy, or the browser will block API calls.

## 3. First-run setup (once, in the browser)

1. Open the Vercel URL → **Create account** (real signup works; the localhost-only demo login does not apply to a hosted instance).
2. Go to **Experiments → "Seed / refresh benchmark"** to load the 16-program benchmark.
3. Pick **Quick · 6 programs** + `LLM_PROVIDER=mock` for a free first run to confirm everything's wired up. Switch to `gemini` + a Full run for real results.

---

## What you have to do yourself

I've made the repo deploy-ready (this guide, `frontend/vercel.json`, `frontend/.env.example`, `backend/Procfile`). The steps that need **your accounts and credentials** — creating the Vercel/Render projects, entering API keys, and clicking Deploy — are yours to do; I can't log in as you.

## Pushing to GitHub (if not already)

```bash
git add -A && git commit -m "Add deploy config for Vercel (frontend) + Render (backend)"
git push
```
Both Vercel and Render deploy automatically on every push once the projects are connected.
