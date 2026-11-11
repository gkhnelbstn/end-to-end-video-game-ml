# Game Insight

[![CI](https://github.com/gkhnelbstn/end-to-end-video-game-ml/actions/workflows/ci.yml/badge.svg)](https://github.com/gkhnelbstn/end-to-end-video-game-ml/actions/workflows/ci.yml)

A small end-to-end data and ML platform for video games. Celery tasks collect games from
**Steam + SteamSpy** (and optionally **IGDB**) into PostgreSQL, a model predicts a game's
**Metacritic score** from its metadata, **MLflow** tracks every training run and serves the
promoted model through the registry, a FastAPI service exposes data and predictions, and
a Streamlit dashboard browses both. The whole stack starts with one command.

> **Data sources.** The original source, the RAWG API, was unreachable when this was
> written (HTTP 522 from `api.rawg.io` on 2026-11-10). The bundled CSVs in `data/raw` are
> a RAWG snapshot and seed the database; live ingestion now uses Steam + SteamSpy, which
> need no API key. An IGDB client is included and unit-tested against mocked responses,
> but it has **not been run against the live IGDB API yet**.

## Quickstart

Requires Docker with Compose v2.

```bash
git clone https://github.com/gkhnelbstn/end-to-end-video-game-ml.git
cd end-to-end-video-game-ml
docker compose up --build
```

No configuration is needed for a first run. On an empty database the stack loads a
bundled sample of about 16,500 games (`data/raw/games.csv`), which takes a few minutes.
Then the one-shot `train` service trains the first Metacritic model, logs it to MLflow and
promotes it to `champion`; from then on the API serves predictions.

| What | URL |
| --- | --- |
| Dashboard (Streamlit) | http://localhost:8501 |
| API docs (Swagger UI) | http://localhost:8000/docs |
| Admin panel (SQLAdmin), `admin` / `adminpass` | http://localhost:8000/admin |
| Scheduled-task manager | http://localhost:8000/task-management |
| Flower (Celery monitoring) | http://localhost:5555 |
| MLflow (runs, model registry) | http://localhost:5000 |

To change ports, credentials or secrets, copy `.env.example` to `.env` and edit it.
The defaults are for local development only: change `SECRET_KEY`, `ADMIN_PASSWORD` and
the database password before exposing the stack anywhere.

The repository is large to clone (about 500 MB of CSV exports under `data/raw`).

### Data sources and keys

| Source | Key needed | What it adds | Scheduled by default |
| --- | --- | --- | --- |
| Bundled CSVs (RAWG snapshot) | no | ~16,500 games seeded on first start (~139,000 in all CSVs) | one-shot `seed` |
| Steam store + SteamSpy | no | name, release date, genres, platforms (PC/macOS/Linux), Metacritic score, image, Steam categories; SteamSpy adds community tags | Mondays: newest releases and top sellers (100 each) |
| IGDB | yes (Twitch app) | every platform, IGDB critic average (`critic_rating`), cover, trailer | 1st of the month, only when credentials are set |
| RAWG API | yes | legacy client, kept working in code | only when `RAWG_API_KEY` is set |

Steam allows roughly 200 app-detail requests per 5 minutes, so the client pauses 1.5 s
between calls (`STEAM_REQUEST_INTERVAL`); in testing, 20 games took about 3 minutes.
SteamSpy is often overloaded; when it fails, the game is saved without SteamSpy tags.

**IGDB credentials.** Register an application in the
[Twitch developer console](https://dev.twitch.tv/console/apps) (see the
[IGDB guide](https://api-docs.igdb.com/#account-creation)), then put the client id and
secret in `.env` (git-ignored; never commit real credentials) and restart:

```bash
cp .env.example .env
# set IGDB_CLIENT_ID=... and IGDB_CLIENT_SECRET=... in .env
docker compose up -d
```

IGDB's `aggregated_rating` is an average of critic reviews, not a Metacritic score, so it
is stored in its own `critic_rating` column and is not used as a training label.

**One game, several sources.** Each source's id is stored (`steam_appid`, `igdb_id`; RAWG
ids are the row ids). An incoming game is matched by its source id, then by slug or exact
name with the same release year. A match from the same source is refreshed; a match from
another source only fills empty fields and adds genres, platforms and tags, so one source
never overwrites another. Games and look-up rows created by Steam or IGDB get ids from
100,000,000 up so they cannot collide with RAWG ids.

## Architecture

```mermaid
flowchart LR
    STEAM[Steam + SteamSpy] -->|httpx| W[Celery worker]
    IGDB[IGDB, optional] -->|httpx| W
    CSV[(data/raw/*.csv)] -->|seed script| DB
    B[FastAPI backend<br/>+ APScheduler] -->|enqueue tasks| R[(Redis)]
    R --> W
    W -->|SQLAlchemy| DB[(PostgreSQL)]
    W -->|train: runs, metrics,<br/>model versions| M[MLflow server]
    B -->|load champion model| M
    M -->|backend store| DB
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
| `mlflow` | MLflow tracking server and model registry. Metadata in an `mlflow` database on the same Postgres server, artifacts in the `mlflow_artifacts` volume, served over HTTP. |
| `train` | One-shot: trains the Metacritic model after `seed` and registers it (see [Machine learning](#machine-learning)). |
| `backend` | FastAPI app: REST API, predictions, SQLAdmin panel, and an in-process APScheduler that enqueues the periodic Celery tasks. |
| `worker` | Celery worker: ingestion (Steam, IGDB, RAWG) and scheduled retraining. |
| `flower` | Celery monitoring UI. |
| `frontend` | Streamlit dashboard; talks only to the backend API. |
| `backfill` | Opt-in (`--profile backfill`): queues ingestion for a range of years. |

`backend`, `worker`, `flower`, `migrate`, `seed` and `train` share one image
(`Dockerfile`, target `app`); the dashboard (target `frontend`) and MLflow (target
`mlflow`) have their own. All are multi-stage builds that install the locked dependencies
with uv and run as a non-root user.

### Data flow

- **Scheduled jobs** (backend's APScheduler, defaults in `src/backend/task_scheduler.py`):
  Steam newest releases and top sellers every Monday, model retraining every Monday
  afterwards, IGDB last month's releases on the 1st (only with credentials), RAWG jobs
  only with a RAWG key. Schedules live in memory: changes made through the task manager
  are lost when the backend restarts, and the defaults are recreated.
- **Manual runs.** Any task can be run, paused or edited from `/task-management` or the
  `/api/tasks/...` endpoints, for example
  `POST /api/tasks/run/src.worker.tasks.fetch_steam_games_task` with
  `{"list_name": "new", "limit": 50}` (lists: `topsellers`, `new`, `top_rated`).
- **Bulk loads.** `seed` imports the RAWG CSV snapshot; `backfill` queues one RAWG fetch
  per month for a range of years (needs a working RAWG API).

### Database

Defined in `src/backend/models.py`, migrated with Alembic (`src/backend/alembic`):

- `games` with many-to-many links to `genres`, `platforms`, `stores` and `tags`; RAWG
  rows keep RAWG's ids, `steam_appid` and `igdb_id` link rows to the other sources
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
| `GET /api/games/{id}/predicted-metacritic` | The champion model's prediction for a stored game, next to its actual score. |
| `POST /api/predictions/metacritic` | Prediction for a hypothetical game: `{"release_year": 2025, "genres": ["RPG"], "platforms": ["PC"], "tags": ["Singleplayer"]}`. |
| `GET /api/ml/model`, `POST /api/ml/reload` | Which model version is served and its metrics; re-check the `champion` alias now. |
| `POST /api/users`, `POST /api/auth/login` | Register and log in (dashboard accounts). |
| `GET/POST /api/users/{id}/favorites[/{game_id}]` | Favorite games. |
| `/api/tasks/...` | Inspect workers, run Celery tasks, manage scheduled tasks. |

Full, interactive reference: http://localhost:8000/docs.

**Limitations to know about.** Dashboard login is demo-grade: after login the dashboard
identifies the user with an `X-User-Id` header, and there are no tokens or sessions. The
`/api/tasks/...` endpoints are unauthenticated. This is fine on a laptop and not suitable
for a public deployment as is.

## Machine learning

**Task.** Predict a game's Metacritic score (0 to 100) from what is known before reviews
come in: release year, genres, platforms and tags. Labels are the games in the database
that have a Metacritic score (5,116 of the 16,520 seeded games; Steam adds more).
User ratings, ratings counts and playtime are deliberately not used: they are only known
after release, and Steam and IGDB rows do not have them.

**Pipeline** (`src/ml`):

- `features.py`: one-hot genres, platforms and tags, their counts, and the release year
  (with a missing-year flag); indicators present in fewer than ~0.5% of games are dropped.
- `train.py`: holds out ~20% of games as a test set chosen by a hash of the game id (a
  game never moves between train and test as data grows, so model versions are compared
  fairly), compares a mean-score baseline, Ridge regression and histogram gradient
  boosting by 5-fold cross-validated MAE, refits the best on the training part and scores
  it on the test set.
- `serving.py`: the API loads `models:/metacritic-predictor@champion` lazily and re-checks
  the alias every 60 seconds (`MODEL_REFRESH_SECONDS`), so a newly promoted version is
  served without a restart. Without a model, prediction endpoints answer 503.
- Dashboard: each game's details show the predicted next to the actual score, and the
  **Score Predictor** page shows the served model's metrics and predicts a score for any
  combination of year, genres, platforms and tags.

**What MLflow records for every training run** (experiment `metacritic-prediction`):
one parent run with dataset size per source, the logged training dataset, the best
model's CV and test metrics (MAE, RMSE, R²), the baseline's test MAE, permutation
importance per input, the 25 largest test errors (`largest_test_errors.csv`), and one
nested run per candidate. The best model is logged with its signature and an input
example and registered as a new version of `metacritic-predictor`. The `champion` alias
moves to it only if it beats both the baseline and the current champion on the same test
set; otherwise it stays registered with the tag `promoted=false`.

**Results** on the seeded sample (`data/raw/games.csv`; 4,099 training and 1,017 test
games), from `notebooks/metacritic-analysis.ipynb`:

| Model | CV MAE | Test MAE | Test R² |
| --- | --- | --- | --- |
| Mean baseline | 8.62 | 8.28 | 0.00 |
| Ridge | 7.79 | 7.69 | 0.13 |
| Histogram gradient boosting (selected) | 7.23 | 7.13 | 0.23 |

The model is 14% better than always guessing the mean, but metadata explains only a small
part of the score: it is off by about 7 points on average and pulls extreme scores toward
the middle (games scored above 90 are under-predicted by about 13 points). Tags are the
most informative input, then platforms and release year.

![Predicted vs actual Metacritic on held-out games](reports/figures/predicted_vs_actual.png)

The [analysis notebook](notebooks/metacritic-analysis.ipynb) also covers score coverage
by year, the score distribution, genre and tag associations, and permutation importance
(figures in `reports/figures`). Re-run it with:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/metacritic-analysis.ipynb
```

**Retraining.** Every Monday after the Steam ingestion, from the task manager
(`train_metacritic_model`), or by hand:

```bash
docker compose run --rm train
```

Every `docker compose up` also runs `train` once, so each start registers a new model
version; on unchanged data it is not promoted and the champion stays as it was.

Training outside Docker works too; point it at the stack's database and MLflow:

```bash
DATABASE_URL=postgresql+psycopg://game_insight:game_insight@127.0.0.1:5433/game_insight \
MLFLOW_TRACKING_URI=http://localhost:5000 uv run python -m src.ml.train
```

## Common tasks

```bash
# Load every bundled CSV (about 139,000 games; takes a while)
docker compose run --rm seed python -m src.scripts.seed_from_csv

# Fetch 50 of the newest Steam releases now
curl -X POST http://localhost:8000/api/tasks/run/src.worker.tasks.fetch_steam_games_task \
  -H "Content-Type: application/json" -d '{"list_name": "new", "limit": 50}'

# Retrain the model (promoted only if it is better)
docker compose run --rm train

# Create another admin panel account
docker compose exec backend python -m src.backend.create_admin

# Create a migration after changing the models, then apply it
docker compose run --rm -v ./src:/app/src migrate \
  alembic -c src/backend/alembic.ini revision --autogenerate -m "describe the change"
docker compose up -d --build

# Back up / restore the database
docker compose exec -T db pg_dump -U game_insight game_insight > backup.sql
docker compose exec -T db psql -U game_insight game_insight < backup.sql

# Stop the stack (data is kept). Add -v to also delete the database and MLflow volumes.
docker compose down
```

## Development

Requires [uv](https://docs.astral.sh/uv/); it installs Python 3.12 if needed.

```bash
uv sync                      # create .venv from uv.lock
uv run pytest                # API, worker, source-client and ML tests (no services needed)
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

The tests mock all HTTP calls (Steam, SteamSpy, IGDB, RAWG) and train real models against
a throwaway SQLite-backed MLflow, so they need no network or services.

CI (GitHub Actions) runs ruff, the test suite against a PostgreSQL service, and a
`docker compose` end-to-end check on every push and pull request: it starts the stack,
seeds the 2000 to 2004 CSVs, trains and registers a model in the MLflow service, and
calls the prediction endpoints.

### Project layout

```
├── compose.yaml            # the whole stack
├── Dockerfile              # multi-stage; targets: app, frontend, mlflow
├── pyproject.toml, uv.lock # dependencies (uv)
├── data/raw/               # RAWG CSV snapshot used by the seed script
├── notebooks/              # metacritic-analysis.ipynb, plus early exploration notebooks
├── reports/figures/        # figures written by the analysis notebook
├── src/
│   ├── backend/            # FastAPI app, models, Alembic migrations, admin, scheduler
│   ├── worker/             # Celery tasks; sources/ has the Steam, IGDB clients; RAWG client
│   ├── ml/                 # features, training with MLflow, model serving
│   ├── frontend/           # Streamlit dashboard
│   └── scripts/            # seed_from_csv.py, backfill_data.py, ensure_database.py
└── tests/
```

## Roadmap

- Verify the IGDB client against the live API.
- Richer model inputs: descriptions, developer and publisher history, pre-release signals.
- Real authentication (tokens) for the dashboard and the task endpoints.
- Persistent schedules for the task manager.

## License

MIT. See [LICENSE](LICENSE). Game data comes from [RAWG](https://rawg.io) (the CSV
snapshot), [Steam](https://store.steampowered.com), [SteamSpy](https://steamspy.com) and
optionally [IGDB](https://www.igdb.com); check their terms of use before redistributing it.
