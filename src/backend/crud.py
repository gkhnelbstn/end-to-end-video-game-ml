"""
CRUD (Create, Read, Update, Delete) operations for the database models.
"""
from sqlalchemy.orm import Session
from . import models, schemas


def get_or_create(db: Session, model, **kwargs):
    """
    Gets an object or creates it if it doesn't exist.
    """
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        db.add(instance)
        db.commit()
        db.refresh(instance)
        return instance


def get_game_by_slug(db: Session, slug: str):
    """
    Gets a game by its slug.
    """
    return db.query(models.Game).filter(models.Game.slug == slug).first()


from sqlalchemy import desc

def get_games(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    genre: str = None,
    platform: str = None,
    rating: float = None,
    sort_by: str = None,
    sort_order: str = "asc",
):
    """
    Gets a list of games with optional filtering and sorting.
    """
    query = db.query(models.Game)

    if search:
        query = query.filter(models.Game.name.contains(search))
    if genre:
        query = query.join(models.Game.genres).filter(models.Genre.slug == genre)
    if platform:
        query = query.join(models.Game.platforms).filter(models.Platform.slug == platform)
    if rating:
        query = query.filter(models.Game.rating >= rating)

    if sort_by:
        sort_column = getattr(models.Game, sort_by, None)
        if sort_column:
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(sort_column)

    return query.offset(skip).limit(limit).all()


def create_game(db: Session, game: schemas.GameCreate):
    """
    Creates a new game and its relationships.
    """
    db_game = models.Game(
        id=game.id,
        slug=game.slug,
        name=game.name,
        released=game.released,
        rating=game.rating,
        ratings_count=game.ratings_count,
        metacritic=game.metacritic,
        playtime=game.playtime,
    )

    # Handle genres, platforms, stores, and tags
    for genre_data in game.genres:
        genre = get_or_create(db, models.Genre, id=genre_data.id, name=genre_data.name, slug=genre_data.slug)
        db_game.genres.append(genre)

    for platform_data in game.platforms:
        platform = get_or_create(db, models.Platform, id=platform_data.id, name=platform_data.name, slug=platform_data.slug)
        db_game.platforms.append(platform)

    for store_data in game.stores:
        store = get_or_create(db, models.Store, id=store_data.id, name=store_data.name, slug=store_data.slug)
        db_game.stores.append(store)

    for tag_data in game.tags:
        tag = get_or_create(db, models.Tag, id=tag_data.id, name=tag_data.name, slug=tag_data.slug)
        db_game.tags.append(tag)

    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game


from . import security

def get_user_by_email(db: Session, email: str):
    """
    Gets a user by their email address.
    """
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate):
    """
    Creates a new user.
    """
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def add_favorite_game(db: Session, user: models.User, game: models.Game):
    """
    Adds a game to a user's list of favorite games.
    """
    user.favorite_games.append(game)
    db.commit()
    db.refresh(user)
    return user


def remove_favorite_game(db: Session, user: models.User, game: models.Game):
    """
    Removes a game from a user's list of favorite games.
    """
    user.favorite_games.remove(game)
    db.commit()
    db.refresh(user)
    return user


def get_favorite_games(db: Session, user: models.User):
    """
    Gets a list of a user's favorite games.
    """
    return user.favorite_games


from sqlalchemy import func
from sqlalchemy.orm import Session
from . import models, schemas

def get_games_per_year(db: Session):
    """
    Gets the number of games released per year.
    """
    return db.query(func.extract('year', models.Game.released), func.count(models.Game.id)).group_by(func.extract('year', models.Game.released)).all()

def get_average_rating_by_genre(db: Session):
    """
    Gets the average rating for each genre.
    """
    return db.query(models.Genre.name, func.avg(models.Game.rating)).join(models.Game.genres).group_by(models.Genre.name).all()


def update_game(db: Session, db_game: models.Game, game_update: schemas.GameCreate):
    """
    Updates an existing game and its relationships.
    """
    # Update simple fields
    db_game.name = game_update.name
    db_game.released = game_update.released
    db_game.rating = game_update.rating
    db_game.ratings_count = game_update.ratings_count
    db_game.metacritic = game_update.metacritic
    db_game.playtime = game_update.playtime

    # Update relationships
    db_game.genres.clear()
    for genre_data in game_update.genres:
        genre = get_or_create(db, models.Genre, id=genre_data.id, name=genre_data.name, slug=genre_data.slug)
        db_game.genres.append(genre)

    db_game.platforms.clear()
    for platform_data in game_update.platforms:
        platform = get_or_create(db, models.Platform, id=platform_data.id, name=platform_data.name, slug=platform_data.slug)
        db_game.platforms.append(platform)

    db_game.stores.clear()
    for store_data in game_update.stores:
        store = get_or_create(db, models.Store, id=store_data.id, name=store_data.name, slug=store_data.slug)
        db_game.stores.append(store)

    db_game.tags.clear()
    for tag_data in game_update.tags:
        tag = get_or_create(db, models.Tag, id=tag_data.id, name=tag_data.name, slug=tag_data.slug)
        db_game.tags.append(tag)

    db.commit()
    db.refresh(db_game)
    return db_game
