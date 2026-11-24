# Development

```
backend/    FastAPI, SQLAlchemy 2, Alembic, unittest   (Python 3.13)
frontend/   React 19, TypeScript, Vite, TanStack Query, Vitest
e2e/        Playwright end-to-end tests against a running instance
Dockerfile  single image: builds the frontend, serves it and the API (/api) with uvicorn
```

## Backend

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
cd backend
export DATABASE_URL=sqlite:///./habits.db PUBLIC_URL=http://localhost:5173
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.web:application --reload --port 8000   # prints a setup token
```

Tests and checks:

```bash
../.venv/bin/python -m unittest discover -s tests -v
../.venv/bin/ruff check . && ../.venv/bin/ruff format --check .
```

Database changes: edit the models in `app/models/`, then `../.venv/bin/alembic revision --autogenerate -m "…"` and review the generated file in `alembic/versions/`. CI checks that the migrations match the models (`alembic check`).

## Frontend

```bash
cd frontend
npm ci
npm run dev      # http://localhost:5173, proxies /api to the backend on :8000
npm test         # Vitest
npm run lint
npm run build
```

`PUBLIC_URL` must be the address in the browser (`http://localhost:5173` with the Vite dev server), otherwise changes are rejected by the CSRF protection.

## End-to-end tests

Against the built image (like CI):

```bash
docker build -t app:dev .
docker run -d --name app-e2e -p 8000:8000 -e PUBLIC_URL=http://localhost:8000 app:dev
export E2E_SETUP_TOKEN=$(docker logs app-e2e 2>&1 | grep -E '^    [A-Za-z0-9_-]{20,}$' | tail -1 | tr -d ' ')
cd e2e && npm ci && npx playwright install chromium webkit
E2E_BASE_URL=http://localhost:8000 npx playwright test
```

The first run creates the account through the setup page; later runs log in (`E2E_USERNAME`/`E2E_PASSWORD`, defaults in `e2e/global-setup.ts`).

## Conventions

- English for code, comments, docs and commit messages. The interface is German until internationalisation lands (v0.4).
- "Today" always comes from the configured time zone (`app/services/day_service.py`, `frontend/src/lib/dates.ts`), never from the server clock.
- Every change on a day goes through the offline queue (`frontend/src/lib/sync-engine.ts`); the server never silently overwrites a newer state (409 with the server state instead).
