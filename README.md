## upGrad Course Recommendation Chatbot

A conversational course recommender for upGrad. A Playwright scraper builds a SQLite + Excel catalog, an OpenAI-backed FastAPI service runs a slot-filling chat that learns who you are without interrogating you, and a Tailwind/React frontend themed to match upgrad.com surfaces three picks with one-line rationales. See `BUILD_PLAN.md` for the full spec and `docs/SCHEMA.md` / `docs/PROMPTS.md` for the data dictionary and versioned prompts.

### Setup (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

copy .env.example .env
# edit .env, set OPENAI_API_KEY
```

### Run

```powershell
python -m scraper.run --full                          # build the catalog
python -m scraper.run --backfill-faculty              # populate faculty tags (after --full)
uvicorn backend.main:app --reload --port 8000         # backend
cd frontend; npm install; npm run dev                 # frontend at :5173
```

### Deploy

Backend on Render (`render.yaml`), frontend on Netlify (`netlify.toml`). Set
`OPENAI_API_KEY` and `ALLOWED_ORIGINS` (your Netlify URL) on Render, and
`VITE_API_BASE` (your Render URL) on Netlify.

### Keeping the backend warm

The Render free tier sleeps after ~15 min of inactivity, so the first request to a
cold instance can take 30 to 60 seconds. To keep it warm:

1. Sign up for UptimeRobot (https://uptimerobot.com/), free up to 50 monitors.
2. Add a monitor:
   - Type: HTTP(s)
   - URL: `https://<your-render-url>/healthz`
   - Interval: 5 minutes
3. Done. The instance receives a request every 5 minutes and never sleeps.

`/healthz` is a no-op liveness probe (no DB or OpenAI calls), so the ping is cheap.
Alternative: cron-job.org with the same URL on a 10-minute interval.

### What's new in v0.2

- Keepalive-friendly `/healthz` + UptimeRobot guidance.
- Tighter, non-generic persona voice with a banned-phrase list and a per-turn reminder.
- Long-conversation handling: running summary + sliding window + off-topic steer-back.
- "Show me more" pagination and chat-driven filter refinement ("any IIM options?", "cheaper please").
- Richer cards: `fit_reasons` and an honest `watch_outs` per recommendation.
