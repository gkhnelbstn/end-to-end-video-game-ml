"""Pydantic schemas for API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Lookup(_OrmModel):
    """A genre, platform, store or tag. Extra RAWG fields are ignored."""

    id: int
    name: str
    slug: str


# Kept as separate names so the OpenAPI schema stays descriptive.
class Genre(Lookup):
    pass


class Platform(Lookup):
    pass


class Store(Lookup):
    pass


class Tag(Lookup):
    pass


class GameBase(BaseModel):
    id: int
    slug: str
    name: str
    released: datetime | None = None
    rating: float | None = None
    ratings_count: int | None = None
    metacritic: int | None = None
    playtime: int | None = None
    background_image: str | None = None
    clip: str | None = None


class GameCreate(GameBase):
    genres: list[Genre] = []
    platforms: list[Platform] = []
    stores: list[Store] = []
    tags: list[Tag] = []


class Game(GameCreate, _OrmModel):
    pass


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    email: str
    password: str


class User(_OrmModel):
    id: int
    email: str
    is_active: bool
    favorite_games: list[Game] = []
