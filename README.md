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
-   **Portainer:** `http://localhost:9000`

Optional: start with auto-seed on first run (if DB is empty and CSVs exist under `data/raw/`):

```bash
docker compose --profile init up -d
```

This enables the `seed-on-empty` helper service which checks the database and runs the CSV seeder automatically if appropriate.

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

## Seeder and Media Backfill

Seed CSV data and backfill media fields:

```bash
# Run seeder (parses CSV under data/raw). If a game exists, it backfills background_image/clip when available
docker compose run --rm seeder
```

Notes:
- Seeder now parses optional `background_image` and `clip` fields from CSV. If the game already exists, it updates missing media fields in place.
- If your CSV lacks these fields, images/trailers may remain empty; consider enriching CSV or adding a separate backfill job.

### Auto-seed on empty DB

The compose file includes a helper service `seed-on-empty` (behind the `init` profile) that will:

- Check if the database has zero rows in `games`.
- Check if there are any `.csv` files under `data/raw/`.
- If both conditions are met, it runs the same seeder logic as `seeder`.

Usage:

```bash
# Bring up the stack and run the helper once on startup
docker compose --profile init up -d

# Or run only the helper
docker compose --profile init up -d seed-on-empty
```

If the database is not empty or there are no CSV files, the helper will skip seeding and exit.

## Frontend UX Updates

- Game cards are clickable; clicking an image opens the detail view via query param `?game_id=<id>`.
- The app reads query params with `st.get_query_params()` to deep-link directly to a game.
- If a game has `background_image`, it's shown in the detail view.
- If a game has a `clip` URL, it is rendered with `st.video(...)`.
- Platform filter is populated dynamically from the backend API.

## New API Endpoints

- `GET /api/platforms` → returns all platforms (name, slug, etc.) for dynamic filtering in the frontend.

## Troubleshooting: Alembic config not found

If you see:

```bash
FAILED: No config file 'alembic.ini' found, or file has no '[alembic]' section
```

Run Alembic with an explicit config path inside the container:

```bash
# Apply latest migrations using absolute path inside container
docker compose exec backend alembic -c /app/src/backend/alembic.ini upgrade head

# Or if using docker-compose v1
docker-compose exec backend alembic -c /app/src/backend/alembic.ini upgrade head
```

If the path still fails, verify where the code is mounted:

```bash
docker compose exec backend ls -l /app/src/backend/alembic.ini
```

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

### Default admin (created automatically)

On API startup, if no admin user exists, the app creates a default admin:

- Username: `admin`
- Password: `adminpass`

Change this in production. You can log into the admin panel with these credentials at `http://localhost:8000/admin`.

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
