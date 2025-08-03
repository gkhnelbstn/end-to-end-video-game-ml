"""Main FastAPI application for the Game Insight project."""

from fastapi import FastAPI

app = FastAPI(
    title="Game Insight API",
    description="API for collecting and serving video game data.",
    version="0.1.0",
)


@app.get("/")
def read_root() -> dict[str, str]:
    """
    Root endpoint for the API.

    Returns:
        A welcome message.
    """
    return {"message": "Welcome to the Game Insight API!"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Used to verify that the service is running and responsive.

    Returns:
        A status message indicating the service is "ok".
    """
    return {"status": "ok"}
