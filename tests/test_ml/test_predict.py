"""Tests for prediction-time SHAP explanations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def test_explain_prediction_returns_feature_attributions(
    upset_feature_frame: pd.DataFrame,
    ml_artifact_root: Path,
) -> None:
    """A saved model should explain one match with one SHAP value per feature."""
    from ml.predict import explain_prediction
    from ml.train import FEATURE_COLUMNS, train_upset_tracker

    result = train_upset_tracker(
        upset_feature_frame,
        artifact_root=ml_artifact_root,
        version="v-test",
    )
    feature_row = upset_feature_frame.iloc[[0]][FEATURE_COLUMNS]

    explanation = explain_prediction(
        model_path=result.model_path,
        feature_row=feature_row,
        threshold_path=result.threshold_path,
        shap_output_path=ml_artifact_root / "shap" / "sample.parquet",
    )

    assert explanation.probability >= 0.0
    assert explanation.probability <= 1.0
    assert explanation.threshold == pytest.approx(result.metrics["decision_threshold"])
    assert explanation.prediction in {0, 1}
    assert explanation.prediction == int(
        explanation.probability >= result.metrics["decision_threshold"]
    )
    assert len(explanation.attributions) == len(FEATURE_COLUMNS)
    assert {item["feature"] for item in explanation.attributions} == set(FEATURE_COLUMNS)
    assert (ml_artifact_root / "shap" / "sample.parquet").exists()
