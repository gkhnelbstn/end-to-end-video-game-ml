# Game Insight

[![CI](https://github.com/gkhnelbstn/end-to-end-video-game-ml/actions/workflows/ci.yml/badge.svg)](https://github.com/gkhnelbstn/end-to-end-video-game-ml/actions/workflows/ci.yml)

A small data platform for video game data. Celery tasks pull games from the
[RAWG API](https://rawg.io/apidocs) into PostgreSQL, a FastAPI service exposes the data
(search, filters, statistics, scheduled-task control), and a Streamlit dashboard browses it.
The whole stack starts with one command.

> **Status.** The data pipeline, API, admin panel and dashboard work and are tested.
> The machine-learning part (predicting ratings from the collected data) is **not
> implemented yet**; it is on the [roadmap](#roadmap).

## Quickstart

Requires Docker with Compose v2.

```bash
git clone https://github.com/gkhnelbstn/end-to-end-video-game-ml.git
cd end-to-end-video-game-ml
docker compose up --build
```

No configuration is needed for a first run. On an empty database the stack loads a
bundled sample of about 16,500 games (`data/raw/games.csv`) in the background, which takes
a few minutes; the dashboard is usable while it loads.

| What | URL |
| --- | --- |
| Dashboard (Streamlit) | http://localhost:8501 |
| API docs (Swagger UI) | http://localhost:8000/docs |
| Admin panel (SQLAdmin), `admin` / `adminpass` | http://localhost:8000/admin |
| Scheduled-task manager | http://localhost:8000/task-management |
| Flower (Celery monitoring) | http://localhost:5555 |

To change ports, credentials or secrets, copy `.env.example` to `.env` and edit it.
The defaults are for local development only: change `SECRET_KEY`, `ADMIN_PASSWORD` and
the database password before exposing the stack anywhere.

The repository is large to clone (about 500 MB of CSV exports under `data/raw`).

### Getting a RAWG API key

Live ingestion from RAWG needs an API key. Browsing the bundled sample does not.

1. Create a free account at [rawg.io](https://rawg.io/signup).
2. Request a key on the [API page](https://rawg.io/apidocs).
3. Put it in `.env` (git-ignored; never commit a real key):

   ```bash
   cp .env.example .env
   # then set RAWG_API_KEY=<your key> in .env
   docker compose up -d
   ```

Without a key the fetch tasks fail with a clear `RAWG_API_KEY is not set` error and
everything else keeps working.

## Architecture

```mermaid
flowchart LR
    RAWG[RAWG API] -->|httpx| W[Celery worker]
    CSV[(data/raw/*.csv)] -->|seed script| DB
    B[FastAPI backend<br/>+ APScheduler] -->|enqueue tasks| R[(Redis)]
    R --> W
    W -->|SQLAlchemy| DB[(PostgreSQL)]
    B -->|SQLAlchemy| DB
    F[Streamlit dashboard] -->|HTTP| B
    FL[Flower] --> R
```

| Compose service | Role |
| --- | --- |
| `db` | PostgreSQL 17. Data persists in the `postgres_data` volume. |
| `redis` | Celery broker and result backend. |
| `migrate` | One-shot: runs `alembic upgrade head`, then exits. |
| `seed` | One-shot: loads `data/raw/games.csv` if the `games` table is empty. |
| `backend` | FastAPI app: REST API, SQLAdmin panel, and an in-process APScheduler that enqueues the periodic Celery tasks. |
| `worker` | Celery worker that runs the RAWG ingestion tasks. |
| `flower` | Celery monitoring UI. |
| `frontend` | Streamlit dashboard; talks only to the backend API. |
| `backfill` | Opt-in (`--profile backfill`): queues ingestion for a range of years. |

`backend`, `worker`, `flower`, `migrate` and `seed` share one image (`Dockerfile`, target
`app`); the dashboard has its own (target `frontend`). Both are multi-stage builds that
install the locked dependencies with uv and run as a non-root user.

### Data flow

- **Scheduled ingestion.** The backend's scheduler enqueues `fetch_weekly_updates_task`
  every Monday (games updated in the last 7 days; existing rows are refreshed) and
  `fetch_monthly_updates_task` on the 1st of each month (games released in the previous
  month). Schedules live in memory: changes made through the task manager are lost when
  the backend restarts, and the two defaults are recreated.
- **Manual runs.** Any scheduled task can be run, paused or edited from
  `/task-management` or the `/api/tasks/...` endpoints.
- **Bulk loads.** `seed` imports RAWG CSV exports; `backfill` queues one RAWG fetch per
  month for a range of years.

### Database

Defined in `src/backend/models.py`, migrated with Alembic (`src/backend/alembic`):

- `games` with many-to-many links to `genres`, `platforms`, `stores` and `tags`
  (ids are RAWG's ids)
- `users` and their `user_favorite_games`
- `admin_users` for the admin panel

A test (`tests/test_migrations.py`) fails CI if the migrations and the models drift apart.

### API overview

| Endpoint | Purpose |
| --- | --- |
| `GET /api/games` | List games. Query: `search`, `genre`, `platform` (slugs), `rating` (minimum), `sort_by` (`name`, `released`, `rating`, `metacritic`), `sort_order`, `skip`, `limit`. |
| `GET /api/games/{id}` | One game with genres, platforms, stores and tags. |
| `GET /api/genres`, `GET /api/platforms` | Filter options. |
| `GET /api/stats/...` | `games-per-year`, `avg-rating-by-genre`, `rating-distribution`, `top-genres`, `top-platforms`. |
| `POST /api/users`, `POST /api/auth/login` | Register and log in (dashboard accounts). |
| `GET/POST /api/users/{id}/favorites[/{game_id}]` | Favorite games. |
| `/api/tasks/...` | Inspect workers, run Celery tasks, manage scheduled tasks. |

Full, interactive reference: http://localhost:8000/docs.

**Limitations to know about.** Dashboard login is demo-grade: after login the dashboard
identifies the user with an `X-User-Id` header, and there are no tokens or sessions. The
`/api/tasks/...` endpoints are unauthenticated. This is fine on a laptop and not suitable
for a public deployment as is.

## Common tasks

```bash
# Load every bundled CSV (about 139,000 games; takes a while)
docker compose run --rm seed python -m src.scripts.seed_from_csv

# Queue RAWG ingestion for a range of years (needs RAWG_API_KEY)
docker compose --profile backfill run --rm backfill 2023 2024

# Create another admin panel account
docker compose exec backend python -m src.backend.create_admin

# Create a migration after changing the models, then apply it
docker compose run --rm -v ./src:/app/src migrate \
  alembic -c src/backend/alembic.ini revision --autogenerate -m "describe the change"
docker compose up -d --build

# Back up / restore the database
docker compose exec -T db pg_dump -U game_insight game_insight > backup.sql
docker compose exec -T db psql -U game_insight game_insight < backup.sql

# Stop the stack (data is kept). Add -v to also delete the database volume.
docker compose down
```

## Development

Requires [uv](https://docs.astral.sh/uv/); it installs Python 3.12 if needed.

```bash
uv sync                      # create .venv from uv.lock
uv run pytest                # API and worker tests (SQLite, no services needed)
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pre-commit install    # run ruff on every commit
```

The migration test needs PostgreSQL and is skipped unless `TEST_DATABASE_URL` is set.
It wipes the database it is pointed at, so give it a scratch one:

```bash
docker compose up -d db
docker compose exec db createdb -U game_insight scratch
TEST_DATABASE_URL=postgresql+psycopg://game_insight:game_insight@127.0.0.1:5433/scratch uv run pytest
```

CI (GitHub Actions) runs ruff, the test suite against a PostgreSQL service, and a
`docker compose up` smoke test on every push and pull request.

### Project layout

```
├── compose.yaml            # the whole stack
├── Dockerfile              # multi-stage; targets: app, frontend
├── pyproject.toml, uv.lock # dependencies (uv)
├── data/raw/               # RAWG CSV exports used by the seed script
├── notebooks/              # early exploration notebooks (not part of the stack)
├── src/
│   ├── backend/            # FastAPI app, models, Alembic migrations, admin, scheduler
│   ├── worker/             # Celery tasks and the RAWG client
│   ├── frontend/           # Streamlit dashboard
│   └── scripts/            # seed_from_csv.py, backfill_data.py
└── tests/
```

## Roadmap

- Feature preparation and a first model that predicts a game's rating or Metacritic score
  from the collected data; experiment tracking; a prediction endpoint and dashboard view.
- Real authentication (tokens) for the dashboard and the task endpoints.
- Persistent schedules for the task manager.

## License

MIT. See [LICENSE](LICENSE). Game data comes from [RAWG](https://rawg.io); check their
terms of use before redistributing it.
