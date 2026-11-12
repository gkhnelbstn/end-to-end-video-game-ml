"""Database queries used by the API, the worker and the seeder."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, or_, select
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
    "critic_rating",
    "playtime",
    "esrb_rating",
    "background_image",
    "clip",
)
_SOURCE_IDS = ("steam_appid", "igdb_id")


def _get_or_create_lookup(db: Session, model, item: schemas.LookupIn):
    """Return the matching look-up row, creating it if needed."""
    # Bulk loads touch the same few thousand rows over and over; remember them per session.
    cache = db.info.setdefault("lookup_cache", {})
    key = (model, item.id if item.id is not None else item.slug)
    if (cached := cache.get(key)) is not None:
        return cached
    instance = cache[key] = _find_or_create_lookup(db, model, item)
    return instance


def _find_or_create_lookup(db: Session, model, item: schemas.LookupIn):
    # Only RAWG data carries ids from our id space. Steam's genre "1" is not RAWG's genre 1.
    instance = db.get(model, item.id) if item.id is not None else None
    if instance is None:
        # Match by slug or name. This also covers RAWG entries that share a name or slug
        # under different ids (both columns are unique here).
        instance = db.scalar(
            select(model)
            .where(
                or_(
                    model.slug == item.slug,
                    func.lower(model.name) == item.name.lower(),
                )
            )
            .limit(1)
        )
    if instance is None:
        instance = model(id=item.id, name=item.name, slug=item.slug)
        db.add(instance)
        db.flush()
    return instance


def _lookups(db: Session, model, items: list[schemas.LookupIn]) -> list:
    rows = [_get_or_create_lookup(db, model, item) for item in items]
    # Sources occasionally repeat an entry; a duplicate would violate the association PK.
    return list({row.id: row for row in rows}.values())


def _set_relations(db: Session, db_game: models.Game, game: schemas.GameCreate) -> None:
    for attr, model in _RELATIONS.items():
        setattr(db_game, attr, _lookups(db, model, getattr(game, attr)))


def _add_relations(db: Session, db_game: models.Game, game: schemas.GameCreate) -> None:
    for attr, model in _RELATIONS.items():
        current = getattr(db_game, attr)
        known = {row.id for row in current}
        new_rows = _lookups(db, model, getattr(game, attr))
        current.extend(row for row in new_rows if row.id not in known)


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
    scored: bool | None = None,
    released_from: date | None = None,
    released_to: date | None = None,
) -> list[models.Game]:
    """List games with optional filtering and sorting.

    `scored` True keeps games with a Metacritic score, False those without one. Both
    release-date bounds are inclusive days.
    """
    stmt = select(models.Game)
    if scored is True:
        stmt = stmt.where(models.Game.metacritic.is_not(None))
    elif scored is False:
        stmt = stmt.where(models.Game.metacritic.is_(None))
    if released_from:
        stmt = stmt.where(models.Game.released >= datetime.combine(released_from, time.min))
    if released_to:
        next_day = datetime.combine(released_to + timedelta(days=1), time.min)
        stmt = stmt.where(models.Game.released < next_day)

    if search:
        stmt = stmt.where(models.Game.name.icontains(search))
    if genre:
        stmt = stmt.where(models.Game.genres.any(models.Genre.slug == genre))
    if platform:
        stmt = stmt.where(models.Game.platforms.any(models.Platform.slug == platform))
    if rating:
        stmt = stmt.where(models.Game.rating >= rating)

    if sort_by in ("name", "released", "rating", "ratings_count", "metacritic"):
        column = getattr(models.Game, sort_by)
        stmt = stmt.order_by(
            column.desc().nulls_last() if sort_order == "desc" else column.asc().nulls_last()
        )
    # Tie-breaker so pagination is stable.
    stmt = stmt.order_by(models.Game.id)

    return list(db.scalars(stmt.offset(skip).limit(limit)))


def find_matching_game(db: Session, game: schemas.GameCreate) -> models.Game | None:
    """Find the row that already represents this game, from this or another source.

    In order: the source's own id, then the slug, then the same name with the same
    release year (a game is only merged across sources when both agree).
    """
    if game.id is not None and (row := db.get(models.Game, game.id)) is not None:
        return row
    for field in _SOURCE_IDS:
        value = getattr(game, field)
        if value is not None:
            row = db.scalar(select(models.Game).where(getattr(models.Game, field) == value))
            if row is not None:
                return row

    year = game.released.year if game.released else None
    candidates = db.scalars(
        select(models.Game).where(or_(models.Game.slug == game.slug, models.Game.name == game.name))
    ).all()
    for row in candidates:
        row_year = row.released.year if row.released else None
        same_year = year is None or row_year is None or row_year == year
        # Never merge two different games that both have an id from the same source.
        compatible_ids = all(
            getattr(row, f) is None or getattr(game, f) in (None, getattr(row, f))
            for f in _SOURCE_IDS
        )
        if same_year and compatible_ids:
            return row
    return None


def _free_slug(db: Session, game: schemas.GameCreate) -> str:
    """The game's slug, made unique if another game already uses it."""
    if get_game_by_slug(db, game.slug) is None:
        return game.slug
    suffixes = [str(game.released.year)] if game.released else []
    suffixes += [f"steam-{game.steam_appid}"] if game.steam_appid else []
    suffixes += [f"igdb-{game.igdb_id}"] if game.igdb_id else []
    for suffix in suffixes:
        candidate = f"{game.slug}-{suffix}"
        if get_game_by_slug(db, candidate) is None:
            return candidate
    n = 2
    while get_game_by_slug(db, f"{game.slug}-{n}") is not None:
        n += 1
    return f"{game.slug}-{n}"


