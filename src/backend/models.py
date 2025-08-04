"""
SQLAlchemy models for the Game Insight project database.

This module defines the database schema using SQLAlchemy's declarative base.
It includes tables for games, genres, platforms, stores, tags, and users,
with appropriate relationships and indexing.
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
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum


# --- Association Tables for Many-to-Many Relationships ---

game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)

game_platforms = Table(
    "game_platforms",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id"), primary_key=True),
    Column("platform_id", Integer, ForeignKey("platforms.id"), primary_key=True),
)

game_stores = Table(
    "game_stores",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id"), primary_key=True),
    Column("store_id", Integer, ForeignKey("stores.id"), primary_key=True),
)

game_tags = Table(
    "game_tags",
    Base.metadata,
    Column("game_id", Integer, ForeignKey("games.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


# --- Main 'games' Table ---

class Game(Base):
    """Represents a video game in the database."""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    released = Column(DateTime)
    rating = Column(Float)
    ratings_count = Column(Integer)
    metacritic = Column(Integer)
    playtime = Column(Integer)

    # Timestamps
    updated_at = Column(DateTime, onupdate=func.now())
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    genres = relationship("Genre", secondary=game_genres, back_populates="games")
    platforms = relationship("Platform", secondary=game_platforms, back_populates="games")
    stores = relationship("Store", secondary=game_stores, back_populates="games")
    tags = relationship("Tag", secondary=game_tags, back_populates="games")


# --- Look-up Tables ---

class Genre(Base):
    """Represents a game genre (e.g., Action, RPG)."""
    __tablename__ = "genres"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    games = relationship("Game", secondary=game_genres, back_populates="genres")

class Platform(Base):
    """Represents a gaming platform (e.g., PC, PlayStation 5)."""
    __tablename__ = "platforms"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    games = relationship("Game", secondary=game_platforms, back_populates="platforms")

class Store(Base):
    """Represents a digital game store (e.g., Steam, GOG)."""
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    games = relationship("Game", secondary=game_stores, back_populates="stores")

class Tag(Base):
    """Represents a game tag (e.g., Singleplayer, Multiplayer)."""
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    games = relationship("Game", secondary=game_tags, back_populates="tags")


# --- User Management Tables ---

class UserRole(enum.Enum):
    """Enumeration for user roles."""
    USER = "user"
    ADMIN = "admin"

class User(Base):
    """Represents a user of the application."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
