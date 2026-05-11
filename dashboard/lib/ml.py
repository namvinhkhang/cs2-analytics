"""Model artifact helpers for dashboard pages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from ml import predict as upset_predict
from ml.predict import PredictionExplanation
from ml.train import BOOLEAN_FEATURE_COLUMNS, FEATURE_COLUMNS

DEFAULT_MODEL_PATH = Path("ml/models/upset_tracker_v1.0.joblib")
DEFAULT_THRESHOLD_PATH = Path("ml/evaluation/decision_threshold.txt")
DEFAULT_MODEL_CARD_PATH = Path("ml/MODEL_CARD.md")


@dataclass(frozen=True)
class ModelCard:
    """Model card content and numeric metrics for dashboard display."""

    title: str
    body: str
    metrics: dict[str, float]


def _model_card_title(body: str, path: Path) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("_", " ").title()


def _numeric_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in metrics.items()
        if isinstance(value, int | float) and not isinstance(value, bool)
    }


def load_model_card(
    path: Path = DEFAULT_MODEL_CARD_PATH,
    metrics_path: Path = Path("ml/evaluation/metrics.json"),
) -> ModelCard:
    """Read the model card markdown and optional numeric metrics."""
    body = path.read_text(encoding="utf-8")
    metrics: dict[str, float] = {}
    if metrics_path.exists():
        raw_metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if isinstance(raw_metrics, dict):
            metrics = _numeric_metrics(raw_metrics)
    return ModelCard(title=_model_card_title(body, path), body=body, metrics=metrics)


def load_threshold(path: Path = DEFAULT_THRESHOLD_PATH) -> float:
    """Read the persisted upset decision threshold."""
    return float(path.read_text(encoding="utf-8").strip())


def _feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"missing feature columns: {missing_columns}")

    features = frame[FEATURE_COLUMNS].copy()
    for column in BOOLEAN_FEATURE_COLUMNS:
        features[column] = features[column].fillna(False).astype(bool).astype(int)
    return features.fillna(-1)


def score_upset_frame(
    frame: pd.DataFrame,
    model_path: Path = DEFAULT_MODEL_PATH,
) -> pd.DataFrame:
    """Add model upset probabilities to a mart frame without SHAP overhead."""
    scored = frame.copy()
    if scored.empty:
        scored["upset_probability"] = pd.Series(dtype=float)
        return scored

    model = joblib.load(model_path)
    probabilities = pd.DataFrame(model.predict_proba(_feature_matrix(scored))).iloc[:, 1]
    scored["upset_probability"] = [float(probability) for probability in probabilities]
    return scored


def explain_upset_row(
    row: pd.Series,
    model_path: Path = DEFAULT_MODEL_PATH,
    threshold_path: Path = DEFAULT_THRESHOLD_PATH,
) -> PredictionExplanation:
    """Explain one mart row with the versioned upset model artifact."""
    missing_columns = [column for column in FEATURE_COLUMNS if column not in row.index]
    if missing_columns:
        raise ValueError(f"missing feature columns: {missing_columns}")

    feature_row = pd.DataFrame([{column: row[column] for column in FEATURE_COLUMNS}])
    return upset_predict.explain_prediction(
        model_path=model_path,
        feature_row=feature_row,
        threshold_path=threshold_path,
    )
