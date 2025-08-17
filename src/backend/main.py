"""Main FastAPI application for the Game Insight project."""

import os
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from passlib.context import CryptContext

from . import models, schemas, crud
from .database import engine, get_db, SessionLocal
from .logger_config import setup_logging
from .admin import create_admin, setup_admin_views
from .celery_app import celery_app
from .celery_admin import CeleryMonitoringView
from .models import AdminUser
from .task_scheduler import task_scheduler
from .task_management_api import router as task_management_router
from .task_admin import TaskManagementView, setup_task_management_routes

# Set up logging
setup_logging()

# Safe database initialization
def initialize_database():
    """
    Safely initialize database tables and views.
    Only creates tables if they don't exist, preserving existing data.
    """
    try:
        # Create tables only if they don't exist (this is the default behavior)
        models.Base.metadata.create_all(bind=engine)
        print("✅ Database tables initialized successfully.")
    except Exception as e:
        print(f"⚠️ Error initializing database tables: {e}")

# Initialize database (skip when Alembic is managing migrations)
if os.getenv("USE_ALEMBIC", "0") != "1":
    initialize_database()

# Function to create database views after table creation
def create_views():
    try:
        with open('src/backend/views.sql', 'r') as f:
            sql = f.read()
        if sql.strip():
            db = SessionLocal()
            try:
                db.execute(text(sql))
                db.commit()
                print("✅ Views created successfully.")
            except Exception as e:
                print(f"⚠️ Error creating views: {e}")
                db.rollback()
            finally:
                db.close()
    except FileNotFoundError:
        print("⚠️ views.sql file not found. Skipping view creation.")
    except Exception as e:
        print(f"⚠️ Unexpected error reading views.sql: {e}")

# Function to create the first admin user
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_first_admin():
    db = SessionLocal()
    try:
        if not db.query(AdminUser).filter(AdminUser.username == "admin").first():
            admin_user = AdminUser(
                username="admin",
                hashed_password=pwd_context.hash("adminpass"),  # Change in production
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ First admin user created: username=admin, password=adminpass")
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

# FastAPI Application
app = FastAPI(
    title="Game Insight API",
    description="API for collecting and serving video game data.",
    version="0.1.0",
)

# Session middleware for admin authentication
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-this-in-production")

# Admin panel setup
admin = create_admin(app)
setup_admin_views(admin)
# Task management views removed from admin panel - use /task-management instead

# Application startup and shutdown events
@app.on_event("startup")
async def on_startup():
    create_views()
    create_first_admin()
    await task_scheduler.start()
    # setup_task_management_routes(admin)  # Disabled - causes routing conflicts with SQLAdmin

@app.on_event("shutdown")
async def on_shutdown():
    await task_scheduler.shutdown()

# Health Check Endpoint
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

# Root Endpoint
@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Game Insight API!"}

# ------------------ Celery API Endpoints ------------------

@app.post("/api/tasks/revoke/{task_id}")
def revoke_task(task_id: str):
    try:
        celery_app.control.revoke(task_id, terminate=True)
        return {"status": "success", "message": f"Task {task_id} revoked."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/available")
def get_available_tasks():
    tasks = {}
    for name, task in celery_app.tasks.items():
        if not name.startswith('celery.'):
            tasks[name] = {
                'name': name,
                'description': task.__doc__,
            }
    return {"tasks": tasks}

@app.post("/api/tasks/run/{task_name}")
def run_task(task_name: str, params: dict = None):
    task = celery_app.tasks.get(task_name)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    params = params or {}
    result = task.delay(**params)
    return {"task_id": result.id, "status": "started"}

@app.get("/api/tasks/running")
def running_tasks():
    inspector = celery_app.control.inspect()
    active = inspector.active() or {}
    scheduled = inspector.scheduled() or {}
    reserved = inspector.reserved() or {}

    return {
        "active": active,
        "scheduled": scheduled,
        "reserved": reserved
    }

@app.get("/api/tasks/workers")
def get_workers():
    inspector = celery_app.control.inspect()
    workers = inspector.ping()
    if not workers:
        raise HTTPException(status_code=500, detail="No active workers found.")
    return {"workers": list(workers.keys())}

@app.post("/api/tasks/broadcast/{command}")
def broadcast_command(command: str):
    if command not in ["shutdown", "ping"]:
        raise HTTPException(status_code=400, detail="Unsupported command.")

    responses = celery_app.control.broadcast(command)
    return {"command": command, "responses": responses}

# Task Management API
app.include_router(task_management_router)

# Task Management UI endpoint
templates = Jinja2Templates(directory="src/backend/templates")

@app.get("/task-management", response_class=HTMLResponse)
async def task_management_ui(request: Request):
    """Serve the task management UI."""
    return templates.TemplateResponse("task_management.html", {"request": request})

# ------------------ Game Insight API Endpoints ------------------

@app.get("/api/games", response_model=List[schemas.Game])
def list_games(db: Session = Depends(get_db), search: Optional[str] = None, genre: Optional[str] = None,
               platform: Optional[str] = None, rating: Optional[float] = None, sort_by: Optional[str] = None,
               sort_order: Optional[str] = "asc", skip: int = 0, limit: int = 100):
    return crud.get_games(db=db, search=search, genre=genre, platform=platform, rating=rating,
                          sort_by=sort_by, sort_order=sort_order, skip=skip, limit=limit)

@app.get("/api/games/{game_id}", response_model=schemas.Game)
def get_game_details(game_id: int, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game

@app.get("/api/genres", response_model=List[schemas.Genre])
def list_genres(db: Session = Depends(get_db)):
    return db.query(models.Genre).all()

@app.get("/api/platforms", response_model=List[schemas.Platform])
def list_platforms(db: Session = Depends(get_db)):
    return db.query(models.Platform).all()

# ------------------ User and Favorites Endpoints ------------------

def get_current_user(x_user_id: Optional[int] = Header(default=None), db: Session = Depends(get_db)):
    # If frontend sends X-User-Id header, use that user if exists; otherwise fallback to a demo user
    if x_user_id is not None:
        user = db.query(models.User).filter(models.User.id == x_user_id).first()
        if user:
            return user
    return crud.get_user_by_email(db, email="test@example.com")

@app.post("/api/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

# --- Auth ---
@app.post("/api/auth/login")
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, email=payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from .security import verify_password
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {"id": user.id, "email": user.email}

@app.post("/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
def add_favorite(user_id: int, game_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return crud.add_favorite_game(db=db, user=current_user, game=game)

# Alias with API prefix for consistency
@app.post("/api/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
def add_favorite_api(user_id: int, game_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return crud.add_favorite_game(db=db, user=current_user, game=game)

@app.get("/api/users/{user_id}/favorites", response_model=List[schemas.Game])
def list_favorites(user_id: int, db: Session = Depends(get_db)):
    # Ensure the user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.get_favorite_games(db=db, user=user)

# Stats Endpoints
@app.get("/api/stats/games-per-year")
def get_games_per_year(db: Session = Depends(get_db)):
    return crud.get_games_per_year(db)

@app.get("/api/stats/avg-rating-by-genre")
def get_avg_rating_by_genre(db: Session = Depends(get_db)):
    return crud.get_average_rating_by_genre(db)

@app.get("/api/stats/rating-distribution")
def get_rating_distribution(db: Session = Depends(get_db)):
    return crud.get_rating_distribution(db)

@app.get("/api/stats/top-genres")
def get_top_genres(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_genres(db, limit=limit)

@app.get("/api/stats/top-platforms")
def get_top_platforms(limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_top_platforms(db, limit=limit)
