"""Prediction-time SHAP explanations for the Upset Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd
import shap

from ml.train import FEATURE_COLUMNS


@dataclass(frozen=True)
class PredictionExplanation:
    """One prediction plus per-feature SHAP attributions."""

    probability: float
    attributions: list[dict[str, float | str]]


def explain_prediction(
    *,
    model_path: Path,
    feature_row: pd.DataFrame,
    shap_output_path: Path | None = None,
) -> PredictionExplanation:
    """Load a trained model and compute SHAP values for one match row."""
    if len(feature_row) != 1:
        raise ValueError("feature_row must contain exactly one row")

    model = joblib.load(model_path)
    features = feature_row[FEATURE_COLUMNS].copy()
    for column in ["is_overtime", "is_cross_region"]:
        features[column] = features[column].astype(int)
    features = features.fillna(-1)

    probability = float(model.predict_proba(features)[:, 1][0])
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
    return PredictionExplanation(probability=probability, attributions=attributions)
