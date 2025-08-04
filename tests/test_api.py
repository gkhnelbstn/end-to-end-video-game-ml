import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.backend.main import app
from src.backend.database import Base, get_db
from src.backend import models

# --- Test Database Setup ---
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# --- Sample Data ---
@pytest.fixture(scope="module")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create genres
    action_genre = models.Genre(id=1, name="Action", slug="action")
    rpg_genre = models.Genre(id=2, name="RPG", slug="rpg")

    # Create platforms
    pc_platform = models.Platform(id=1, name="PC", slug="pc")
    ps5_platform = models.Platform(id=2, name="PlayStation 5", slug="playstation-5")

    # Create games
    game1 = models.Game(id=1, name="Game A", slug="game-a", rating=4.5, released="2023-01-01T00:00:00")
    game1.genres.append(action_genre)
    game1.platforms.append(pc_platform)

    game2 = models.Game(id=2, name="Game B", slug="game-b", rating=3.5, released="2022-01-01T00:00:00")
    game2.genres.append(rpg_genre)
    game2.platforms.append(ps5_platform)

    game3 = models.Game(id=3, name="Game C", slug="game-c", rating=4.8, released="2023-05-01T00:00:00")
    game3.genres.append(action_genre)
    game3.platforms.append(ps5_platform)

    db.add_all([action_genre, rpg_genre, pc_platform, ps5_platform, game1, game2, game3])
    db.commit()

    yield db
    Base.metadata.drop_all(bind=engine)

# --- Tests ---
def test_list_games_no_filters(test_db):
    response = client.get("/api/games")
    assert response.status_code == 200
    assert len(response.json()) == 3

def test_filter_by_genre(test_db):
    response = client.get("/api/games?genre=action")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert "Game B" not in [g["name"] for g in data]

def test_filter_by_platform(test_db):
    response = client.get("/api/games?platform=pc")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Game A"

def test_filter_by_rating(test_db):
    response = client.get("/api/games?rating=4.0")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert "Game B" not in [g["name"] for g in data]

def test_sort_by_rating_desc(test_db):
    response = client.get("/api/games?sort_by=rating&sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert [g["name"] for g in data] == ["Game C", "Game A", "Game B"]

def test_sort_by_released_asc(test_db):
    response = client.get("/api/games?sort_by=released&sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert [g["name"] for g in data] == ["Game B", "Game A", "Game C"]
