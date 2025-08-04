"""Main FastAPI application for the Game Insight project."""

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from . import models, schemas, crud
from .database import engine, get_db
from .logging import setup_logging
from .admin import admin_app

# Set up logging
setup_logging()

# Create the database tables
models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Game Insight API",
    description="API for collecting and serving video game data.",
    version="0.1.0",
)

# Mount the admin app
app.mount("/admin", admin_app)


@app.get("/")
def read_root() -> dict[str, str]:
    """Root endpoint for the API."""
    return {"message": "Welcome to the Game Insight API!"}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# --- API Endpoints for Frontend ---

@app.get("/api/games", response_model=List[schemas.Game])
def list_games(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """
    List games with optional search and pagination.
    """
    # This is a simplified implementation. A real implementation would use
    # the new view and have more advanced filtering.
    if search:
        return db.query(models.Game).filter(models.Game.name.contains(search)).offset(skip).limit(limit).all()
    return db.query(models.Game).offset(skip).limit(limit).all()


@app.get("/api/games/{game_id}", response_model=schemas.Game)
def get_game_details(game_id: int, db: Session = Depends(get_db)):
    """
    Get the details for a single game.
    """
    return db.query(models.Game).filter(models.Game.id == game_id).first()


@app.get("/api/genres", response_model=List[schemas.Genre])
def list_genres(db: Session = Depends(get_db)):
    """
    Get a list of all genres.
    """
    return db.query(models.Genre).all()
