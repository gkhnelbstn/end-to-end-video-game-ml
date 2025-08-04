"""Main FastAPI application for the Game Insight project."""

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
import httpx
import os
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


# --- User Authentication Endpoints ---

from fastapi.security import OAuth2PasswordRequestForm
from . import security

@app.post("/api/token", response_model=schemas.Token)
async def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
    user = security.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = security.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.get("/api/games/{game_slug}/trailer")
async def get_game_trailer(game_slug: str):
    """
    Get the trailer for a single game from the RAWG API.
    """
    api_key = os.environ.get("RAWG_API_KEY")
    if not api_key:
        return {"error": "RAWG API key not configured."}

    url = f"https://api.rawg.io/api/games/{game_slug}/movies?key={api_key}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            trailer_data = response.json()
            if trailer_data.get("results"):
                return trailer_data["results"][0]
            else:
                return {"message": "No trailer found for this game."}
        except httpx.HTTPError as e:
            return {"error": f"Failed to fetch trailer from RAWG API: {e}"}
