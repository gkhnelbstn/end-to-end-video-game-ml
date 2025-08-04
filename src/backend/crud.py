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
