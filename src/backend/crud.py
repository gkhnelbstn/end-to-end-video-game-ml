"""Database queries used by the API, the worker and the seeder."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models, schemas, security

_RELATIONS = {
    "genres": models.Genre,
    "platforms": models.Platform,
    "stores": models.Store,
    "tags": models.Tag,
}
_SCALAR_FIELDS = (
    "name",
    "released",
    "rating",
    "ratings_count",
    "metacritic",
    "playtime",
    "background_image",
    "clip",
)


def _get_or_create_lookup(db: Session, model, item: schemas.Lookup):
    """Return the look-up row with this RAWG id, creating it if needed."""
    # Bulk loads touch the same few thousand rows over and over; remember them per session.
    cache = db.info.setdefault("lookup_cache", {})
    if (cached := cache.get((model, item.id))) is not None:
        return cached
    instance = cache[(model, item.id)] = _find_or_create_lookup(db, model, item)
    return instance


def _find_or_create_lookup(db: Session, model, item: schemas.Lookup):
    instance = db.get(model, item.id)
    if instance is None:
        # RAWG has a few entries that share a name or slug under different ids;
        # both columns are unique here, so reuse the existing row.
        instance = db.scalar(
            select(model).where(or_(model.slug == item.slug, model.name == item.name)).limit(1)
        )
    if instance is None:
        instance = model(id=item.id, name=item.name, slug=item.slug)
        db.add(instance)
        db.flush()
    return instance


def _set_relations(db: Session, db_game: models.Game, game: schemas.GameCreate) -> None:
    for attr, model in _RELATIONS.items():
        # RAWG occasionally repeats an entry; a duplicate would violate the association PK.
        unique = {item.id: item for item in getattr(game, attr)}
        setattr(db_game, attr, [_get_or_create_lookup(db, model, i) for i in unique.values()])


def get_game(db: Session, game_id: int) -> models.Game | None:
    return db.get(models.Game, game_id)


def get_game_by_slug(db: Session, slug: str) -> models.Game | None:
    return db.scalar(select(models.Game).where(models.Game.slug == slug))


def count_games(db: Session) -> int:
    return db.scalar(select(func.count(models.Game.id))) or 0


def get_games(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    genre: str | None = None,
    platform: str | None = None,
    rating: float | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
) -> list[models.Game]:
    """List games with optional filtering and sorting."""
    stmt = select(models.Game)

    if search:
        stmt = stmt.where(models.Game.name.icontains(search))
    if genre:
        stmt = stmt.where(models.Game.genres.any(models.Genre.slug == genre))
    if platform:
        stmt = stmt.where(models.Game.platforms.any(models.Platform.slug == platform))
    if rating:
        stmt = stmt.where(models.Game.rating >= rating)

    if sort_by in ("name", "released", "rating", "metacritic"):
        column = getattr(models.Game, sort_by)
        stmt = stmt.order_by(
            column.desc().nulls_last() if sort_order == "desc" else column.asc().nulls_last()
        )
    # Tie-breaker so pagination is stable.
    stmt = stmt.order_by(models.Game.id)

    return list(db.scalars(stmt.offset(skip).limit(limit)))


def create_game(db: Session, game: schemas.GameCreate) -> models.Game:
    """Create a game together with its genres, platforms, stores and tags."""
    db_game = models.Game(id=game.id, slug=game.slug)
    for field in _SCALAR_FIELDS:
        setattr(db_game, field, getattr(game, field))
    db.add(db_game)
    _set_relations(db, db_game, game)
    db.commit()
    return db_game


def update_game(db: Session, db_game: models.Game, game: schemas.GameCreate) -> models.Game:
    """Overwrite an existing game with fresh data. Missing media fields are kept."""
    for field in _SCALAR_FIELDS:
        value = getattr(game, field)
        if value is None and field in ("background_image", "clip"):
            continue
        setattr(db_game, field, value)
    _set_relations(db, db_game, game)
    db.commit()
    return db_game


def update_game_media(
    db: Session, db_game: models.Game, background_image: str | None, clip: str | None
) -> models.Game:
    """Fill in media fields only."""
    if background_image:
        db_game.background_image = background_image
    if clip:
        db_game.clip = clip
    db.commit()
    return db_game


def get_genres(db: Session) -> list[models.Genre]:
    return list(db.scalars(select(models.Genre).order_by(models.Genre.name)))


def get_platforms(db: Session) -> list[models.Platform]:
    return list(db.scalars(select(models.Platform).order_by(models.Platform.name)))


# --- Users ---


def get_user(db: Session, user_id: int) -> models.User | None:
    return db.get(models.User, user_id)


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.scalar(select(models.User).where(models.User.email == email))


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        email=user.email, hashed_password=security.get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    return db_user


def add_favorite_game(db: Session, user: models.User, game: models.Game) -> models.User:
    if game not in user.favorite_games:
        user.favorite_games.append(game)
        db.commit()
    return user


def remove_favorite_game(db: Session, user: models.User, game: models.Game) -> models.User:
    if game in user.favorite_games:
        user.favorite_games.remove(game)
        db.commit()
    return user


# --- Statistics ---


def get_games_per_year(db: Session) -> list[dict]:
    year = func.extract("year", models.Game.released)
    rows = db.execute(
        select(year, func.count(models.Game.id))
        .where(models.Game.released.is_not(None))
        .group_by(year)
        .order_by(year)
    )
    return [{"year": int(y), "count": count} for y, count in rows]


def get_average_rating_by_genre(db: Session) -> list[dict]:
    rows = db.execute(
        select(models.Genre.name, func.avg(models.Game.rating))
        .join(models.Game.genres)
        .where(models.Game.rating.is_not(None))
        .group_by(models.Genre.name)
        .order_by(models.Genre.name)
    )
    return [{"genre": name, "avg_rating": float(avg)} for name, avg in rows]


def get_rating_distribution(db: Session) -> list[dict]:
    """Number of games per rating, rounded to the nearest integer."""
    bucket = func.round(models.Game.rating)
    rows = db.execute(
        select(bucket, func.count(models.Game.id))
        .where(models.Game.rating.is_not(None))
        .group_by(bucket)
        .order_by(bucket)
    )
    return [{"rating": int(r), "count": count} for r, count in rows]


def _top_by_game_count(db: Session, model, relation, limit: int) -> list[dict]:
    count = func.count(models.Game.id)
    rows = db.execute(
        select(model.name, count)
        .join(relation)
        .group_by(model.name)
        .order_by(count.desc(), model.name)
        .limit(limit)
    )
    return [{"name": name, "count": n} for name, n in rows]


def get_top_genres(db: Session, limit: int = 10) -> list[dict]:
    return _top_by_game_count(db, models.Genre, models.Game.genres, limit)


def get_top_platforms(db: Session, limit: int = 10) -> list[dict]:
    return _top_by_game_count(db, models.Platform, models.Game.platforms, limit)
