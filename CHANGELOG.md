# Changelog

Notable changes, newest first. Pull request numbers link to the details.

## 1.0.0

The first complete version: data collection, a tracked and served model, a dashboard
that shows the model's estimates as part of the catalogue, and real sign-in.

### Accounts
- Dashboard sign-in, registration, password reset and passkeys through Rauthy (OpenID
  Connect, authorization code + PKCE). The API checks Rauthy's access tokens. It no
  longer stores dashboard passwords or trusts an `X-User-Id` header. Favourites moved to
  `/api/me/favorites`. A mail catcher receives Rauthy's e-mails locally. (#34)

### Dashboard and estimates
- Estimates appear inside the catalogue: unscored games carry an expected reception
  (a range and Metacritic's wording), drawn as a hatched range next to real scores. The
  home page has shelves for upcoming games, recent games critics never scored, and
  recently reviewed games. The predictor moved to `/estimate`. New visual design, light
  and dark. (#33)
- React + Vite + TypeScript dashboard replaces the Streamlit app, served by nginx. (#28)

### Model
- Gradient boosting uses settings from a randomised search; `--tune N` reruns it.
  Every run logs per-band MAE and balanced band accuracy. Re-weighting rare bands, a
  band classifier and Wikidata studio history were measured and not adopted (README has
  the numbers). (#33)
- Metacritic score model with MLflow tracking, a model registry and a `champion` alias
  that only moves to a better model; the API serves the champion and picks up new
  versions without a restart. (#27)

### Data
- Steam + SteamSpy ingestion (no key) and an IGDB client, with games merged across
  sources without one source overwriting another. Fixed the seeder dropping every
  Metacritic score from the CSV snapshot. (#27)

### Setup and maintenance
- `docker compose up --build` starts everything with no configuration; uv for Python
  dependencies; CI for lint, tests, the dashboard and an end-to-end compose check.
  Fixed migrations, the weekly update task and the test suite. (#25)
- Frontend tooling upgraded (Vite 7, Vitest 4, React Router 7), which clears the
  open dependency security alerts. A notebook output that showed an API key was removed.
  Architecture walk-through with diagrams in `docs/architecture.md`. (this release)

## 0.2.0 and earlier

RAWG data collection into CSV files, MongoDB and Streamlit experiments, then FastAPI,
Celery, SQLAdmin and Alembic. See the git history before #25.
