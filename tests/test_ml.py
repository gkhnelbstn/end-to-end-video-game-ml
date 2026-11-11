"""Features, training with MLflow tracking + registry, and the prediction API."""

import math

import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient

from src.backend import main
from src.ml import CHAMPION_ALIAS, EXPERIMENT_NAME, MODEL_NAME, features, train
from src.ml.data import load_dataset
from src.ml.serving import ModelService, ModelUnavailableError


@pytest.fixture
def tracking(tmp_path, monkeypatch):
    """A private MLflow tracking server (SQLite + local artifacts) for one test."""
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    mlflow.create_experiment(EXPERIMENT_NAME, artifact_location=(tmp_path / "artifacts").as_uri())
    yield MlflowClient()
    mlflow.set_tracking_uri(None)


def synthetic_games(n: int = 300, seed: int = 0) -> pd.DataFrame:
    """Games whose score depends on genre, platform count and one tag, plus noise."""
    rng = np.random.default_rng(seed)
    rows, scores = [], []
    for i in range(n):
        genres = ["RPG"] if i % 3 == 0 else ["Action"] if i % 3 == 1 else ["Casual"]
        platforms = ["PC", "PlayStation 5", "Xbox Series S/X"][: 1 + i % 3]
        tags = ["Singleplayer"] + (["Great Soundtrack"] if i % 4 == 0 else [])
        score = 70 + {"RPG": 8, "Action": 2, "Casual": -10}[genres[0]] + 2 * len(platforms)
        score += 5 * ("Great Soundtrack" in tags) + rng.normal(0, 2)
        rows.append(
            {
                "release_year": float(2000 + i % 25) if i % 10 else math.nan,
                "genres": features.join_names(genres),
                "platforms": features.join_names(platforms),
                "tags": features.join_names(tags),
            }
        )
        scores.append(float(np.clip(round(score), 0, 100)))
    frame = features.to_frame(rows)
    frame["metacritic"] = scores
    frame["game_id"] = range(1, n + 1)
    frame["name"] = [f"Game {i}" for i in range(n)]
    frame["source"] = "rawg"
    return frame


def test_feature_dicts():
    frame = features.to_frame(
        [
            {
                "name": "Space Rangers",
                "release_year": 2020,
                "release_month": 11,
                "esrb_rating": "Teen",
                "genres": "Action|RPG",
                "platforms": "PC",
                "stores": "Steam",
                "tags": "",
            },
            {"release_year": None, "tags": "Co-op"},
        ]
    )
    first, second = features.to_feature_dicts(frame)
    assert first == {
        "release_year": 1.0,
        "release_quarter=Q4": 1.0,
        "esrb=Teen": 1.0,
        "title_words": 2.0,
        "word=space": 1.0,
        "word=rangers": 1.0,
        "n_genres": 2.0,
        "genre=Action": 1.0,
        "genre=RPG": 1.0,
        "n_platforms": 1.0,
        "platform=PC": 1.0,
        "n_stores": 1.0,
        "store=Steam": 1.0,
        "n_tags": 0.0,
    }
    assert second["release_year_missing"] == 1.0 and second["tag=Co-op"] == 1.0
    assert second["esrb=unknown"] == 1.0 and "title_words" not in second


@pytest.mark.parametrize(
    ("name", "sequel", "subtitle", "rerelease"),
    [
        ("Halo 3", 3, False, False),
        ("Diablo II: Lord of Destruction", 2, True, False),
        ("Final Fantasy VII", 7, False, False),
        ("Dark Souls: Remastered", None, True, True),
        ("Portal", None, False, False),
        ("2064: Read Only Memories", None, True, False),
    ],
)
def test_name_features(name, sequel, subtitle, rerelease):
    out = features.name_features(name)
    assert out.get("title_sequel_number") == (None if sequel is None else float(sequel))
    assert ("title_subtitle" in out) is subtitle
    assert ("title_rerelease" in out) is rerelease


def test_join_names_dedupes_sorts_and_escapes():
    assert features.join_names(["b", "a|x", "b", ""]) == "a/x|b"


def test_load_dataset_only_games_with_metacritic(db):
    game = db.get(main.models.Game, 1)
    game.metacritic, game.steam_appid = 80, 10
    db.commit()
    frame = load_dataset(db)
    assert frame["game_id"].tolist() == [1]
    assert frame.loc[0, ["genres", "platforms", "source"]].tolist() == ["Action", "PC", "steam"]
    assert frame.loc[0, "release_year"] == 2023.0
    assert frame.loc[0, "name"] == "Game A"


def test_test_split_is_stable_as_data_grows():
    ids = pd.Series(range(1, 10_001))
    mask = train.is_test_game(ids)
    assert 0.18 < mask.mean() < 0.22
    # Adding games (including generated ids >= 1e8) never moves an existing game.
    grown = pd.Series([*range(1, 10_001), *range(100_000_001, 100_000_500)])
    assert (train.is_test_game(grown)[:10_000] == mask).all()