def create_game(db: Session, game: schemas.GameCreate) -> models.Game:
    """Create a game together with its genres, platforms, stores and tags."""
    db_game = models.Game(id=game.id, slug=_free_slug(db, game))
    for field in (*_SCALAR_FIELDS, *_SOURCE_IDS):
        setattr(db_game, field, getattr(game, field))
    db.add(db_game)
    _set_relations(db, db_game, game)
    db.commit()
    return db_game


def update_game(db: Session, db_game: models.Game, game: schemas.GameCreate) -> models.Game:
    """Overwrite an existing game with fresh data from the same source.

    Missing media fields are kept.
    """
    for field in _SCALAR_FIELDS:
        value = getattr(game, field)
        if value is None and field in ("background_image", "clip", "esrb_rating"):
            continue
        setattr(db_game, field, value)
    for field in _SOURCE_IDS:
        if getattr(game, field) is not None:
            setattr(db_game, field, getattr(game, field))
    _set_relations(db, db_game, game)
    db.commit()
    return db_game


def merge_game(db: Session, db_game: models.Game, game: schemas.GameCreate) -> models.Game:
    """Enrich a game with data from another source: fill gaps, add genres/tags/platforms.

    Values the row already has are kept, so one source never overwrites another.
    """
    for field in (*_SCALAR_FIELDS, *_SOURCE_IDS):
        if getattr(db_game, field) is None and getattr(game, field) is not None:
            setattr(db_game, field, getattr(game, field))
    _add_relations(db, db_game, game)
    db.commit()
    return db_game


def upsert_game(
    db: Session, game: schemas.GameCreate, source_field: str | None = None
) -> tuple[models.Game, str]:
    """Insert, refresh or enrich a game. Returns the row and "created", "updated" or "merged".

    `source_field` names the id field of the source the data comes from ("steam_appid",
    "igdb_id", or None for RAWG, whose id is the row id). When the matched row came from
    the same source, the fresh data replaces the old; otherwise it only fills gaps.
    """
    existing = find_matching_game(db, game)
    if existing is None:
        return create_game(db, game), "created"
    same_source = (
        game.id is not None and existing.id == game.id
        if source_field is None
        else getattr(existing, source_field) == getattr(game, source_field)
    )
    if same_source:
        return update_game(db, existing, game), "updated"
    return merge_game(db, existing, game), "merged"


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
        # RAWG stores 0 for "not rated yet"; counting those would drag every average down.
        .where(models.Game.rating > 0)
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


def get_top_stores(db: Session, limit: int = 10) -> list[dict]:
    return _top_by_game_count(db, models.Store, models.Game.stores, limit)


def get_esrb_ratings(db: Session) -> list[dict]:
    count = func.count(models.Game.id)
    rows = db.execute(
        select(models.Game.esrb_rating, count)
        .where(models.Game.esrb_rating.is_not(None))
        .group_by(models.Game.esrb_rating)
        .order_by(count.desc())
    )
    return [{"name": name, "count": n} for name, n in rows]


def get_summary(db: Session) -> dict:
    """Headline numbers for the dashboard."""
    games, scored, avg_score, first, last = db.execute(
        select(
            func.count(models.Game.id),
            func.count(models.Game.metacritic),
            func.avg(models.Game.metacritic),
            func.min(models.Game.released),
            # Announced games carry placeholder dates years ahead; count released ones only.
            func.max(case((models.Game.released <= func.now(), models.Game.released))),
        )
    ).one()
    return {
        "games": games,
        "with_metacritic": scored,
        "avg_metacritic": None if avg_score is None else round(float(avg_score), 1),
        "genres": db.scalar(select(func.count(models.Genre.id))),
        "platforms": db.scalar(select(func.count(models.Platform.id))),
        "first_year": first.year if first else None,
        "last_year": last.year if last else None,
    }


def get_metacritic_distribution(db: Session) -> list[dict]:
    """Games per 10-point Metacritic band (0-9, 10-19, ..., 90-100)."""
    score = models.Game.metacritic
    band = case((score >= 100, 90), else_=(score // 10) * 10)
    rows = db.execute(
        select(band, func.count(models.Game.id))
        .where(models.Game.metacritic.is_not(None))
        .group_by(band)
        .order_by(band)
    )
    return [{"band": int(b), "count": n} for b, n in rows]
