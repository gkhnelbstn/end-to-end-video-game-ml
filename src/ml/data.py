"""Loading the training set from the application database."""

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.backend import models
from src.ml.features import game_to_row, to_frame


def load_dataset(db: Session) -> pd.DataFrame:
    """Every game with a Metacritic score: model inputs plus `metacritic` and provenance.

    `source` says where the row came from: "steam" when it has a Steam app id, "igdb"
    for IGDB-only rows, otherwise "rawg" (the CSV snapshot).
    """
    games = db.scalars(
        select(models.Game)
        .where(models.Game.metacritic.is_not(None))
        .options(
            selectinload(models.Game.genres),
            selectinload(models.Game.platforms),
            selectinload(models.Game.tags),
        )
        .order_by(models.Game.id)
    ).all()

    frame = to_frame([game_to_row(game) for game in games])
    frame["metacritic"] = [float(game.metacritic) for game in games]
    frame["game_id"] = [game.id for game in games]
    frame["name"] = [game.name for game in games]
    frame["source"] = [
        "steam" if game.steam_appid else "igdb" if game.igdb_id else "rawg" for game in games
    ]
    return frame
