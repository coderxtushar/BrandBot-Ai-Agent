# Brand Bot

An AI agent that builds your personal brand across **LinkedIn, X, Threads, Instagram, Medium and YouTube Shorts**.
It learns your brand, researches a timely angle on the web, writes platform-native content in your voice,
and has a reviewer agent check every draft (sending weak ones back for a rewrite).

**Stack:** LangGraph · LangChain · Gemini · Tavily · FastAPI (SSE) · SQLAlchemy 2 + Alembic (SQLite/Postgres) · React 19 · Vite · Tailwind 4

## How it works

```
profile ─► planner ─► research ─┬─ Send ─► platform[linkedin] ─┐
(reused if saved)               ├─ Send ─► platform[x]        ─┼─► result
                                └─ Send ─► platform[...]      ─┘

platform subgraph (runs in parallel for each platform):
  write ─► review ─► approved or out of attempts? ─► finalize
    ▲          │ no
    └──────────┘   lint issues (char limits, hashtag counts…) + reviewer feedback
```

- **Structured output everywhere**: every LLM call returns a Pydantic model ([backend/schemas.py](backend/schemas.py)).
- **Platform specs** ([backend/platforms/specs.py](backend/platforms/specs.py)): style guide, hard-rule lint, and a copy-ready renderer for each platform. To add a platform, add one spec.
- **Cheap retries**: drafts that break hard rules (such as a tweet over 280 characters) go straight back to the writer without paying for an LLM review.
- **Safe research**: web results go into prompts as delimited, untrusted data.
- **Saved brands and history**: brands, their profiles, and every run (plan, sources, drafts, reviews) are stored. A saved profile is reused, so runs skip that step until you change your brand input.

```
brands ─< runs ─< platform_results ─< drafts
```

## Run it

```bash
# Backend (Python 3.11–3.13)
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt   # or: python -m venv .venv && pip install ...
cp .env.example .env        # add GOOGLE_API_KEY and TAVILY_API_KEY, or set DEMO_MODE=true
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm install
cp .env.example .env        # VITE_API_URL if the API isn't on :8000
npm run dev                 # http://localhost:5173
```

`DEMO_MODE=true` returns canned content with realistic streaming, so you can work on the UI without API keys or credits.

### Database

By default the data lives in a local SQLite file (`brandbot.db`), and tables are created on startup.
For Postgres:

```bash
docker compose up -d                       # local Postgres 17
export DATABASE_URL=postgresql+asyncpg://brandbot:brandbot@localhost:5432/brandbot
export DB_AUTO_CREATE=false
.venv/bin/alembic upgrade head             # apply migrations
```

After changing [backend/db/models.py](backend/db/models.py), run `alembic revision --autogenerate -m "..."`.
A test fails if the models and migrations drift apart.

## API

| Method | Path | |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/platforms` | Supported platforms |
| POST | `/brands` | Create a brand (name + input) |
| GET | `/brands` | List brands |
| GET / PATCH / DELETE | `/brands/{id}` | Read, update, or delete. Changing the input clears the saved profile |
| PUT | `/brands/{id}/profile` | Save a hand-edited brand profile (the "Brand profile" card in the UI) |
| POST | `/brands/{id}/runs/stream` | Generate and **save** a run, as SSE: `run`, `progress`*, then `result` (or `error`) |
| POST | `/brands/{id}/runs` | Same, without streaming |
| GET | `/brands/{id}/runs` | Run history (`limit`, `offset`) |
| GET / DELETE | `/runs/{id}` | A saved run with all drafts, or delete it |
| POST | `/runs`, `/runs/stream` | Stateless: generate without saving |

Interactive docs: http://localhost:8000/docs

## Tests

```bash
.venv/bin/python -m pytest        # offline: uses fake LLM and search
cd frontend && npm run lint && npm run build
```

## Roadmap

- [x] **1. Foundation**: settings, pinned deps, current Gemini model, structured output, async API
- [x] **2. Multi-platform agent**: 6 platform specs, `Send` fan-out, review → rewrite loop
- [x] **3. Streaming API + tests**: SSE progress, offline tests, demo mode
- [x] **4. React app**: platform picker, live progress, native previews, copy / .md export
- [x] **5. Persistence**: SQLAlchemy + Alembic (SQLite or Postgres), saved brands, profile editor, run history UI
- [ ] **6. Editing loop**: regenerate one draft, "shorter / punchier" rewrites, approve/reject drafts, LangGraph checkpointer + `interrupt()` for approval
- [ ] **7. Visuals**: Gemini image generation for Instagram covers and carousel slides, Shorts thumbnails
- [ ] **8. Accounts and publishing**: auth, OAuth for LinkedIn / X / Threads / Instagram, scheduled publishing
- [ ] **9. Content calendar and analytics**: schedule view, metrics pulled back in, best performers feed future runs
- [ ] **10. Deploy**: Docker, Cloud Run + Vercel, LangSmith tracing, rate limits

Medium no longer issues API tokens for new integrations, so Medium stays "export Markdown and import".
YouTube Shorts produces scripts; uploading needs a rendered video file.
