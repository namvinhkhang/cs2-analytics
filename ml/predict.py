"""Prediction-time SHAP explanations for the Upset Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
import shap

from ml.train import BOOLEAN_FEATURE_COLUMNS, DEFAULT_DECISION_THRESHOLD, FEATURE_COLUMNS


@dataclass(frozen=True)
class PredictionExplanation:
    """One prediction plus per-feature SHAP attributions."""

    probability: float
    prediction: int
    threshold: float
    attributions: list[dict[str, float | str]]


def load_decision_threshold(threshold_path: Path | None) -> float:
    """Load a saved decision threshold, falling back to the default cutoff."""
    if threshold_path is None:
        return DEFAULT_DECISION_THRESHOLD
    return float(threshold_path.read_text().strip())


def explain_prediction(
    *,
    model_path: Path,
    feature_row: pd.DataFrame,
    threshold_path: Path | None = None,
    shap_output_path: Path | None = None,
) -> PredictionExplanation:
    """Load a trained model and compute SHAP values for one match row."""
    if len(feature_row) != 1:
        raise ValueError("feature_row must contain exactly one row")

    model = joblib.load(model_path)
    features = feature_row[FEATURE_COLUMNS].copy()
    for column in BOOLEAN_FEATURE_COLUMNS:
        features[column] = features[column].fillna(False).astype(bool).astype(int)
    features = features.fillna(-1)

    probability = float(model.predict_proba(features)[:, 1][0])
    threshold = load_decision_threshold(threshold_path)
    prediction = int(probability >= threshold)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(features)
    row_values = shap_values[0]

    attribution_frame = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "value": features.iloc[0].to_list(),
            "shap_value": row_values,
        }
    )
    if shap_output_path is not None:
        shap_output_path.parent.mkdir(parents=True, exist_ok=True)
        attribution_frame.to_parquet(shap_output_path, index=False)

    attributions: list[dict[str, float | str]] = [
        {
            "feature": str(row["feature"]),
            "value": float(row["value"]),
            "shap_value": float(row["shap_value"]),
        }
        for row in attribution_frame.to_dict(orient="records")
    ]
    return PredictionExplanation(
        probability=probability,
        prediction=prediction,
        threshold=threshold,
        attributions=attributions,
    )
