# Game Insight Project

This project is designed to collect, analyze, and model video game data from the [RAWG.io API](https://rawg.io/apidocs). The system periodically fetches game data, stores it in a database, visualizes it through a Streamlit-based interface, and uses machine learning models to generate insights and predictions (e.g., game popularity, sales figures).

## Project Goals

-   **Data Ingestion:** Periodically fetch video game data from the RAWG API, handling rate limits gracefully.
-   **Data Storage:** Store the collected data in a structured PostgreSQL database.
-   **Data Visualization:** Provide data insights through a user-friendly dashboard built with Streamlit.
-   **Machine Learning:** Develop models to predict game popularity scores, market trends, or potential sales figures.
-   **User Management:** Implement a user registration and authentication system.

## Tech Stack

This project utilizes the following technologies and libraries:

-   **Backend:**
    -   **Framework:** FastAPI
    -   **Package Manager:** uv
    -   **ORM:** SQLAlchemy
    -   **Migrations:** Alembic
    -   **Admin:** SQLAdmin
-   **Frontend:**
    -   **Framework:** Streamlit
-   **Database:**
    -   **System:** PostgreSQL 17
-   **Task Queue & Scheduling:**
    -   **Task Manager:** Celery
    -   **Monitoring:** Flower
-   **Logging & Monitoring:**
    -   **Log Aggregation:** Fluentd
-   **Containerization:**
    -   **Platform:** Docker & Docker Compose
-   **Testing:**
    -   **Framework:** Pytest

## Getting Started

To run this project locally, you need to have Docker and Docker Compose installed.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Set up the environment:**
    - Create a `.env` file in the root of the project. You can use `.env.example` as a template.
    - Update the environment variables in the `.env` file as needed.

3.  **Install dependencies:**
    - The project uses `uv` to manage dependencies. The dependencies for each service are defined in `requirements.in` files.
    - To install all dependencies for local development, run:
      ```bash
      make requirements
      ```
    - If you change a `requirements.in` file, you need to regenerate the corresponding `.lock` file by running:
      ```bash
      make lock
      ```

4.  **Start the services using Docker Compose:**
    ```bash
    docker compose up --build -d
    ```

This command will build the images and start all services in detached mode.
-   **Backend API:** `http://localhost:8000`
-   **Frontend Dashboard:** `http://localhost:8501`
-   **Celery Monitoring (Flower):** `http://localhost:5555`
-   **Admin Panel:** `http://localhost:8000/admin`
-   **Health Check:** `http://localhost:8000/health`

### .env example

Create a `.env` at the project root. Use `.env.example` as a reference, or start with the snippet below:

```
DATABASE_URL=postgresql://user:password@db:5432/game_insight_db
CELERY_BROKER_URL=redis://redis:6379/0
BACKEND_BASE_URL=http://backend:8000
RAWG_API_KEY=your_api_key_here
SECRET_KEY=a_very_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Notes:
- Set RAWG_API_KEY to a valid key from RAWG.io.
- Values above are suitable for the provided Docker Compose setup (services talk over the Docker network).

## Run locally using docker-compose.dokploy.yml (with Fluentd)

This compose includes Fluentd and the logging configuration used for Dokploy. On Windows, the Docker logging driver must connect to Fluentd via the host (127.0.0.1).

1. Stop any previous stack and remove orphans:
   ```powershell
   docker compose -f docker-compose.dokploy.yml down --remove-orphans
   ```
2. Start Fluentd first and wait until it listens on 24224:
   ```powershell
   docker compose -f docker-compose.dokploy.yml up -d fluentd
   while(-not (Test-NetConnection 127.0.0.1 -Port 24224).TcpTestSucceeded){ Start-Sleep -Seconds 1 }
   ```
3. Start the remaining services:
   ```powershell
   docker compose -f docker-compose.dokploy.yml up -d --build backend flower celery-beat frontend worker
   ```
4. Verify logs:
   ```powershell
   docker logs game-insight-fluentd --since 1m
   docker logs game-insight-backend --since 1m
   ```

Troubleshooting:
- If you see `failed to initialize logging driver: lookup fluentd: i/o timeout`, ensure `fluentd-address` is `127.0.0.1:24224` in the compose and that Fluentd is running before other services.

## Deploy with Dokploy

This repo includes `docker-compose.dokploy.yml` for deployments managed by [Dokploy](https://dokploy.com/). It preserves a hybrid env strategy: `.env` for local, and variables can be added/overridden in Dokploy UI for the server.

Steps (Git-based deployment):
- In Dokploy, create a Project (e.g., "game-insight").
- Create Application → Docker Compose.
  - Repository: connect your Git provider/repo.
  - Branch: the branch with your deployment config.
  - Compose path: `docker-compose.dokploy.yml` (repo root).
  - Context/Workdir: repo root.
- Environment variables: In the Dokploy Application → Environment tab, add the keys from `.env.example` as needed (DATABASE_URL, CELERY_BROKER_URL, RAWG_API_KEY, SECRET_KEY, etc.). Values set here will override any defaults.
- Start order (important for logging): Start `fluentd` first, then start the remaining services (backend, frontend, flower, celery-beat, worker). Even though Compose has `depends_on`, Docker’s logging driver connects during container creation, so Fluentd must be ready.
- Logging driver note: The compose is set to `fluentd-address: 127.0.0.1:24224`. This works on a single-server Dokploy because the Docker daemon connects to the host’s Fluentd. Ensure port 24224 is reachable on the host; the compose publishes both TCP and UDP 24224.
- Traefik/domains: Not required. Labels remain placeholders; you can ignore or later configure Dokploy/Traefik ingress to route to `backend` (8000) and `frontend` (8501).
- Volumes: `postgres_data` and `fluentd_logs` are persisted by Docker volumes on the server.

Validate deployment:
- Check container status in Dokploy UI.
- View logs: `fluentd` should show it’s listening on 24224; backend should start without logging driver errors.
- Access services: Backend `http://<server-ip>:8000`, Frontend `http://<server-ip>:8501` (unless fronted by a reverse proxy/ingress).

## Database Migrations (Alembic)

Alembic is integrated and automatically runs on backend container startup. The Docker entrypoint applies `upgrade head` before launching the API. The database is persisted via a Docker volume, so rebuilding images will not reset data.

- Environment variable: `USE_ALEMBIC=1` is set for the backend service to disable `create_all` and delegate schema management to Alembic.

Common commands (run from repository root):

```bash
# Generate a new migration from current SQLAlchemy models
docker compose run --rm backend \
  alembic -c /app/src/backend/alembic.ini revision --autogenerate -m "your message"

# Apply latest migrations
docker compose run --rm backend \
  alembic -c /app/src/backend/alembic.ini upgrade head

# Show current DB revision
docker compose run --rm backend \
  alembic -c /app/src/backend/alembic.ini current
```

Notes:
- Alembic configuration and versions live under `src/backend/alembic/`.
- Inside the container, project root is `/app`. Use absolute paths like `/app/src/backend/alembic.ini`.
- If you develop outside Docker, ensure you have the same dependencies installed via `uv`.

## Logging

All services are configured to send their logs to a central Fluentd container. The logs are stored in the `./logs` directory on the host machine.

## Database Schema

The database schema is defined using SQLAlchemy in `src/backend/models.py`. It includes the following main tables:
-   `games`: Stores the core information about each game.
-   `genres`, `platforms`, `stores`, `tags`: Look-up tables for related game data.
-   `users`: Stores user account information.

The relationships between these tables are managed through association tables.

## Admin Panel

This project includes a web-based admin panel for managing database models, accessible at `http://localhost:8000/admin`.

### Creating an Admin User

To use the admin panel, you first need to create an admin user. You can do this by running the following command in your terminal:

```bash
docker compose exec backend python src/backend/create_admin.py
```

This script will prompt you to enter an email and password for the new admin user. Once created, you can use these credentials to log in to the admin panel.

Admin templates are loaded from `/app/src/backend/templates` inside the container.

If you see a 500 error on list pages after upgrading SQLAdmin, avoid using legacy `column_filters` with raw model columns; use the new filter API or remove filters.

## Project Structure

The project is organized based on the `cookiecutter-data-science` template. Service-specific code is located under the `src/` directory.

```
├── .env.example
├── data
│   ├── external
│   ├── interim
│   ├── processed
│   └── raw
├── docker-compose.yml
├── Dockerfile.dev
├── docs
├── fluentd
├── logs
├── Makefile
├── models
├── notebooks
├── references
├── reports
├── requirements.dev.in
├── requirements.dev.lock
├── src
│   ├── backend
│   │   ├── Dockerfile
│   │   ├── requirements.in
│   │   └── requirements.lock
│   ├── frontend
│   │   ├── Dockerfile
│   │   ├── requirements.in
│   │   └── requirements.lock
│   └── worker
│       ├── Dockerfile
│       ├── requirements.in
│       └── requirements.lock
├── test_environment.py
└── tests
```

## Project To-Do List / Roadmap

1.  **Complete Data Ingestion and Storage:**
    -   Full Data Parsing: Update the Celery tasks to parse the entire RAWG API response for each game and save all the data to the new database tables (platforms, stores, tags, etc.).
    -   Historical Data Backfill: Create a script or a set of Celery tasks to fetch and save the data for all relevant past years (e.g., 1980-present).
    -   Scheduled Tasks: Configure Celery Beat to run the fetch_monthly_updates_task and fetch_weekly_updates_task on a regular schedule.
2.  **Enhance the Backend API:** (Completed)
    -   Advanced Filtering: Improve the /api/games endpoint to allow filtering by genre, platform, rating, etc.
    -   Sorting: Add sorting options to the /api/games endpoint (e.g., by release date, rating).
    -   User-specific Endpoints: Create endpoints for users to manage their profiles, view their favorite games, etc.
    -   API for Visualizations: Create dedicated endpoints to provide aggregated data for the charts and graphs on the frontend dashboard.
3.  **Build out the Frontend Dashboard:**
    -   Game Detail Page: Create a detailed view for each game, showing all its information (screenshots, platforms, stores, tags, etc.).
    -   Advanced Filtering UI: Add UI elements (dropdowns, sliders) to the frontend to allow users to use the advanced API filtering.
    -   Data Visualizations: Create interactive charts and graphs to visualize game data (e.g., number of games released per year, average rating by genre).
    -   User Profile Page: Create a page where users can view and edit their profile information.
4.  **Implement User Features:**
    -   User Registration: Add a registration form to the Streamlit app.
    -   "Favorite" Games: Allow users to mark games as favorites and view their list of favorite games.
5.  **Machine Learning Models:**
    -   Data Preparation: Create data pipelines to prepare the collected data for machine learning.
    -   Model Training: Train the initial machine learning models (e.g., to predict game ratings).
    -   **MLFlow Integration**: Integrate MLFlow to track experiments, log models, and manage the ML lifecycle.
    -   Model Serving: Create API endpoints to serve predictions from the trained models.
    -   Display Predictions: Integrate the model predictions into the frontend dashboard.
6.  **Production-Readiness:**
    -   Comprehensive Testing: Add more unit and integration tests for the backend and frontend.
    -   CI/CD: Set up a Continuous Integration/Continuous Deployment pipeline to automate testing and deployment.
    -   Security Hardening: Secure all endpoints, add more robust error handling, and manage secrets more securely (e.g., with a secrets manager).
