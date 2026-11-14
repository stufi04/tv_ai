# Episode Generator

Pick a popular TV show and get a brand-new episode, or pick two for a crossover. The story is written
by Google Gemini and illustrated with a generated image.

```
backend/    FastAPI + Pydantic API that talks to Gemini (also hosts the pytest suite)
frontend/   React 19 + TypeScript + Vite single-page app
```

## Quick start

Prerequisites: Python 3.12+, Node.js 22.12+, and a free Gemini API key from
[Google AI Studio](https://aistudio.google.com/apikey).

### Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then paste your GEMINI_API_KEY into .env
fastapi dev app/main.py       # http://localhost:8000, docs at /docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to the backend)
```

### Single-process mode

Build the frontend and let FastAPI serve it:

```bash
cd frontend && npm run build
cd ../backend && FRONTEND_DIST=../frontend/dist fastapi run app/main.py   # http://localhost:8000
```

## Configuration

Set these in `backend/.env` or as environment variables:

| Variable             | Default                  | Purpose                                         |
| -------------------- | ------------------------ | ----------------------------------------------- |
| `GEMINI_API_KEY`     | (none)                   | Required for generating episodes.               |
| `GEMINI_TEXT_MODEL`  | `gemini-2.5-flash`       | Model that writes the story.                    |
| `GEMINI_IMAGE_MODEL` | `gemini-2.5-flash-image` | Model that draws the illustration.              |
| `GENERATE_IMAGES`    | `true`                   | Turn image generation off entirely.             |
| `FRONTEND_DIST`      | (none)                   | Serve a built frontend from this directory.     |

**Free tier caveat:** Gemini's free tier covers the Flash text models, but image generation quota on
free projects is limited or zero, depending on the model and region. The image step is therefore
best-effort. If it fails, you still get the story, and the UI says there is no illustration.
Rate-limit errors from the text model come back as HTTP 429 with a friendly message.

## API

| Method | Path            | Description                                                    |
| ------ | --------------- | -------------------------------------------------------------- |
| GET    | `/api/health`   | Liveness check.                                                |
| GET    | `/api/shows`    | All shows in the catalogue, sorted by title.                   |
| POST   | `/api/episodes` | Body `{"showIds": ["the-office", "stranger-things"]}` (1 or 2 ids). |

`POST /api/episodes` returns `{showIds, title, logline, story, imageDataUrl}`. Errors:
`404` unknown show, `422` invalid selection, `429` Gemini rate limit, `502` Gemini failure,
`503` missing API key.

## Tests

All tests run with pytest from `backend/`. Gemini is replaced with a deterministic fake, so tests need
no API key or network.

```bash
cd backend
playwright install chromium   # once
pytest                        # everything
pytest -m "not e2e"           # skip the browser tests
pytest -m e2e --headed        # watch the browser tests run
```

- `tests/test_api.py`: end-to-end HTTP tests of the API.
- `tests/test_episode_generator.py`: the Gemini integration (prompting, image fallback, error mapping)
  against a stubbed client.
- `tests/e2e/`: Playwright browser tests. They build the frontend, serve it from the real FastAPI app
  and click through the user journeys. They need Node.js on the `PATH`.

Linting: `ruff check . && ruff format --check .` in `backend/`, and `npm run lint` in `frontend/`.
CI runs everything (`.github/workflows/ci.yml`).

## Design notes

- **Show catalogue**: a curated JSON file (`backend/app/data/shows.json`). It is static, fast and
  testable. The `ShowCatalog` class is the seam for swapping in a live source such as the TVMaze API.
  The list is small, so search and genre filtering happen on the client.
- **Gemini integration**: `GeminiEpisodeGenerator` asks the text model for structured JSON (validated
  against the `EpisodeDraft` Pydantic model) containing the story and a scene description. The scene
  description is then passed to the image model. The API depends on an `EpisodeGenerator` protocol,
  so tests swap in a fake through FastAPI dependency overrides.
- **API models** use snake_case in Python and camelCase in JSON (Pydantic alias generator).
- **Frontend**: TanStack Query manages server state (`useShows`, `useGenerateEpisode`).
  `useShowSelection` holds the "at most two shows" rule. Components are presentational.
