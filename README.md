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

2.  **Start the services using Docker Compose:**
    ```bash
    docker compose up --build -d
    ```

This command will build the images and start all services in detached mode.
-   **Backend API:** `http://localhost:8000`
-   **Frontend Dashboard:** `http://localhost:8501`
-   **Celery Monitoring (Flower):** `http://localhost:5555`

## Logging

All services are configured to send their logs to a central Fluentd container. The logs are stored in the `./logs` directory on the host machine.

## Database Schema

The database schema is defined using SQLAlchemy in `src/backend/models.py`. It includes the following main tables:
-   `games`: Stores the core information about each game.
-   `genres`, `platforms`, `stores`, `tags`: Look-up tables for related game data.
-   `users`: Stores user account information.

The relationships between these tables are managed through association tables.

## Project Structure

The project is organized based on the `cookiecutter-data-science` template. Service-specific code is located under the `src/` directory.
... (rest of the structure remains the same)
