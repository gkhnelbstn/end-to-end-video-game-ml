"""Train the Metacritic model, track it in MLflow and promote it if it is better.

    python -m src.ml.train            # uses DATABASE_URL and MLFLOW_TRACKING_URI

One training run:
1. loads every game with a Metacritic score from the database;
2. holds out about 20% of games as the test set, chosen by a hash of the game id, so a
   game stays on the same side of the split as the database grows and no model is ever
   trained on a game it is later compared on;
3. cross-validates each candidate on the training part, each in a nested MLflow run;
4. refits the candidate with the best CV MAE, scores it on the test set, logs the model,
   and registers it as a new version of `metacritic-predictor`;
5. moves the `champion` alias to the new version only if it beats both the mean-score
   baseline and the current champion on the same test set.
"""

import argparse
import json
import logging
import math
import os
import sys
import tempfile
import time

import cloudpickle
import mlflow
import numpy as np
import pandas as pd
import sklearn
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_score

from src.backend.database import SessionLocal
from src.ml import CHAMPION_ALIAS, EXPERIMENT_NAME, MODEL_NAME, features
from src.ml.data import load_dataset

logger = logging.getLogger(__name__)

SEED = 42
TEST_SIZE = 0.2
CV_FOLDS = 5
DEFAULT_MIN_ROWS = 200


def candidates() -> dict:
    """Name -> (pipeline, hyper-parameters to log)."""
    ridge_alpha = 3.0
    hgb = {"learning_rate": 0.05, "max_iter": 300, "max_leaf_nodes": 31, "l2_regularization": 1.0}
    return {
        "baseline_mean": (features.build_pipeline(DummyRegressor(strategy="mean")), {}),
        "ridge": (features.build_pipeline(Ridge(alpha=ridge_alpha)), {"alpha": ridge_alpha}),
        "hist_gradient_boosting": (
            features.build_pipeline(
                HistGradientBoostingRegressor(random_state=SEED, early_stopping=False, **hgb),
                dense=True,
            ),
            hgb,
        ),
    }


def is_test_game(game_ids: pd.Series) -> np.ndarray:
    """Stable split: a game is in the test set iff a hash of its id falls below TEST_SIZE.

    A seeded random split reshuffles every row whenever a game is added, so the previous
    champion would be scored on games it was trained on and would look unbeatable.
    """
    hashed = (game_ids.to_numpy(dtype=np.uint64) * np.uint64(2654435761)) % np.uint64(2**32)
    return hashed / 2**32 < TEST_SIZE


def regression_metrics(y_true, y_pred, prefix: str) -> dict[str, float]:
    y_pred = np.clip(y_pred, 0, 100)
    return {
        f"{prefix}_mae": float(mean_absolute_error(y_true, y_pred)),
        f"{prefix}_rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        f"{prefix}_r2": float(r2_score(y_true, y_pred)),
    }


def group_importance(model, x_test: pd.DataFrame, y_test, repeats: int = 5) -> dict[str, float]:
    """Permutation importance per input column: how much test MAE rises when it is shuffled."""
    rng = np.random.default_rng(SEED)
    base = mean_absolute_error(y_test, np.clip(model.predict(x_test), 0, 100))
    importance = {}
    for column in features.INPUT_COLUMNS:
        increases = []
        for _ in range(repeats):
            shuffled = x_test.copy()
            shuffled[column] = rng.permutation(shuffled[column].to_numpy())
            increases.append(
                mean_absolute_error(y_test, np.clip(model.predict(shuffled), 0, 100)) - base
            )
        importance[column] = float(np.mean(increases))
    return importance


def champion_mae(client: MlflowClient, x_test, y_test) -> tuple[float | None, str | None]:
    """Test MAE of the current champion, or (None, None) if there is none or it fails."""
    try:
        version = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
    except mlflow.exceptions.MlflowException:
        return None, None
    try:
        model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@{CHAMPION_ALIAS}")
        predictions = np.asarray(model.predict(x_test), dtype=float)
    except Exception:
        logger.exception("Could not score champion version %s; replacing it", version.version)
        return None, str(version.version)
    mae = float(mean_absolute_error(y_test, np.clip(predictions, 0, 100)))
    return mae, str(version.version)


