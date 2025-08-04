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


class Game(GameBase):
    genres: List[Genre] = []

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
