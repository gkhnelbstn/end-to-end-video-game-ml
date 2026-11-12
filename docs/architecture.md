# How Game Insight works

This page follows the system from the outside in: what runs where, how the stack
starts, how games get into the database, how the model is trained and served, how a page
of the dashboard is put together, and how sign-in works. The diagrams are Mermaid and
render on GitHub. Names in `code` are the real services, files and functions.

- [1. The pieces](#1-the-pieces)
- [2. Starting the stack](#2-starting-the-stack)
- [3. Getting games in](#3-getting-games-in)
- [4. One game, several sources](#4-one-game-several-sources)
- [5. Training a model](#5-training-a-model)
- [6. Serving estimates in the product](#6-serving-estimates-in-the-product)
- [7. Signing in](#7-signing-in)
- [8. The database](#8-the-database)
- [9. Tests and CI](#9-tests-and-ci)

## 1. The pieces

Everything runs in Docker Compose (`compose.yaml`). The browser only ever talks to the
dashboard's nginx on one origin; nginx forwards `/api` to FastAPI and `/auth` to Rauthy.
Ports are the defaults on the host.

```mermaid
flowchart TB
    subgraph browser["Browser"]
        UI["React dashboard<br/>(Vite build)"]
    end

    subgraph edge["frontend · :8080"]
        NGINX["nginx<br/>static files, /api and /auth proxy"]
    end

    subgraph app["Application"]
        API["backend · :8000<br/>FastAPI, SQLAdmin,<br/>APScheduler"]
        WORKER["worker<br/>Celery tasks"]
        FLOWER["flower · :5555"]
    end

    subgraph identity["Identity"]
        RAUTHY["rauthy<br/>OpenID Connect"]
        MAIL["mailcrab · :8025"]
    end

    subgraph data["Data"]
        PG[("db · Postgres 17<br/>game_insight + mlflow")]
        REDIS[("redis<br/>broker + results")]
    end

    subgraph ml["Machine learning"]
        MLFLOW["mlflow · :5000<br/>runs + model registry"]
        ART[("mlflow_artifacts<br/>volume")]
    end

    subgraph outside["Outside sources"]
        STEAM["Steam + SteamSpy"]
        IGDB["IGDB (optional)"]
    end

    UI --> NGINX
    NGINX -->|/api| API
    NGINX -->|/auth| RAUTHY
    API -->|signing keys| RAUTHY
    RAUTHY -->|registration mail| MAIL
    API -->|SQLAlchemy| PG
    API -->|enqueue| REDIS
    REDIS --> WORKER
    FLOWER --> REDIS
    WORKER -->|SQLAlchemy| PG
    WORKER -->|httpx| STEAM
    WORKER -->|httpx| IGDB
    WORKER -->|log runs, register models| MLFLOW
    API -->|load champion| MLFLOW
    MLFLOW --> PG
    MLFLOW --> ART
```

| Piece | Code | Job |
| --- | --- | --- |
| Dashboard | `frontend/src` | Browse games, read estimates, save favourites, estimate an unreleased game. |
| API | `src/backend/main.py` | Games, stats, predictions, favourites, task management, admin panel. |
| Scheduler | `src/backend/task_scheduler.py` | Runs inside the API process and puts periodic jobs on the Celery queue. |
| Worker | `src/worker/tasks.py`, `src/worker/sources/` | Fetches games from Steam, SteamSpy and IGDB; trains the model on schedule. |
| Model code | `src/ml/` | Features, training with MLflow, loading the champion for the API. |
| Identity | Rauthy, `deploy/rauthy/clients.json`, `src/backend/auth.py` | Accounts, sign-in, registration; the API checks its tokens. |

## 2. Starting the stack

`docker compose up --build` brings everything up in dependency order. Four services are
one-shots: they do one job and exit, and the services after them wait for success.

```mermaid
flowchart TD
    db[("db")] --> migrate["migrate<br/>alembic upgrade head"]
    migrate --> seed["seed<br/>load data/raw/games.csv<br/>if games is empty"]
    db --> mlflow["mlflow"]
    seed --> train["train<br/>fit, log, register,<br/>promote if better"]
    mlflow --> train
    migrate --> backend["backend"]
    redis[("redis")] --> backend
    mlflow --> backend
    migrate --> worker["worker"]
    redis --> worker
    bootstrap["rauthy-bootstrap<br/>write clients.json<br/>with FRONTEND_PORT"] --> rauthy["rauthy"]
    mailcrab["mailcrab"] --> rauthy
    backend --> frontend["frontend"]
    rauthy --> frontend

    classDef once fill:#fff3d6,stroke:#c68b0f,color:#131a2b
    class migrate,seed,train,bootstrap once
```

On a second start the one-shots run again but find nothing to do: migrations are
applied, the `games` table is not empty, and a retrained model on unchanged data is
registered but not promoted. Rauthy reads its bootstrap files only when its own
database is empty.

## 3. Getting games in

There are three ways in. The bundled CSV snapshot seeds an empty database. Scheduled
jobs fetch new games every week (Steam) and month (IGDB). Any job can also be run by
hand from `/task-management`.

```mermaid
sequenceDiagram
    autonumber
    participant S as APScheduler<br/>(in backend)
    participant R as Redis
    participant W as Celery worker
    participant ST as Steam store
    participant SS as SteamSpy
    participant DB as Postgres

    Note over S: Monday 00:00 and 01:00:<br/>newest releases, top sellers
    S->>R: fetch_steam_games_task(list_name, limit)
    R->>W: deliver task
    W->>ST: list + app details (1.5 s apart)
    W->>SS: community tags
    Note right of SS: often overloaded, then<br/>the game is saved without tags
    W->>DB: upsert each game (see section 4)
    Note over S: Monday 03:00
    S->>R: train_metacritic_model_task
    R->>W: deliver task
    W->>DB: games with a Metacritic score
    W-->>W: train (see section 5)
```

| Job | When | Needs |
| --- | --- | --- |
| Steam newest releases, top sellers | Mondays 00:00, 01:00 | nothing |
| Retrain the model | Mondays 03:00 | nothing |
| IGDB last month's releases | 1st of the month, 00:30 | `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` |
| RAWG weekly and monthly updates | Mondays, 1st of the month | `RAWG_API_KEY` (the API was down when tested) |

Schedules live in memory, so changes made in the task manager last until the backend
restarts.

## 4. One game, several sources

The same game can arrive from the CSV snapshot, Steam and IGDB. `crud.upsert_game`
decides whether a game is new, a refresh, or extra detail for a game already stored.

```mermaid
flowchart TD
    IN["Incoming game<br/>from one source"] --> A{"Row with this<br/>source's id?"}
    A -->|yes| SAME
    A -->|no| B{"Row with the same slug,<br/>or same name and year,<br/>and no conflicting source id?"}
    B -->|no| NEW["Create a row<br/>(Steam/IGDB ids start at 100,000,000,<br/>slug made unique if taken)"]
    B -->|yes| C{"Did that row come<br/>from this source?"}
    C -->|yes| SAME["Refresh: overwrite fields<br/>and links, keep media<br/>the source left empty"]
    C -->|no| MERGE["Merge: fill empty fields only,<br/>add genres, platforms, stores, tags"]
```

One source never overwrites another. Two rows that each hold a different id from the
same source are never merged, even when the names match.

## 5. Training a model

`python -m src.ml.train` (the `train` service, the weekly job, or by hand) trains on
every game that has a Metacritic score. Its inputs are things known before reviews come
in: title, release date, ESRB rating, genres, platforms, stores and tags.

```mermaid
flowchart TD
    LOAD["load_dataset<br/>games with a Metacritic score"] --> ENOUGH{"At least<br/>ML_MIN_TRAINING_ROWS?"}
    ENOUGH -->|no| SKIP["skip, report why"]
    ENOUGH -->|yes| SPLIT["Hash split by game id<br/>~80% train · ~20% test<br/>(a game never changes side)"]
    SPLIT --> TUNE{"--tune N?"}
    TUNE -->|yes| SEARCH["Randomised search on the<br/>training part (nested run)"]
    TUNE -->|no| CANDS
    SEARCH --> CANDS["Candidates, 5-fold CV MAE:<br/>mean baseline · Ridge ·<br/>histogram gradient boosting"]
    CANDS --> BEST["Lowest CV MAE wins<br/>(baseline excluded)"]
    BEST --> TEST["Test-set metrics: MAE, RMSE, R²,<br/>per-band MAE, balanced band accuracy,<br/>permutation importance, worst errors"]
    TEST --> REG["Log to MLflow and register<br/>a new version of<br/>metacritic-predictor"]
    REG --> GATE{"Beats the baseline<br/>and the current champion<br/>on the same test set?"}
    GATE -->|yes| PROMOTE["Move the champion alias<br/>to this version"]
    GATE -->|no| KEEP["Tag promoted=false,<br/>champion unchanged"]
```

The current champion is re-scored on the same test games before the comparison, so a
version trained on more data is not compared against an old, easier test set.

## 6. Serving estimates in the product

The API never ships a model file of its own. It asks MLflow for
`models:/metacritic-predictor@champion` on first use and re-checks the alias every
`MODEL_REFRESH_SECONDS` (60 by default), so a newly promoted version goes live without a
restart.

This is what happens when the home page asks for recent games critics never scored:

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant N as nginx
    participant A as FastAPI
    participant D as Postgres
    participant M as Model service
    participant F as MLflow

    B->>N: GET /api/games?scored=false
    N->>A: proxy
    A->>D: query the page of games
    A->>M: predict(unscored games that have<br/>genres, platforms and tags)
    alt champion not loaded or alias moved
        M->>F: resolve champion, download model
    end
    M-->>A: one score per game (one call per page)
    A-->>A: range = score ± test MAE,<br/>band from the score
    A-->>B: games with expected<br/>{score, low, high, reception}
    Note over B: hatched range on the 0-100 strip,<br/>real scores are a solid mark
```

Without a champion, lists load without estimates and the prediction endpoints answer
503. The game page asks `/api/games/{id}/predicted-metacritic` for the same estimate. For
a scored game it shows how the real score compares with what the model would have
expected.

## 7. Signing in

Accounts live in Rauthy; the app stores no passwords. The dashboard uses the
authorization code flow with PKCE (`oidc-client-ts`), and the API checks every access
token itself.

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (dashboard)
    participant R as Rauthy (/auth/v1)
    participant A as FastAPI
    participant D as Postgres

    B->>B: Sign in: make a PKCE verifier and challenge
    B->>R: /oidc/authorize (client game-insight, challenge)
    R-->>B: login page
    B->>R: e-mail + password (or passkey)
    R-->>B: redirect to /callback?code=...
    B->>R: /oidc/token (code + verifier)
    R-->>B: access, ID and refresh tokens<br/>(kept in session storage)
    B->>A: PUT /api/me/favorites/3498<br/>Authorization: Bearer (access token)
    A->>R: /oidc/certs (cached, over the compose network)
    A-->>A: check signature, issuer, audience, expiry
    A->>D: find user by sub, or create it
    A-->>B: 204
    Note over B,R: Before the token expires, oidc-client-ts<br/>renews it with the refresh token
```

The issuer the API expects (`OIDC_ISSUER`) is the address the browser sees,
`http://localhost:<FRONTEND_PORT>/auth/v1/`. The keys come from Rauthy directly
(`OIDC_JWKS_URL`). A user from before Rauthy is linked to the account that brings the same
verified e-mail address. Registration and password-reset mail goes to mailcrab, so
nothing leaves the machine.

## 8. The database

Alembic migrations in `src/backend/alembic/versions` build this schema;
`tests/test_migrations.py` fails CI if the migrations and `models.py` disagree. MLflow
keeps its own tables in a separate `mlflow` database on the same server.

```mermaid
erDiagram
    genres ||--o{ game_genres : ""
    games ||--o{ game_genres : ""
    games ||--o{ user_favorite_games : ""
    users ||--o{ user_favorite_games : ""

    games {
        int id PK
        string slug UK
        string name
        datetime released
        int metacritic "the label"
        float critic_rating "IGDB"
        float rating
        int ratings_count
        string esrb_rating
        int steam_appid UK
        int igdb_id UK
    }
    genres {
        int id PK
        string name UK
        string slug UK
    }
    users {
        int id PK
        string sub UK "Rauthy id"
        string email UK
        bool is_active
        enum role
    }
    admin_users {
        int id PK
        string username UK
        string hashed_password
    }
```

`platforms`, `stores` and `tags` have the same shape as `genres` and link to `games`
the same way (`game_platforms`, `game_stores`, `game_tags`). Game ids are RAWG's ids, or
100,000,000 and up for rows first created from Steam or IGDB. `metacritic` is the
training label; `critic_rating` holds IGDB's critic average and is never used as one.
`admin_users` are separate from dashboard accounts: they sign in to the SQLAdmin panel
at `/admin`.

## 9. Tests and CI

```mermaid
flowchart LR
    PUSH["push / pull request"] --> LINT["lint<br/>ruff check, ruff format"]
    PUSH --> TEST["test<br/>pytest + Postgres service<br/>(migrations checked)"]
    PUSH --> FE["frontend<br/>tsc, Vitest, vite build"]
    PUSH --> E2E["docker<br/>build images, start the stack,<br/>seed 2000-2004, train"]
    E2E --> SMOKE["smoke test: health, games,<br/>workers, nginx, MLflow, prediction,<br/>Rauthy issuer, 401 without a token"]
```

The Python tests mock every outside HTTP call and train real models against a
throwaway MLflow, so they need no network. Token checks are tested with tokens signed by a
throwaway RSA key (expired, wrong audience, wrong issuer, forged).
