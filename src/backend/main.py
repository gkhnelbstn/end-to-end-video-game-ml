"""FastAPI application for the Game Insight project."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from starlette.requests import Request

from src.ml import features
from src.ml.serving import ModelUnavailableError, model_service

from . import config, crud, models, schemas, security
from .admin import create_admin, setup_admin_views
from .celery_app import celery_app
from .database import SessionLocal, engine, get_db
from .logger_config import setup_logging
from .task_management_api import router as task_management_router
from .task_scheduler import task_scheduler

setup_logging()
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
DbSession = Annotated[Session, Depends(get_db)]


def create_views() -> None:
    """(Re)create the reporting views defined in views.sql (PostgreSQL only)."""
    if engine.dialect.name != "postgresql":
        return
    sql = (BACKEND_DIR / "views.sql").read_text()
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:
        logger.exception("Could not create database views")


def create_first_admin() -> None:
    """Create the initial admin panel account if there is none yet."""
    with SessionLocal() as db:
        if db.scalar(select(models.AdminUser).limit(1)) is not None:
            return
        db.add(
            models.AdminUser(
                username=config.ADMIN_USERNAME,
                hashed_password=security.get_password_hash(config.ADMIN_PASSWORD),
            )
        )
        db.commit()
        logger.info("Created initial admin user '%s'", config.ADMIN_USERNAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Without Alembic (USE_ALEMBIC=0) fall back to creating tables from the models.
    if os.getenv("USE_ALEMBIC", "0") != "1":
        models.Base.metadata.create_all(bind=engine)
    create_views()
    create_first_admin()
    await task_scheduler.start()
    yield
    await task_scheduler.shutdown()


app = FastAPI(
    title="Game Insight API",
    description="API for collecting and serving video game data.",
    version="0.2.0",
    lifespan=lifespan,
)

# Admin panel (session handling is set up by SQLAdmin's authentication backend).
setup_admin_views(create_admin(app))


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Game Insight API!"}


# ------------------ Celery task endpoints ------------------


@app.post("/api/tasks/revoke/{task_id}")
def revoke_task(task_id: str):
    celery_app.control.revoke(task_id, terminate=True)
    return {"status": "success", "message": f"Task {task_id} revoked."}


@app.get("/api/tasks/available")
def get_available_tasks():
    tasks = {
        name: {"name": name, "description": task.__doc__}
        for name, task in celery_app.tasks.items()
        if not name.startswith("celery.")
    }
    return {"tasks": tasks}


@app.post("/api/tasks/run/{task_name}")
def run_task(task_name: str, params: Annotated[dict[str, Any] | None, Body()] = None):
    task = celery_app.tasks.get(task_name)
    if not task or task_name.startswith("celery."):
        raise HTTPException(status_code=404, detail="Task not found")
    result = task.delay(**(params or {}))
    return {"task_id": result.id, "status": "started"}


@app.get("/api/tasks/running")
def running_tasks():
    inspector = celery_app.control.inspect()
    return {
        "active": inspector.active() or {},
        "scheduled": inspector.scheduled() or {},
        "reserved": inspector.reserved() or {},
    }


@app.get("/api/tasks/workers")
def get_workers():
    workers = celery_app.control.inspect().ping()
    if not workers:
        raise HTTPException(status_code=503, detail="No active workers found.")
    return {"workers": list(workers.keys())}


@app.post("/api/tasks/broadcast/{command}")
def broadcast_command(command: str):
    if command not in ["shutdown", "ping"]:
        raise HTTPException(status_code=400, detail="Unsupported command.")
    return {"command": command, "responses": celery_app.control.broadcast(command)}


# Scheduled-task management API and its UI
app.include_router(task_management_router)
templates = Jinja2Templates(directory=BACKEND_DIR / "templates")


@app.get("/task-management", response_class=HTMLResponse)
async def task_management_ui(request: Request):
    """Serve the task management UI."""
    return templates.TemplateResponse(request, "task_management.html")


# ------------------ Game endpoints ------------------


@app.get("/api/games", response_model=list[schemas.Game])
def list_games(
    db: DbSession,
    search: str | None = None,
    genre: str | None = None,
    platform: str | None = None,
    rating: float | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    skip: int = 0,
    limit: int = 100,
):
    return crud.get_games(
        db=db,
        search=search,
        genre=genre,
        platform=platform,
        rating=rating,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )


def get_game_or_404(game_id: int, db: DbSession) -> models.Game:
    game = crud.get_game(db, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@app.get("/api/games/{game_id}", response_model=schemas.Game)
def get_game_details(game: Annotated[models.Game, Depends(get_game_or_404)]):
    return game


@app.get("/api/genres", response_model=list[schemas.Genre])
def list_genres(db: DbSession):
    return crud.get_genres(db)


@app.get("/api/platforms", response_model=list[schemas.Platform])
def list_platforms(db: DbSession):
    return crud.get_platforms(db)


# ------------------ Metacritic predictions (MLflow champion model) ------------------


def _predict(rows: list[dict]) -> list[float]:
    try:
        return model_service.predict(features.to_frame(rows))
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/games/{game_id}/predicted-metacritic", response_model=schemas.MetacriticPrediction)
def predict_game_metacritic(game: Annotated[models.Game, Depends(get_game_or_404)]):
    """What the model expects this game to score, from its year, genres, platforms and tags."""
    [prediction] = _predict([features.game_to_row(game)])
    info = model_service.info()
    return schemas.MetacriticPrediction(
        predicted_metacritic=prediction,
        model_name=info["model_name"],
        model_version=info["version"],
        game_id=game.id,
        actual_metacritic=game.metacritic,
    )


@app.post("/api/predictions/metacritic", response_model=schemas.MetacriticPrediction)
def predict_metacritic(game: schemas.GameFeatures):
    """Predict a Metacritic score for a hypothetical game."""
    row = {
        "release_year": game.release_year,
        "genres": features.join_names(game.genres),
        "platforms": features.join_names(game.platforms),
        "tags": features.join_names(game.tags),
    }
    [prediction] = _predict([row])
    info = model_service.info()
    return schemas.MetacriticPrediction(
        predicted_metacritic=prediction,
        model_name=info["model_name"],
        model_version=info["version"],
    )


@app.get("/api/ml/model", response_model=schemas.ModelInfo)
def model_info():
    """The champion model currently served, with its evaluation metrics."""
    try:
        info = model_service.info()
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return schemas.ModelInfo(model_version=info["version"], **info)


@app.post("/api/ml/reload", response_model=schemas.ModelInfo)
def reload_model():
    """Re-resolve the champion alias now instead of waiting for the next refresh."""
    try:
        info = model_service.reload()
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return schemas.ModelInfo(model_version=info["version"], **info)


# ------------------ Users and favorites ------------------


def get_current_user(db: DbSession, x_user_id: Annotated[int | None, Header()] = None):
    """Identify the caller from the X-User-Id header set by the dashboard after login.

    This is a demo-grade scheme, not real authentication: there are no tokens.
    """
    user = crud.get_user(db, x_user_id) if x_user_id is not None else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@app.post("/api/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: DbSession):
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.post("/api/auth/login")
def login(payload: schemas.LoginRequest, db: DbSession):
    user = crud.get_user_by_email(db, email=payload.email)
    if not user or not security.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"id": user.id, "email": user.email}


# The un-prefixed path is kept as an alias for backwards compatibility.
@app.post("/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
@app.post("/api/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
def add_favorite(
    user_id: int,
    game: Annotated[models.Game, Depends(get_game_or_404)],
    db: DbSession,
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return crud.add_favorite_game(db=db, user=current_user, game=game)


@app.get("/api/users/{user_id}/favorites", response_model=list[schemas.Game])
def list_favorites(user_id: int, db: DbSession):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.favorite_games


# ------------------ Statistics ------------------


@app.get("/api/stats/games-per-year")
def get_games_per_year(db: DbSession):
    return crud.get_games_per_year(db)


@app.get("/api/stats/avg-rating-by-genre")
def get_avg_rating_by_genre(db: DbSession):
    return crud.get_average_rating_by_genre(db)


@app.get("/api/stats/rating-distribution")
def get_rating_distribution(db: DbSession):
    return crud.get_rating_distribution(db)


@app.get("/api/stats/top-genres")
def get_top_genres(db: DbSession, limit: int = 10):
    return crud.get_top_genres(db, limit=limit)


@app.get("/api/stats/top-platforms")
def get_top_platforms(db: DbSession, limit: int = 10):
    return crud.get_top_platforms(db, limit=limit)
