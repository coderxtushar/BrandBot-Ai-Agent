# Brand Bot

An AI agent that builds your personal brand across **LinkedIn, X, Threads, Instagram, Medium and YouTube Shorts**.
It learns your brand, researches a timely angle on the web, writes platform-native content in your voice,
and has a reviewer agent check every draft (sending weak ones back for a rewrite).

**Stack:** LangGraph · LangChain · Gemini · Tavily · FastAPI (SSE) · SQLAlchemy 2 + Alembic (SQLite/Postgres) · Next.js 16 · Tailwind 4 · shadcn/ui · Framer Motion · TanStack Query

## How it works

```
profile ─► planner ─► research ─► plan_review ─┬─ Send ─► platform[linkedin] ─┐
(reused if saved)                 (optional    ├─ Send ─► platform[x]        ─┼─► result
                                   pause)      └─ Send ─► platform[...]      ─┘

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
- **Human in the loop**: with "review the angle first", a run pauses after research (LangGraph `interrupt()`). You edit the angle, drop sources, or add guidance, then it continues. The run is checkpointed (SQLite file, or Postgres), so a paused run survives server restarts.
- **Visuals**: an art-director step turns any draft into an image brief using your brand's visual style, and Gemini generates it at the platform's aspect ratio (1:1 LinkedIn, 16:9 X and Medium, 4:5 Threads and Instagram, 9:16 Shorts). Images show up in the previews (carousel cover, article header, Shorts thumbnail).
- **Accounts**: email + password sign-in (argon2 hashes, HTTP-only session cookies stored hashed, login rate limit, CSRF origin check). Every brand, run, draft and image belongs to one user.
- **Publishing**: connect LinkedIn, X, Threads and Instagram with OAuth (PKCE for X; tokens encrypted at rest and refreshed automatically), then publish a draft now or schedule it. A background scheduler claims each due post atomically, so a post never goes out twice, and retries temporary failures.
- **Analytics**: stats for published posts are read back from X, Threads and Instagram every few hours and kept as history. LinkedIn doesn't share personal post stats with apps, so you can type results in, and mark posts you published yourself (e.g. Medium, Shorts) so they count too. The analytics page shows totals vs the previous period, a daily trend, platform and topic comparisons, a day × time heatmap and your top posts.
- **Learning loop**: new runs show the writers this brand's best-performing posts per platform, and tell the planner which topics work best. The Publish dialog suggests your best posting time from your own history.
- **Calendar**: a month view of everything scheduled and published; drag a post to another day to reschedule it.
- **Editing loop**: approve/reject each draft, edit it in a form built from the platform's own format, or ask the AI to rewrite it ("shorter", "punchier", or your own words). Rewrites go through the same write → review loop. Every change is a version you can restore.

```
brands ─< runs ─< platform_results ─< drafts ─< draft_versions
                                              └─< draft_images
```

## Run it

```bash
# Backend (Python 3.11–3.13)
uv venv --python 3.12 .venv && uv pip install -r requirements-dev.txt   # or: python -m venv .venv && pip install ...
cp .env.example .env        # add GOOGLE_API_KEY and TAVILY_API_KEY, or set DEMO_MODE=true
.venv/bin/uvicorn backend.main:app --reload --port 8000

# Frontend (Next.js)
cd frontend && npm install
cp .env.example .env.local  # NEXT_PUBLIC_API_URL if the API isn't on :8000
npm run dev                 # http://localhost:3000  (landing page; the app is at /studio)
```

`DEMO_MODE=true` returns canned content with realistic streaming, so you can work on the UI without API keys or credits.

### Publishing to your accounts

Create a developer app per platform and set its OAuth redirect URL to
`{API_PUBLIC_URL}/connections/{platform}/callback`, then add the credentials to `.env`:

| Platform | What to set up | Env vars |
|---|---|---|
| LinkedIn | Products "Share on LinkedIn" + "Sign In with LinkedIn using OpenID Connect" | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_API_VERSION` (YYYYMM) |
| X | OAuth 2.0, app type "Web App" (confidential client) | `X_CLIENT_ID`, `X_CLIENT_SECRET` |
| Threads | Threads API use case | `THREADS_APP_ID`, `THREADS_APP_SECRET` |
| Instagram | Instagram API with Instagram Login (Business or Creator accounts) | `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` |

