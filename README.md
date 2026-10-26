# teachathon-26-demo

Demo of an adaptive mastery-learning web app (TeachAThon 2026). A professor reviews and approves a
concept graph built from a textbook, and students work through it as a skill-tree map with
auto-graded questions.

**What runs today.** Everything runs on a synthetic 16-section physics course with 33 questions.
No LLM call is made and no book is read. The graph's candidate edges come from mock classifiers.
Bayesian knowledge tracing, mastery gating, the professor difficulty board and real-book ingestion
are not in this repo yet.

- **Student side** (`/`, `/level/:id`): a skill-tree map where locked levels unlock as prerequisites
  are completed, and a level page with one question at a time, hints and instant feedback.
- **Professor side** (`/review`): an evidence panel for each proposed edge, a review queue,
  accept/reject/retype, drag-to-add edges (cycles are refused) and graph approval.
- **Backend**: FastAPI, SQLModel, Alembic, SQLite. Includes an LLM provider layer (OpenRouter, a
  fake provider for tests, a cache and a spend ledger) that the demo does not call.

## Requirements

- Node 20.19 or newer (or 22.12+), and npm
- [uv](https://docs.astral.sh/uv/) (it installs Python 3.11 for you)

## Run it

**Frontend only** (built-in sample levels, progress saved in the browser):

```bash
npm install
npm run dev          # http://localhost:5173
```

**Full demo** (graph from the backend, plus the professor screen). Use three terminals, all from
the repo root:

```bash
# 1. one-time setup: install, create the database, load the sample course
npm install
(cd backend && uv sync && uv run alembic upgrade head)
uv run --project backend python -m backend.seed --mock

# 2. backend on :8000 (pick any admin key)
TA_ADMIN_KEY=demo-key uv run --project backend uvicorn backend.main:app --reload

# 3. frontend on :5173
npm run dev
```

The database is created at `data/app.db`. Delete it and repeat step 1 to reset the demo.

### Try it

1. Open <http://localhost:5173/>. The map shows 16 physics concepts and a banner saying the graph is
   still a draft, because the professor has not approved it.
2. Open <http://localhost:5173/review>. Without a key the screen is read-only. Enter `demo-key` (the
   value you set in `TA_ADMIN_KEY`) to unlock editing.
3. Click an edge to see its evidence from both classifiers. The queue starts with edges where the
   two classifiers disagree.
4. Accept, reject or retype edges. Drag from one node to another to add an edge. Add one that
   closes a loop and it is refused with a message naming the cycle.
5. Click **Approve graph**. The graph is frozen and the student map's banner changes.
6. Back on `/`, click a level to answer its questions. Finishing a level unlocks the next ones.

If the backend is not running, the student map says so and falls back to the sample levels.

## Test it

| Check | Command |
|---|---|
| Frontend unit tests | `npm test` |
| Frontend lint | `npm run lint` |
| Frontend type check and build | `npm run build` |
| Backend tests | `cd backend && uv run pytest` |
| Backend lint and format | `cd backend && uv run ruff check . && uv run ruff format --check .` |
| Browser end-to-end | `scripts/e2e/run.sh` |

`scripts/e2e/run.sh` seeds a scratch database, starts the backend and the dev server, drives the
student map and the whole review flow in headless Chromium, prints PASS/FAIL per check, and shuts
everything down. It needs network access the first time, to download Playwright's browser.
Screenshots go to the directory you pass as the first argument (default `/tmp/ta_e2e_shots`).

Last run on a fresh clone (2026-10-26): 22 frontend tests passed; 136 backend tests passed and 1
was skipped (a live-provider test that needs an API key); the build succeeded; ruff was clean; every
browser check passed. `npm run lint` reports one warning, in `src/context/ProgressContext.tsx`.

## Configuration

Settings come from `TA_*` environment variables or a `.env` file in the repo root.

| Variable | Meaning | Default |
|---|---|---|
| `TA_ADMIN_KEY` | Key for the `X-Admin-Key` header on admin routes. Admin routes are refused if it is unset. | none |
| `TA_DATABASE_URL` | Database URL | `sqlite:///data/app.db` |
| `TA_LLM_BUDGET_USD` | Per-run spend cap for LLM stages | `5.0` |
| `TA_OPENROUTER_MODEL` | Model for the graph pipeline | `anthropic/claude-sonnet-5.5` |
| `OPENROUTER_API_KEY` | Only needed for a real (paid) pipeline run, which the demo does not do | none |

## API

With the backend running, interactive docs are at <http://localhost:8000/docs>.

- Public: `GET /health`, `GET /courses`, `GET /graph`
- Admin (need `X-Admin-Key`): `POST /admin/graph/edges`, `POST /admin/graph/edges/{id}/accept`,
  `POST /admin/graph/edges/{id}/reject`, `PATCH`/`DELETE /admin/graph/edges/{id}`,
  `POST /admin/graph/approve`, `GET /admin/graph/edits`

## Layout

```
src/        React 19 + TypeScript frontend (Vite, @xyflow/react, TanStack Query)
backend/    FastAPI app, models, migrations, graph pipeline, LLM layer, mock data, tests
scripts/    browser end-to-end check
```

The graph command line, for the mock pipeline: `uv run --project backend python -m backend.graph status --course-id 1`
(also `build` and `classify`; `classify` needs `--dry-run` first).
