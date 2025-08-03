"""
SQLAlchemy models for the Game Insight project database.

This module defines the database schema using SQLAlchemy's declarative base.
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean,
    Table,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# Association table for the many-to-many relationship between games and genres.
game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)


class Game(Base):
    """Represents a video game in the database."""

    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    released = Column(DateTime, nullable=True)
    rating = Column(Float, nullable=True)
    ratings_count = Column(Integer, nullable=True)
    metacritic = Column(Integer, nullable=True)
    playtime = Column(Integer, nullable=True)
    updated = Column(DateTime, onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    genres = relationship("Genre", secondary=game_genres, back_populates="games")


class Genre(Base):
    """Represents a game genre."""

    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)

    games = relationship("Game", secondary=game_genres, back_populates="genres")


class User(Base):
    """Represents a user of the application."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
