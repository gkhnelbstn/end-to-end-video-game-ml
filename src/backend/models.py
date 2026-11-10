"""SQLAlchemy models: games, their look-up tables, and users."""

import enum
from datetime import datetime

from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, String, Table, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _association(name: str, left: str, right: str) -> Table:
    """Build a many-to-many association table between two tables."""
    left_col, right_col = f"{left[:-1]}_id", f"{right[:-1]}_id"
    return Table(
        name,
        Base.metadata,
        Column(left_col, Integer, ForeignKey(f"{left}.id", ondelete="CASCADE"), primary_key=True),
        Column(right_col, Integer, ForeignKey(f"{right}.id", ondelete="CASCADE"), primary_key=True),
    )


game_genres = _association("game_genres", "games", "genres")
game_platforms = _association("game_platforms", "games", "platforms")
game_stores = _association("game_stores", "games", "stores")
game_tags = _association("game_tags", "games", "tags")
user_favorite_games = _association("user_favorite_games", "users", "games")


class Game(Base):
    """A video game, keyed by its RAWG id."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    released: Mapped[datetime | None]
    rating: Mapped[float | None] = mapped_column(Float)
    ratings_count: Mapped[int | None]
    metacritic: Mapped[int | None]
    playtime: Mapped[int | None]
    background_image: Mapped[str | None]
    clip: Mapped[str | None]

    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())
    created_at: Mapped[datetime | None] = mapped_column(server_default=func.now())

    genres: Mapped[list["Genre"]] = relationship(secondary=game_genres, back_populates="games")
    platforms: Mapped[list["Platform"]] = relationship(
        secondary=game_platforms, back_populates="games"
    )
    stores: Mapped[list["Store"]] = relationship(secondary=game_stores, back_populates="games")
    tags: Mapped[list["Tag"]] = relationship(secondary=game_tags, back_populates="games")
    favorited_by: Mapped[list["User"]] = relationship(
        secondary=user_favorite_games, back_populates="favorite_games"
    )


class _Lookup:
    """Columns shared by the look-up tables. Ids come from RAWG."""

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)

    def __str__(self) -> str:
        return self.name


class Genre(_Lookup, Base):
    """A game genre (e.g. Action, RPG)."""

    __tablename__ = "genres"
    games: Mapped[list[Game]] = relationship(secondary=game_genres, back_populates="genres")


class Platform(_Lookup, Base):
    """A gaming platform (e.g. PC, PlayStation 5)."""

    __tablename__ = "platforms"
    games: Mapped[list[Game]] = relationship(secondary=game_platforms, back_populates="platforms")


class Store(_Lookup, Base):
    """A digital game store (e.g. Steam, GOG)."""

    __tablename__ = "stores"
    games: Mapped[list[Game]] = relationship(secondary=game_stores, back_populates="stores")


class Tag(_Lookup, Base):
    """A game tag (e.g. Singleplayer, Multiplayer)."""

    __tablename__ = "tags"
    games: Mapped[list[Game]] = relationship(secondary=game_tags, back_populates="tags")


class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    """A dashboard user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Store the enum *values* ("user"/"admin"), matching the type the migration creates.
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", values_callable=lambda e: [m.value for m in e]),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )

    created_at: Mapped[datetime | None] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())

    favorite_games: Mapped[list[Game]] = relationship(
        secondary=user_favorite_games, back_populates="favorited_by"
    )


class AdminUser(Base):
    """An account that can log in to the admin panel."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    created_at: Mapped[datetime | None] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())
