"""Turning games into model inputs.

The model input is a DataFrame with one row per game and the columns in INPUT_COLUMNS:

- `name`: the title (words, sequel numbers and edition keywords become features);
- `release_year`, `release_month`: floats, NaN when unknown;
- `esrb_rating`: e.g. "Teen", "" when unknown;
- `genres`, `platforms`, `stores`, `tags`: "|"-separated names.

All of them are known before a game is released and reviewed: the model deliberately does
not see user ratings, play counts or other reception data. The same shape is used for
training, for the MLflow model signature, and for the prediction API, so the logged model
can be called directly. Older model versions only read the columns they were trained on;
MLflow drops the extra ones.
"""

import math
import re
from collections.abc import Iterable

import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_selection import VarianceThreshold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, MaxAbsScaler

from src.backend import models

INPUT_COLUMNS = [
    "name",
    "release_year",
    "release_month",
    "esrb_rating",
    "genres",
    "platforms",
    "stores",
    "tags",
]
NUMERIC_COLUMNS = ["release_year", "release_month"]
TEXT_COLUMNS = ["name", "esrb_rating"]
LIST_COLUMNS = {"genres": "genre", "platforms": "platform", "stores": "store", "tags": "tag"}
SEPARATOR = "|"
# Drop indicator features present in fewer than ~0.5% of games (variance of a rare binary
# feature is about its frequency); keeps thousands of one-off tags and title words out.
MIN_FEATURE_VARIANCE = 0.005

_ROMAN = {"ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
_EDITION_WORDS = {
    "remastered",
    "remaster",
    "remake",
    "hd",
    "collection",
    "edition",
    "anthology",
    "trilogy",
    "definitive",
    "deluxe",
    "goty",
    "complete",
    "redux",
}
_STOP_WORDS = {"the", "of", "a", "an", "and", "in", "to", "for", "on", "at", "&", "-", "vs"}
_WORD = re.compile(r"[a-z0-9']+")


def join_names(names: Iterable[str]) -> str:
    return SEPARATOR.join(sorted({n.replace(SEPARATOR, "/").strip() for n in names if n}))


def split_names(value) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    return [part for part in value.split(SEPARATOR) if part]


def game_to_row(game: models.Game) -> dict:
    """The model input for one game in the database."""
    return {
        "name": game.name or "",
        "release_year": float(game.released.year) if game.released else math.nan,
        "release_month": float(game.released.month) if game.released else math.nan,
        "esrb_rating": game.esrb_rating or "",
        "genres": join_names(g.name for g in game.genres),
        "platforms": join_names(p.name for p in game.platforms),
        "stores": join_names(s.name for s in game.stores),
        "tags": join_names(t.name for t in game.tags),
    }


def to_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=INPUT_COLUMNS)
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    for column in [*TEXT_COLUMNS, *LIST_COLUMNS]:
        # Missing keys and None both become "" (a column absent from every row is all-NaN).
        frame[column] = [value if isinstance(value, str) else "" for value in frame[column]]
    return frame


def name_features(name: str) -> dict[str, float]:
    """Signals in a title: sequel numbers, subtitles, re-release keywords, and its words."""
    lowered = name.lower()
    words = _WORD.findall(lowered)
    out: dict[str, float] = {}
    if not words:
        return out
    last = words[-1]
    sequel = None
    if last.isdigit() and 2 <= int(last) <= 20:
        sequel = int(last)
    elif last in _ROMAN:
        sequel = _ROMAN[last]
    else:
        # "Diablo II: Lord of Destruction", "Halo 3: ODST"
        head = _WORD.findall(re.split(r"[:\-–]", lowered, maxsplit=1)[0])
        if head and head[-1].isdigit() and 2 <= int(head[-1]) <= 20:
            sequel = int(head[-1])
        elif head and head[-1] in _ROMAN and len(head) > 1:
            sequel = _ROMAN[head[-1]]
    if sequel is not None:
        out["title_sequel"] = 1.0
        out["title_sequel_number"] = float(min(sequel, 10))
    if ":" in name or " - " in name:
        out["title_subtitle"] = 1.0
    if _EDITION_WORDS.intersection(words):
        out["title_rerelease"] = 1.0
    out["title_words"] = float(len(words))
    for word in set(words):
        if word not in _STOP_WORDS and not word.isdigit() and word not in _ROMAN:
            out[f"word={word}"] = 1.0
    return out


def to_feature_dicts(frame: pd.DataFrame) -> list[dict]:
    """One sparse feature dict per game (used inside the pipeline)."""
    records = []
    for row in frame.itertuples(index=False):
        features: dict[str, float] = {}
        year = row.release_year
        if _missing(year):
            features["release_year_missing"] = 1.0
        else:
            # Centered so a missing year (all zeros) means "about 2010" to linear models.
            features["release_year"] = (float(year) - 2010.0) / 10.0
        month = row.release_month
        if not _missing(month):
            features[f"release_quarter=Q{(int(month) - 1) // 3 + 1}"] = 1.0
        features[f"esrb={row.esrb_rating or 'unknown'}"] = 1.0
        features.update(name_features(row.name))
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


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _to_dense(matrix):
    return matrix.toarray()
