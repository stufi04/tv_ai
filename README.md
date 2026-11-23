# Episode Generator

Pick a TV show and get a brand-new episode, or pick two for a crossover. The story is written by an
open-weight LLM running on [Groq](https://groq.com). Show data comes from [TVmaze](https://www.tvmaze.com)
(CC BY-SA).

```
backend/    FastAPI + Pydantic API that talks to Groq (also hosts the pytest suite)
frontend/   React 19 + TypeScript + Vite single-page app
```

## Quick start

Prerequisites: Python 3.12+, Node.js 22.12+, and a free Groq API key from
[console.groq.com/keys](https://console.groq.com/keys).

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then paste your GROQ_API_KEY into .env
fastapi dev app/main.py       # http://localhost:8000, docs at /docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to the backend)
```

### Both at once

After the setup above, `./dev.sh` from the repo root starts the backend and frontend together. Ctrl+C stops both.

### Single-process mode

Build the frontend and let FastAPI serve it:

```bash
cd frontend && npm run build
cd ../backend && FRONTEND_DIST=../frontend/dist fastapi run app/main.py   # http://localhost:8000
```

## Configuration

Set these in `backend/.env` or as environment variables:

| Variable                | Default                     | Purpose                                                           |
| ----------------------- | --------------------------- | ----------------------------------------------------------------- |
| `GROQ_API_KEY`          | (none)                      | Required for generating episodes.                                 |
| `GROQ_MODEL`            | `openai/gpt-oss-120b`       | Model that writes the story.                                      |
| `GROQ_FALLBACK_MODELS`  | `openai/gpt-oss-20b`        | Tried in order when the main model is rate limited, busy or slow. |
| `FRONTEND_DIST`         | (none)                      | Serve a built frontend from this directory.                       |
| `CATALOG_CACHE_PATH`    | `backend/.cache/shows.json` | Where the downloaded TVmaze catalogue is cached.                  |
| `CATALOG_MAX_AGE_HOURS` | `168` (one week)            | Refresh the cache in the background after this.                   |
| `SYNC_CATALOG`          | `true`                      | Set to `false` to use only the cache and never contact TVmaze.    |

**First run:** the backend downloads the TVmaze show index (about 3 minutes) in the background and caches
it. The page says so meanwhile. Later starts load the cache instantly.

**Free tier:** Groq's free tier has per-minute and per-day request limits per model (see your limits at
[console.groq.com/settings/limits](https://console.groq.com/settings/limits)). When a model is rate limited
the next model in the chain is tried; if all are, the API returns HTTP 429 with a friendly message.

## API

| Method | Path            | Description                                                    |
| ------ | --------------- | -------------------------------------------------------------- |
| GET    | `/api/health`   | Liveness check.                                                |
| GET    | `/api/shows`    | A page of shows. Query: `q`, `genre`, `offset`, `limit` (max 100), `seed`. Returns `{items, total, nextOffset, syncing}`. |
| GET    | `/api/genres`   | All genres in the catalogue.                                   |
| POST   | `/api/episodes` | Body `{"showIds": ["the-office", "stranger-things"]}` (1 or 2 ids). |

`POST /api/episodes` returns `{showIds, title, logline, story}`. Errors:
`404` unknown show, `422` invalid selection, `429` Groq rate limit on every model, `502` Groq failure,
`503` missing API key.

## Tests

All tests run with pytest from `backend/`. The LLM is replaced with a deterministic fake, so tests need
no API key or network.

```bash
cd backend
playwright install chromium   # once
pytest                        # everything
pytest -m "not e2e"           # skip the browser tests
pytest -m e2e --headed        # watch the browser tests run
```

- `tests/test_api.py`: end-to-end HTTP tests of the API, served from a fixture catalogue.
- `tests/test_catalog.py`: search ranking, the seeded "discover" order, genre filtering and paging.
- `tests/test_tvmaze.py`: mapping TVmaze data, paged download with retries (via `httpx.MockTransport`),
  and the cache store (first run, fresh cache, stale cache, failed refresh).
- `tests/test_episode_generator.py`: the Groq integration (prompt, JSON schema, model fallback, error
  mapping) against a fake Groq API (`httpx.MockTransport`).
- `tests/e2e/`: Playwright browser tests. They build the frontend, serve it from the real FastAPI app
  and click through the user journeys. They need Node.js on the `PATH`.

Linting: `ruff check . && ruff format --check .` in `backend/`, and `npm run lint` in `frontend/`.
CI runs everything (`.github/workflows/ci.yml`).

## Design notes

- **Show catalogue**: TVmaze's search API returns at most 10 results, which can't drive full search with
  infinite scroll. So `TvmazeClient` downloads the whole paged show index (~384 pages, paced under TVmaze's
  rate limit), drops shows without a summary or popularity, and `CatalogStore` caches the result to disk.
  On startup the cache loads immediately. Its age is checked at startup and then hourly; once it is
  missing or older than a week, a background task re-downloads it and swaps it in while the old copy keeps
  being served. A failed refresh is retried at the next hourly check. (An incremental refresh via
  `/updates/shows` is not worth it: a typical week touches ~1,500 shows spread across most index pages.)
- **Browsing**: `ShowCatalog.search` runs server-side. With no search term it returns popular shows
  (TVmaze weight ≥ 90) shuffled by a per-page-load `seed`, then everything else by popularity. With a
  term it ranks exact title matches (ignoring a leading "The"), then prefix, word and substring matches,
  then network matches, breaking ties by popularity. Results are paged (`offset`/`limit`) for infinite
  scroll. Tests use the small fixture `backend/tests/data/shows.json` and never touch the network.
- **LLM integration**: `GroqEpisodeGenerator` calls Groq's OpenAI-compatible chat completions API with
  plain `httpx` and a JSON schema (`response_format: json_schema`, built from the `EpisodeDraft` Pydantic
  model), then validates the reply. The API depends on an `EpisodeGenerator` protocol, so tests swap in a
  fake through FastAPI dependency overrides. The request walks a fallback chain (`GROQ_MODEL`, then
  `GROQ_FALLBACK_MODELS`): a rate-limited (429), over-capacity (498), failing (5xx), timed-out (30 s) or
  unparseable model hands over to the next. Errors another model won't fix (bad request, unknown model,
  bad key) fail immediately. Gemini was used originally but was dropped: its free tier was answering
  most requests with 503 "high demand" for days.
- **API models** use snake_case in Python and camelCase in JSON (Pydantic alias generator).
- **Frontend**: TanStack Query manages server state (`useShows` is an infinite query keyed on search,
  genre and seed; `useGenerateEpisode`). `useShowSelection` keeps the selected shows themselves, so a
  selection survives a new search, and holds the "at most two shows" rule. Components are presentational.
