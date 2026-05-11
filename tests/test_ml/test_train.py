"""Tests for the Upset Tracker training pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def test_temporal_split_keeps_latest_rows_for_holdout(upset_feature_frame: pd.DataFrame) -> None:
    """Temporal split must keep the newest matches in the test set."""
    from ml.train import temporal_train_test_split

    train_df, test_df = temporal_train_test_split(upset_feature_frame, test_fraction=0.2)

    assert len(train_df) == 32
    assert len(test_df) == 8
    assert train_df["played_at"].max() < test_df["played_at"].min()


def test_training_accepts_snowflake_uppercase_columns(
    upset_feature_frame: pd.DataFrame,
    ml_artifact_root: Path,
) -> None:
    """Snowflake fetch_pandas_all returns uppercase labels unless quoted."""
    from ml.train import train_upset_tracker

    snowflake_frame = upset_feature_frame.rename(columns=str.upper)

    result = train_upset_tracker(
        snowflake_frame,
        artifact_root=ml_artifact_root,
        version="v-uppercase",
    )

    assert result.model_path.exists()


def test_feature_contract_excludes_post_match_leakage_columns() -> None:
    """Prediction features must be knowable before a match starts."""
    from ml.train import FEATURE_COLUMNS

    leaked_columns = {"score_diff", "total_rounds", "is_overtime"}

    assert leaked_columns.isdisjoint(FEATURE_COLUMNS)


def test_training_accepts_prediction_time_features_without_post_match_columns(
    upset_feature_frame: pd.DataFrame,
    ml_artifact_root: Path,
) -> None:
    """Training should not require final-score features that are unavailable pre-match."""
    from ml.train import train_upset_tracker

    prediction_time_frame = upset_feature_frame.drop(
        columns=["score_diff", "total_rounds", "is_overtime"]
    )

    result = train_upset_tracker(
        prediction_time_frame,
        artifact_root=ml_artifact_root,
        version="v-pregame",
    )

    assert result.model_path.exists()


def test_training_accepts_null_boolean_features(
    upset_feature_frame: pd.DataFrame,
    ml_artifact_root: Path,
) -> None:
    """Warehouse booleans can be null for series-level rows and should impute safely."""
    from ml.train import train_upset_tracker

    frame = upset_feature_frame.copy()
    frame["is_overtime"] = frame["is_overtime"].astype(object)
    frame["is_cross_region"] = frame["is_cross_region"].astype(object)
    frame.loc[0, "is_overtime"] = None
    frame.loc[1, "is_cross_region"] = None

    result = train_upset_tracker(
        frame,
        artifact_root=ml_artifact_root,
        version="v-null-bools",
    )

    assert result.model_path.exists()


def test_train_upset_tracker_writes_model_and_evaluation_artifacts(
    upset_feature_frame: pd.DataFrame,
    ml_artifact_root: Path,
) -> None:
    """Training should save a versioned model plus local evaluation artifacts."""
    from ml.train import train_upset_tracker

    result = train_upset_tracker(
        upset_feature_frame,
        artifact_root=ml_artifact_root,
        version="v-test",
    )

    assert result.model_path == ml_artifact_root / "models" / "upset_tracker_v-test.joblib"
    assert result.model_path.exists()
    assert result.metrics_path.exists()
    assert result.roc_auc_path.exists()
    assert result.threshold_path.exists()
    assert result.calibration_curve_path.exists()
    assert result.confusion_matrix_path.exists()
    assert 0.0 <= result.metrics["roc_auc"] <= 1.0
    assert 0.0 <= result.metrics["decision_threshold"] <= 1.0
    assert 0.0 <= result.metrics["precision"] <= 1.0
    assert 0.0 <= result.metrics["recall"] <= 1.0
    assert 0.0 <= result.metrics["f2"] <= 1.0


def test_best_fbeta_threshold_respects_positive_rate_cap() -> None:
    """Threshold tuning should avoid alerting above the validation base rate."""
    from ml.train import best_fbeta_threshold

    y_true = pd.Series([0, 0, 0, 1])
    probabilities = pd.Series([0.10, 0.40, 0.50, 0.60])

    threshold = best_fbeta_threshold(
        y_true,
        probabilities,
        beta=0.75,
        max_positive_rate=0.25,
    )

    predictions = (probabilities >= threshold).astype(int)

    assert float(predictions.mean()) <= 0.25
