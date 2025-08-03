"""
CRUD (Create, Read, Update, Delete) operations for the database models.
"""
from sqlalchemy.orm import Session
from . import models, schemas


def get_genre_by_name(db: Session, name: str):
    """
    Gets a genre by its name.
    """
    return db.query(models.Genre).filter(models.Genre.name == name).first()


def create_genre(db: Session, genre: schemas.GenreCreate):
    """
    Creates a new genre.
    """
    db_genre = models.Genre(name=genre.name, slug=genre.slug, id=genre.id)
    db.add(db_genre)
    db.commit()
    db.refresh(db_genre)
    return db_genre


def get_game_by_slug(db: Session, slug: str):
    """
    Gets a game by its slug.
    """
    return db.query(models.Game).filter(models.Game.slug == slug).first()


def create_game(db: Session, game: schemas.GameCreate):
    """
    Creates a new game.
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

    # Handle genres
    for genre_data in game.genres:
        genre = get_genre_by_name(db, name=genre_data.name)
        if not genre:
            genre = create_genre(db, genre=genre_data)
        db_game.genres.append(genre)

    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game
