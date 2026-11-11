"""Pydantic schemas for API requests and responses, and for ingestion."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "untitled"


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Ingestion ---------------------------------------------------------------


class LookupIn(BaseModel):
    """A genre, platform, store or tag as a source reports it. Extra fields are ignored.

    `id` is set only for RAWG data, whose ids the look-up tables keep. Other sources match
    existing rows by slug or name, because their ids live in a different id space.
    """

    id: int | None = None
    name: str
    slug: str = ""

    @model_validator(mode="after")
    def _default_slug(self):
        if not self.slug:
            self.slug = slugify(self.name)
        return self


class GameFields(BaseModel):
    slug: str
    name: str
    released: datetime | None = None
    rating: float | None = None
    ratings_count: int | None = None
    metacritic: int | None = None
    critic_rating: float | None = None
    playtime: int | None = None
    esrb_rating: str | None = None
    background_image: str | None = None
    clip: str | None = None
    steam_appid: int | None = None
    igdb_id: int | None = None


class GameCreate(GameFields):
    """A game from one source. `id` is the RAWG id, or None for other sources."""

    id: int | None = None
    genres: list[LookupIn] = []
    platforms: list[LookupIn] = []
    stores: list[LookupIn] = []
    tags: list[LookupIn] = []


# --- API responses -----------------------------------------------------------


class Lookup(_OrmModel):
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


class Game(GameFields, _OrmModel):
    id: int
    genres: list[Genre] = []
    platforms: list[Platform] = []
    stores: list[Store] = []
    tags: list[Tag] = []


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


# --- Predictions -------------------------------------------------------------


class GameFeatures(BaseModel):
    """What the Metacritic model looks at: things known before release, no reception data.

    Names match the genre/platform/store/tag names in the API. Every field is optional.
    """

    name: str = Field(default="", max_length=200)
    release_year: int | None = Field(default=None, ge=1970, le=2100)
    release_month: int | None = Field(default=None, ge=1, le=12)
    esrb_rating: str | None = None
    genres: list[str] = []
    platforms: list[str] = []
    stores: list[str] = []
    tags: list[str] = []


class MetacriticPrediction(BaseModel):
    predicted_metacritic: float
    model_name: str
    model_version: str
    game_id: int | None = None
    actual_metacritic: int | None = None


class ModelInfo(BaseModel):
    model_name: str
    model_version: str
    run_id: str | None
    metrics: dict[str, float]
    tracking_uri: str
