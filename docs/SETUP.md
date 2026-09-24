# CityPulse — Setup

Everything runs locally. No accounts, API keys or internet access are required for the demo
(the map tiles need internet; without it the zones still render on a plain background).

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Python | 3.11 or newer (tested on 3.14) | `python3 --version` |
| Node.js | 20 or newer (tested on 26) | `node --version` |
| npm | comes with Node | `npm --version` |

## 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

On first start CityPulse creates `backend/data/citypulse.db` and generates 3 days of synthetic
history (≈ 1 second). You should see `CityPulse ready` in the log.

Check it: <http://127.0.0.1:8000/api/health> → `"status": "ok"`.
Interactive API docs: <http://127.0.0.1:8000/docs>.

## 2. Frontend (React + Vite)

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server forwards `/api/*` to the backend on port 8000.

## 3. Configuration (optional)

Copy the example file and edit what you need:

```bash
cp .env.example backend/.env
```

| Variable | Default | Meaning |
|---|---|---|
| `CITYPULSE_DATABASE_URL` | `sqlite:///./data/citypulse.db` | Any SQLAlchemy URL (e.g. PostgreSQL) |
| `CITYPULSE_LIVE_APIS` | `false` | `true` = pull real weather + air quality from Open-Meteo (free, no key) |
| `ANTHROPIC_API_KEY` | empty | Enables AI-assisted summaries. Empty = rule-based templates only |
| `CITYPULSE_AI_MODEL` | `claude-opus-5` | Model used for AI summaries |
| `CITYPULSE_TICK_SECONDS` | `3` | Pipeline update interval |
| `CITYPULSE_ROLLING_WINDOW_MINUTES` | `10` | Correlation / report-count window |
| `CITYPULSE_TRAFFIC_THRESHOLD_PCT` | `30` | Traffic anomaly threshold |
| `CITYPULSE_HEAVY_RAIN_MM_H` | `7.6` | Heavy-rain threshold |

All thresholds are listed in `backend/app/config.py` and explained in `docs/ARCHITECTURE.md`.
Never commit `.env` — it is in `.gitignore`.

## 4. Run the tests

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```

Expected: `98 passed`. Tests use a temporary database and a simulated clock, so they are fast
and deterministic.

Frontend type-check and production build:

```bash
cd frontend
npm run build
```

## 5. Using PostgreSQL instead of SQLite (optional)

```bash
pip install psycopg[binary]
export CITYPULSE_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/citypulse
```

Tables are created automatically on start-up.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend shows "Connecting to CityPulse…" forever | Backend isn't running on port 8000. Start it and the page reconnects by itself. |
| `Address already in use` | Another process is on port 8000/5173. Stop it or use `--port`. |
| Map is dark with no streets | No internet for map tiles. Zones, labels and data still work. |
| All feeds show `UNAVAILABLE` after the laptop slept | Normal — feeds recover on the next tick (≤ 10 s). |
| "Replay: No recorded event found" | History is generated on first start; restart the backend once. |
| Want a clean slate | Delete `backend/data/citypulse.db` and restart, or press **Demo → Normal state**. |
| AI badge never says "AI-assisted" | `ANTHROPIC_API_KEY` not set or the call failed; `/api/health` shows the AI status. Rule-based summaries are complete on their own. |