Also set `SECRET_KEY` (encrypts stored tokens), `WEB_URL`, and `API_PUBLIC_URL`. Instagram and Threads download
images from `API_PUBLIC_URL`, so it must be a public https address for image posts (a tunnel works for testing).
Images are converted to JPEG for Instagram. X threads are posted as text. Medium and YouTube Shorts have no
posting API, so they stay copy / export. In `DEMO_MODE`, every platform is simulated end to end.

### Database

By default the data lives in a local SQLite file (`brandbot.db`), and tables are created on startup.
Paused-run checkpoints go to `brandbot_checkpoints.db` (with Postgres, LangGraph creates its own tables in the same database).
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
| POST | `/auth/register`, `/auth/login`, `/auth/logout` | Accounts (session cookie) |
| GET | `/auth/me` | The signed-in user |
| GET | `/connections` | Connected accounts and which platforms this server can connect |
| POST | `/connections/{platform}/start` | Start OAuth; returns the consent URL |
| GET | `/connections/{platform}/callback` | OAuth redirect target |
| DELETE | `/connections/{id}` | Disconnect (cancels its scheduled posts) |
| POST | `/drafts/{id}/publications` | Publish now, or schedule with `scheduled_at` |
| GET | `/publications` | Your posts (`status`, `start` / `end` filters) |
| PATCH | `/publications/{id}` | Reschedule |
| POST | `/publications/{id}/cancel`, `/publications/{id}/retry` | Cancel a scheduled post, retry a failed one |
| GET | `/analytics/posts` | Published posts with their latest stats (`days`, `brand_id`, `platform`) |
| POST | `/analytics/refresh` | Read fresh stats for your recent posts now |
| GET / POST | `/publications/{id}/metrics` | Stats history, or type in results by hand |
| POST | `/drafts/{id}/manual-publication` | "I posted this myself" (link + date), so its results can be tracked |
| GET | `/platforms` | Supported platforms |
| POST | `/brands` | Create a brand (name + input) |
| GET | `/brands` | List brands |
| GET / PATCH / DELETE | `/brands/{id}` | Read, update, or delete. Changing the input clears the saved profile |
| PUT | `/brands/{id}/profile` | Save a hand-edited brand profile (the "Brand profile" card in the UI) |
| POST | `/brands/{id}/runs/stream` | Generate and **save** a run, as SSE: `run`, `progress`*, then `result` (or `error`) |
| POST | `/brands/{id}/runs` | Same, without streaming |
| GET | `/brands/{id}/runs` | Run history (`limit`, `offset`) |
| GET / DELETE | `/runs/{id}` | A saved run with all drafts, or delete it |
| POST | `/runs/{id}/resume/stream` | Continue a run paused for plan review (`angle`, `pillar`, `source_urls`, `guidance`) |
| POST | `/runs/{id}/cancel` | Discard a paused run |
| GET / PATCH | `/drafts/{id}` | Read a draft, or save an edit (validated per platform) and/or approve/reject it |
| POST | `/drafts/{id}/rewrite` | AI rewrite: `preset` and/or `instruction`, or `fresh: true` for a new draft |
| GET | `/drafts/{id}/versions` | Version history, newest first |
| POST | `/drafts/{id}/versions/{vid}/restore` | Restore an earlier version |
| POST | `/drafts/{id}/images` | Generate an on-brand image (`idea`, `style`: photo / illustration / 3d / minimal) |
| GET | `/drafts/{id}/images` | Images for a draft, newest first |
| DELETE | `/images/{id}` | Delete an image and its file |
| GET | `/media/{path}` | Serve a stored image |
| POST | `/runs`, `/runs/stream` | Stateless: generate without saving |

Interactive docs: http://localhost:8000/docs. Everything except `/health`, `/platforms`, `/auth/*`, the OAuth callback and `/media` needs a signed-in session.

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
- [x] **6. Editing loop**: approve/reject, structured editor, AI rewrites and fresh drafts, version history, plan review via checkpointed `interrupt()`
- [x] **7. Visuals + new UI**: art-directed Gemini images for every platform; web app rebuilt in Next.js with Framer Motion
- [x] **8. Accounts and publishing**: sign-in, OAuth for LinkedIn / X / Threads / Instagram, publish now or on a schedule
- [x] **9. Calendar and analytics**: drag-to-reschedule calendar, stats from the platforms or typed in, analytics dashboard, best posts and topics feed future runs
- [ ] **10. Deploy**: Docker, Cloud Run + Vercel, LangSmith tracing, rate limits

Medium no longer issues API tokens for new integrations, so Medium stays "export Markdown and import".
YouTube Shorts produces scripts; uploading needs a rendered video file.
