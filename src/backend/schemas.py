"""
Pydantic models (schemas) for the Game Insight project.

These models define the shape of the data for API requests and responses,
and for creating items in the database.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class GenreBase(BaseModel):
    name: str
    slug: str
    id: int


class GenreCreate(GenreBase):
    pass


class Genre(GenreBase):
    class Config:
        orm_mode = True


class PlatformBase(BaseModel):
    id: int
    name: str
    slug: str


class PlatformCreate(PlatformBase):
    pass


class Platform(PlatformBase):
    class Config:
        orm_mode = True


class StoreBase(BaseModel):
    id: int
    name: str
    slug: str


class StoreCreate(StoreBase):
    pass


class Store(StoreBase):
    class Config:
        orm_mode = True


class TagBase(BaseModel):
    id: int
    name: str
    slug: str


class TagCreate(TagBase):
    pass


class Tag(TagBase):
    class Config:
        orm_mode = True


class GameBase(BaseModel):
    id: int
    slug: str
    name: str
    released: Optional[datetime] = None
    rating: Optional[float] = None
    ratings_count: Optional[int] = None
    metacritic: Optional[int] = None
    playtime: Optional[int] = None


class GameCreate(GameBase):
    genres: List[GenreCreate] = []
    platforms: List[PlatformCreate] = []
    stores: List[StoreCreate] = []
    tags: List[TagCreate] = []


class Game(GameBase):
    genres: List[Genre] = []
    platforms: List[Platform] = []
    stores: List[Store] = []
    tags: List[Tag] = []

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    favorite_games: List[Game] = []

    class Config:
        orm_mode = True
