"""Serving the champion model inside the API process.

The model is loaded lazily from the MLflow registry (`models:/metacritic-predictor@champion`)
and the alias is re-checked at most every MODEL_REFRESH_SECONDS, so a newly promoted
version is picked up without restarting the API.
"""

import logging
import os
import threading
import time

import numpy as np
import pandas as pd

from src.ml import CHAMPION_ALIAS, MODEL_NAME

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """No champion model is registered yet, or MLflow cannot be reached."""


class ModelService:
    def __init__(self, refresh_seconds: float | None = None):
        self.refresh_seconds = (
            float(os.environ.get("MODEL_REFRESH_SECONDS", "60"))
            if refresh_seconds is None
            else refresh_seconds
        )
        self._lock = threading.Lock()
        self._model = None
        self._version = None
        self._checked_at = 0.0

    def _resolve(self):
        """The registry entry the champion alias points to (no artifacts downloaded)."""
        import mlflow
        from mlflow.tracking import MlflowClient

        try:
            return MlflowClient().get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
        except mlflow.exceptions.MlflowException as exc:
            raise ModelUnavailableError(
                f"No '{CHAMPION_ALIAS}' version of '{MODEL_NAME}' is registered yet. "
                "Train one with `python -m src.ml.train`."
            ) from exc
        except Exception as exc:  # connection errors from the tracking server
            raise ModelUnavailableError(f"MLflow is not reachable: {exc}") from exc

    def _ensure_loaded(self, force: bool = False):
        with self._lock:
            fresh = time.monotonic() - self._checked_at < self.refresh_seconds
            if self._model is not None and fresh and not force:
                return
            try:
                version = self._resolve()
            except ModelUnavailableError:
                if self._model is not None and not force:
                    # Keep serving the last good model if the registry is briefly down.
                    logger.warning(
                        "Could not re-check the champion; keeping version %s", self._version
                    )
                    self._checked_at = time.monotonic()
                    return
                raise
            if self._model is None or str(version.version) != self._version["version"]:
                import mlflow

                logger.info("Loading %s version %s", MODEL_NAME, version.version)
                try:
                    model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version.version}")
                except Exception as exc:
                    raise ModelUnavailableError(f"Could not load the model: {exc}") from exc
                from mlflow.tracking import MlflowClient

                metrics = MlflowClient().get_run(version.run_id).data.metrics
                self._model = model
                self._version = {
                    "version": str(version.version),
                    "run_id": version.run_id,
                    "metrics": {
                        k: v
                        for k, v in metrics.items()
                        if k.startswith(("test_", "cv_", "baseline_"))
                    },
                    "tracking_uri": mlflow.get_tracking_uri(),
                }
            self._checked_at = time.monotonic()

    def predict(self, frame: pd.DataFrame) -> list[float]:
        self._ensure_loaded()
        predictions = np.asarray(self._model.predict(frame), dtype=float)
        return [round(float(p), 1) for p in np.clip(predictions, 0, 100)]

    def info(self) -> dict:
        self._ensure_loaded()
        return {"model_name": MODEL_NAME, **self._version}

    def reload(self) -> dict:
        self._ensure_loaded(force=True)
        return self.info()


model_service = ModelService()
