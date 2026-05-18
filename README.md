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
uvicorn backend.main:app --reload --port 8000         # backend
cd frontend; npm install; npm run dev                 # frontend at :5173
```
