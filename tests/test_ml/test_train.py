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
    assert result.calibration_curve_path.exists()
    assert result.confusion_matrix_path.exists()
    assert 0.0 <= result.metrics["roc_auc"] <= 1.0
