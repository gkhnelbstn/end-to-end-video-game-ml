"""Turning games into model inputs.

The model input is a DataFrame with one row per game and the columns in INPUT_COLUMNS:
`release_year` (float, NaN when unknown) and `genres`, `platforms`, `tags` as
"|"-separated names. The same shape is used for training, for the MLflow model
signature, and for the prediction API, so the logged model can be called directly.
"""

import math
from collections.abc import Iterable

import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import VarianceThreshold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, MaxAbsScaler

from src.backend import models

INPUT_COLUMNS = ["release_year", "genres", "platforms", "tags"]
LIST_COLUMNS = {"genres": "genre", "platforms": "platform", "tags": "tag"}
SEPARATOR = "|"
# Drop indicator features present in fewer than ~0.5% of games (variance of a rare binary
# feature is about its frequency); keeps thousands of one-off tags out of the model.
MIN_FEATURE_VARIANCE = 0.005


def join_names(names: Iterable[str]) -> str:
    return SEPARATOR.join(sorted({n.replace(SEPARATOR, "/").strip() for n in names if n}))


def split_names(value) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    return [part for part in value.split(SEPARATOR) if part]


def game_to_row(game: models.Game) -> dict:
    """The model input for one game in the database."""
    return {
        "release_year": float(game.released.year) if game.released else math.nan,
        "genres": join_names(g.name for g in game.genres),
        "platforms": join_names(p.name for p in game.platforms),
        "tags": join_names(t.name for t in game.tags),
    }


def to_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=INPUT_COLUMNS)
    frame["release_year"] = pd.to_numeric(frame["release_year"], errors="coerce").astype(float)
    for column in LIST_COLUMNS:
        frame[column] = frame[column].fillna("").astype(str)
    return frame


def to_feature_dicts(frame: pd.DataFrame) -> list[dict]:
    """One sparse feature dict per game (used inside the pipeline)."""
    records = []
    for row in frame.itertuples(index=False):
        features: dict[str, float] = {}
        year = row.release_year
        if year is None or (isinstance(year, float) and math.isnan(year)):
            features["release_year_missing"] = 1.0
        else:
            # Centered so a missing year (all zeros) means "about 2010" to linear models.
            features["release_year"] = (float(year) - 2010.0) / 10.0
        for column, prefix in LIST_COLUMNS.items():
            names = split_names(getattr(row, column))
            features[f"n_{column}"] = float(len(names))
            for name in names:
                features[f"{prefix}={name}"] = 1.0
        records.append(features)
    return records


def build_pipeline(estimator, dense: bool = False) -> Pipeline:
    steps = [
        ("features", FunctionTransformer(to_feature_dicts)),
        ("vectorize", DictVectorizer(sparse=True)),
        ("drop_rare", VarianceThreshold(MIN_FEATURE_VARIANCE)),
        ("scale", MaxAbsScaler()),
    ]
    if dense:
        steps.append(("dense", FunctionTransformer(_to_dense, accept_sparse=True)))
    steps.append(("model", estimator))
    return Pipeline(steps)


def _to_dense(matrix):
    return matrix.toarray()