def test_training_skips_small_datasets(tracking):
    assert train.train(synthetic_games(50))["status"] == "skipped"


def test_train_registers_and_promotes_only_improvements(tracking):
    games = synthetic_games()
    first = train.train(games)

    assert first["status"] == "trained" and first["promoted"] is True
    assert first["test_mae"] < first["baseline_test_mae"]
    assert first["best_model"] in {"ridge", "hist_gradient_boosting"}
    champion = tracking.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    assert str(champion.version) == first["model_version"]

    run = tracking.get_run(first["run_id"])
    assert run.data.params["best_model"] == first["best_model"]
    assert {"test_mae", "cv_mae", "baseline_test_mae", "importance_genres"} <= set(run.data.metrics)
    children = tracking.search_runs(
        [run.info.experiment_id], f"tags.mlflow.parentRunId = '{run.info.run_id}'"
    )
    assert {c.data.params["model"] for c in children} == {
        "baseline_mean",
        "ridge",
        "hist_gradient_boosting",
    }
    # The genre drives the synthetic score most; shuffling it must hurt.
    assert first["importance"]["genres"] > first["importance"]["release_year"]

    # Same data again: a new version is registered but it is not better, so no promotion.
    second = train.train(games)
    assert second["model_version"] != first["model_version"]
    assert second["promoted"] is False
    assert second["previous_champion_version"] == first["model_version"]
    champion = tracking.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    assert str(champion.version) == first["model_version"]
    assert (
        tracking.get_model_version(MODEL_NAME, second["model_version"]).tags["promoted"] == "false"
    )


def test_model_service_and_api(tracking, client, monkeypatch):
    train.train(synthetic_games())
    service = ModelService(refresh_seconds=0)
    monkeypatch.setattr(main, "model_service", service)

    rpg = client.post(
        "/api/predictions/metacritic",
        json={"release_year": 2015, "genres": ["RPG"], "platforms": ["PC"], "tags": []},
    ).json()
    casual = client.post(
        "/api/predictions/metacritic",
        json={"release_year": 2015, "genres": ["Casual"], "platforms": ["PC"], "tags": []},
    ).json()
    assert rpg["model_name"] == MODEL_NAME
    assert rpg["predicted_metacritic"] > casual["predicted_metacritic"]

    by_id = client.get("/api/games/1/predicted-metacritic").json()
    assert by_id["game_id"] == 1 and 0 <= by_id["predicted_metacritic"] <= 100

    info = client.get("/api/ml/model").json()
    assert info["model_version"] == "1" and "test_mae" in info["metrics"]
    assert client.post("/api/ml/reload").status_code == 200

    # The registered model loads on its own (feature code is pickled by value).
    loaded = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{CHAMPION_ALIAS}")
    assert loaded.metadata.signature.inputs.input_names() == features.INPUT_COLUMNS


def test_champion_with_older_inputs_still_works(tracking):
    """A champion logged before the input columns grew must still be served and compared.

    MLflow drops input columns the model's signature does not list, so the new, wider
    rows reach the old model as the narrower rows it was trained on.
    """
    from sklearn.dummy import DummyRegressor

    legacy_columns = ["release_year", "genres", "platforms", "tags"]
    games = synthetic_games()
    old_inputs = games[legacy_columns]
    old_model = DummyRegressor(constant=70.0, strategy="constant").fit(
        old_inputs, games["metacritic"]
    )
    with mlflow.start_run():
        mlflow.sklearn.log_model(
            old_model,
            name="model",
            registered_model_name=MODEL_NAME,
            signature=mlflow.models.infer_signature(old_inputs.head(5)),
            serialization_format="cloudpickle",
        )
    tracking.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, "1")

    new_rows = games[features.INPUT_COLUMNS]
    assert ModelService(refresh_seconds=0).predict(new_rows.head(2)) == [70.0, 70.0]
    mae, version = train.champion_mae(tracking, new_rows, games["metacritic"].to_numpy())
    assert version == "1" and mae is not None


def test_api_returns_503_without_a_model(client, monkeypatch):
    class NoModel(ModelService):
        def _resolve(self):
            raise ModelUnavailableError("No 'champion' version yet")

    monkeypatch.setattr(main, "model_service", NoModel())
    response = client.post("/api/predictions/metacritic", json={"genres": ["RPG"]})
    assert response.status_code == 503
    assert "champion" in response.json()["detail"]
    assert client.get("/api/ml/model").status_code == 503
    assert client.get("/api/games/1/predicted-metacritic").status_code == 503


def test_invalid_features_are_rejected(client):
    assert (
        client.post("/api/predictions/metacritic", json={"release_year": 1800}).status_code == 422
    )
