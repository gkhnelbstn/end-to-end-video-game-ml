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
    -   **Message Broker:** Redis
-   **Containerization:**
    -   **Platform:** Docker & Docker Compose
-   **Testing:**
    -   **Framework:** Pytest
-   **Project Template:**
    -   [Cookiecutter Data Science](https://github.com/drivendata/cookiecutter-data-science)

## Getting Started

To run this project locally, you need to have Docker and Docker Compose installed.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd game-insight-project
    ```

2.  **Start the services using Docker Compose:**
    ```bash
    docker compose up --build -d
    ```

This command will build the images and start all services (Backend, Frontend, Database, Redis, Worker, Scheduler) in detached mode.
-   **Backend API:** [http://localhost:8000](http://localhost:8000)
-   **Frontend Dashboard:** [http://localhost:8501](http://localhost:8501)

## Project Structure

The project is organized based on the `cookiecutter-data-science` template. Service-specific code is located under the `src/` directory.

    ├── LICENSE
    ├── Makefile           <- Makefile with common commands.
    ├── README.md          <- This file.
    ├── docker-compose.yml <- Docker Compose file for managing services.
    ├── requirements.txt   <- Main project dependencies (for uv).
    ├── setup.py           <- Makes the project pip-installable.
    ├── src                <- Main source code for the project.
    │   ├── __init__.py
    │   │
    │   ├── backend        <- FastAPI application, API endpoints, and Celery configuration.
    │   │   ├── Dockerfile
    │   │   ├── requirements.txt
    │   │   └── main.py
    │   │
    │   ├── frontend       <- Streamlit dashboard application.
    │   │   ├── Dockerfile
    │   │   ├── requirements.txt
    │   │   └── app.py
    │   │
    │   └── worker         <- Celery tasks for periodic data ingestion.
    │       └── tasks.py
    │
    ├── tests              <- Pytest tests for the application.
    └── ... (other cookiecutter directories)

--------

<p><small>Project based on the <a target="_blank" href="https://drivendata.github.io/cookiecutter-data-science/">cookiecutter data science project template</a>. #cookiecutterdatascience</small></p>
