"""Main FastAPI application for the Game Insight project."""

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from . import models, schemas, crud
from .database import engine, get_db
from .logging import setup_logging
from .admin import admin  # yukarıdaki admin_app
from src.backend.models import AdminUser
from src.backend.database import SessionLocal
from passlib.context import CryptContext

# Set up logging
setup_logging()

# Create the database tables
models.Base.metadata.create_all(bind=engine)

# View'leri oluştur (tablolar oluşturulduktan sonra)
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
                print(f"⚠️  Error creating views: {e}")
                db.rollback()
            finally:
                db.close()
    except FileNotFoundError:
        print("⚠️  views.sql file not found. Skipping view creation.")
    except Exception as e:
        print(f"⚠️  Unexpected error reading views.sql: {e}")

app = FastAPI(
    title="Game Insight API",
    description="API for collecting and serving video game data.",
    version="0.1.0",
)

@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

# Mount the admin app
app.mount("/admin", admin.app)


@app.get("/")
def read_root() -> dict[str, str]:
    """Root endpoint for the API."""
    return {"message": "Welcome to the Game Insight API!"}





# --- API Endpoints for Frontend ---

@app.get("/api/games", response_model=List[schemas.Game])
def list_games(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    genre: Optional[str] = None,
    platform: Optional[str] = None,
    rating: Optional[float] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    skip: int = 0,
    limit: int = 100,
):
    """
    List games with optional filtering, sorting, search, and pagination.
    """
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


from fastapi import HTTPException

# --- User and Favorites Endpoints ---

@app.post("/api/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


# Placeholder for user authentication
def get_current_user(db: Session = Depends(get_db)):
    # In a real app, this would be implemented with OAuth2
    return crud.get_user_by_email(db, email="test@example.com")


@app.post("/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
def add_favorite(
    user_id: int,
    game_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Authorization: Ensure the logged-in user can only modify their own favorites
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this user's favorites")

    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return crud.add_favorite_game(db=db, user=current_user, game=game)


@app.delete("/users/{user_id}/favorites/{game_id}", response_model=schemas.User)
def remove_favorite(
    user_id: int,
    game_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this user's favorites")

    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    return crud.remove_favorite_game(db=db, user=current_user, game=game)


@app.get("/users/{user_id}/favorites", response_model=List[schemas.Game])
def get_favorites(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this user's favorites")

    return crud.get_favorite_games(db=db, user=current_user)


# --- Stats Endpoints ---

@app.get("/api/stats/games-per-year")
def get_games_per_year(db: Session = Depends(get_db)):
    """
    Get the number of games released per year.
    """
    return crud.get_games_per_year(db)


@app.get("/api/stats/avg-rating-by-genre")
def get_avg_rating_by_genre(db: Session = Depends(get_db)):
    """
    Get the average rating for each genre.
    """
    return crud.get_average_rating_by_genre(db)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")  # ✅ Artık tanımlı
def create_first_admin():

    db = SessionLocal()
    try:
        # Kullanıcı zaten varsa oluşturmayalım
        if not db.query(AdminUser).filter(AdminUser.username == "admin").first():
            admin = AdminUser(
                username="admin",
                hashed_password=pwd_context.hash("adminpass"),  # Parolayı değiştirebilirsin
                is_active=True
            )
            db.add(admin)
            db.commit()
            print("✅ First admin user created: username=admin, password=adminpass")
    finally:
        db.close()

# app.on_event("startup") ile çağır
@app.on_event("startup")
def on_startup():
    create_views()
    create_first_admin()