def train(frame: pd.DataFrame, min_rows: int = DEFAULT_MIN_ROWS) -> dict:
    """Train on a dataset as returned by `data.load_dataset`. Returns a summary."""
    if len(frame) < min_rows:
        message = f"only {len(frame)} games have a Metacritic score; need {min_rows}"
        logger.warning("Skipping training: %s", message)
        return {"status": "skipped", "reason": message}

    test_mask = is_test_game(frame["game_id"])
    x = frame[features.INPUT_COLUMNS]
    y = frame["metacritic"].to_numpy()
    x_train, x_test = x[~test_mask], x[test_mask]
    y_train, y_test = y[~test_mask], y[test_mask]
    cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=SEED)

    mlflow.set_experiment(EXPERIMENT_NAME)
    client = MlflowClient()
    with mlflow.start_run(run_name=f"train-{time.strftime('%Y%m%d-%H%M%S')}") as parent:
        mlflow.log_params(
            {
                "n_games": len(frame),
                "n_train": len(x_train),
                "n_test": len(x_test),
                "test_size": TEST_SIZE,
                "cv_folds": CV_FOLDS,
                "seed": SEED,
                "min_feature_variance": features.MIN_FEATURE_VARIANCE,
                **{f"n_{s}": int(n) for s, n in frame["source"].value_counts().items()},
            }
        )
        mlflow.log_input(
            mlflow.data.from_pandas(
                frame[[*features.INPUT_COLUMNS, "metacritic"]],
                name="games-with-metacritic",
                targets="metacritic",
            ),
            context="training",
        )

        results = {}
        for name, (pipeline, params) in candidates().items():
            with mlflow.start_run(run_name=name, nested=True):
                mlflow.log_params({"model": name, **params})
                scores = -cross_val_score(
                    pipeline, x_train, y_train, cv=cv, scoring="neg_mean_absolute_error"
                )
                pipeline.fit(x_train, y_train)
                metrics = {
                    "cv_mae": float(scores.mean()),
                    "cv_mae_std": float(scores.std()),
                    **regression_metrics(y_test, pipeline.predict(x_test), "test"),
                }
                mlflow.log_metrics(metrics)
                results[name] = {"pipeline": pipeline, "metrics": metrics}
            logger.info("%s: %s", name, metrics)

        best_name = min(
            (n for n in results if n != "baseline_mean"),
            key=lambda n: results[n]["metrics"]["cv_mae"],
        )
        best = results[best_name]
        baseline_mae = results["baseline_mean"]["metrics"]["test_mae"]
        test_mae = best["metrics"]["test_mae"]
        importance = group_importance(best["pipeline"], x_test, y_test)
        n_features = int(best["pipeline"].named_steps["drop_rare"].get_support().sum())

        mlflow.log_params({"best_model": best_name, "n_features": n_features})
        mlflow.log_metrics(
            {
                **best["metrics"],
                "baseline_test_mae": baseline_mae,
                **{f"importance_{k}": v for k, v in importance.items()},
            }
        )
        mlflow.log_dict({n: r["metrics"] for n, r in results.items()}, "candidates.json")
        mlflow.log_dict(importance, "permutation_importance.json")
        _log_worst_errors(frame.loc[x_test.index], best["pipeline"].predict(x_test))

        # Keep the feature code inside the pickle so the model loads without this repo.
        cloudpickle.register_pickle_by_value(features)
        try:
            info = mlflow.sklearn.log_model(
                best["pipeline"],
                name="model",
                registered_model_name=MODEL_NAME,
                signature=infer_signature(
                    x_train.head(50), best["pipeline"].predict(x_train.head(50))
                ),
                input_example=x_train.head(3),
                serialization_format="cloudpickle",
                pip_requirements=[
                    f"scikit-learn=={sklearn.__version__}",
                    f"pandas=={pd.__version__}",
                    f"numpy=={np.__version__}",
                    f"cloudpickle=={cloudpickle.__version__}",
                ],
            )
        finally:
            cloudpickle.unregister_pickle_by_value(features)
        version = str(info.registered_model_version)

        previous_mae, previous_version = champion_mae(client, x_test, y_test)
        beats_baseline = test_mae < baseline_mae
        beats_champion = previous_mae is None or test_mae < previous_mae
        promoted = beats_baseline and beats_champion
        if promoted:
            client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, version)
        for key, value in {
            "test_mae": f"{test_mae:.3f}",
            "baseline_test_mae": f"{baseline_mae:.3f}",
            "promoted": str(promoted).lower(),
        }.items():
            client.set_model_version_tag(MODEL_NAME, version, key, value)
        mlflow.log_metric("promoted", float(promoted))
        if previous_mae is not None:
            mlflow.log_metric("champion_test_mae", previous_mae)

    summary = {
        "status": "trained",
        "run_id": parent.info.run_id,
        "best_model": best_name,
        "model_version": version,
        "promoted": promoted,
        "previous_champion_version": previous_version,
        "previous_champion_test_mae": previous_mae,
        "baseline_test_mae": baseline_mae,
        **best["metrics"],
        "n_games": len(frame),
        "n_features": n_features,
        "importance": importance,
    }
    logger.info("Training summary: %s", json.dumps(summary, default=str))
    return summary


def _log_worst_errors(test_frame: pd.DataFrame, predictions, n: int = 25) -> None:
    errors = test_frame[["game_id", "name", "metacritic"]].copy()
    errors["predicted"] = np.clip(predictions, 0, 100).round(1)
    errors["abs_error"] = (errors["predicted"] - errors["metacritic"]).abs().round(1)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "largest_test_errors.csv")
        errors.sort_values("abs_error", ascending=False).head(n).to_csv(path, index=False)
        mlflow.log_artifact(path)


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--min-rows",
        type=int,
        default=int(os.environ.get("ML_MIN_TRAINING_ROWS", DEFAULT_MIN_ROWS)),
        help="skip training when fewer games have a Metacritic score",
    )
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        frame = load_dataset(db)
    return train(frame, min_rows=args.min_rows)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = main()
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0)
