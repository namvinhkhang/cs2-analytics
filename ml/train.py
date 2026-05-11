"""Train the Upset Tracker model from mart_upset_features data.

The pipeline keeps time ordering intact: the newest 20% of matches become the
holdout set so evaluation does not leak future results into training.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import matplotlib
import pandas as pd
from sklearn.calibration import CalibrationDisplay
from sklearn.metrics import ConfusionMatrixDisplay, roc_auc_score
from xgboost import XGBClassifier

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FEATURE_COLUMNS: list[str] = [
    "ranking_delta",
    "score_diff",
    "total_rounds",
    "is_overtime",
    "is_cross_region",
    "team_a_ranking",
    "team_b_ranking",
]
TARGET_COLUMN = "is_upset"
DATE_COLUMN = "played_at"


@dataclass(frozen=True)
class TrainingResult:
    """Paths and metrics produced by one training run."""

    model_path: Path
    metrics_path: Path
    roc_auc_path: Path
    calibration_curve_path: Path
    confusion_matrix_path: Path
    metrics: dict[str, float]


def load_features_from_snowflake(query: str | None = None) -> pd.DataFrame:
    """Load `mart_upset_features` through Snowflake key-pair auth.

    The import stays inside the function so unit tests can run without a live
    Snowflake dependency path or credentials.
    """
    import snowflake.connector

    sql = query or """
        select *
        from CS2_ANALYTICS.MARTS.mart_upset_features
        order by played_at asc
    """
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
    )
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetch_pandas_all()
    finally:
        conn.close()


def temporal_train_test_split(
    frame: pd.DataFrame,
    *,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by `played_at`, reserving the newest rows for holdout evaluation."""
    if frame.empty:
        raise ValueError("training frame cannot be empty")
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")

    ordered = frame.sort_values(DATE_COLUMN).reset_index(drop=True)
    split_index = int(len(ordered) * (1 - test_fraction))
    split_index = max(1, min(split_index, len(ordered) - 1))
    return ordered.iloc[:split_index].copy(), ordered.iloc[split_index:].copy()


def _normalize_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize warehouse column labels to the lowercase names used in code."""
    normalized = frame.copy()
    normalized.columns = [str(column).lower() for column in normalized.columns]
    return normalized


def _feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a numeric feature matrix with stable column order."""
    missing_columns = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"missing feature columns: {missing_columns}")

    features = frame[FEATURE_COLUMNS].copy()
    for column in ["is_overtime", "is_cross_region"]:
        features[column] = features[column].astype(int)
    return features.fillna(-1)


def _new_model() -> XGBClassifier:
    """Build the standard small tabular classifier for local and CI training."""
    return XGBClassifier(
        n_estimators=40,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=42,
    )


def _safe_roc_auc(y_true: pd.Series, probabilities: Any) -> float:
    """Compute ROC-AUC, falling back to 0.5 when the holdout has one class."""
    if y_true.nunique() < 2:
        return 0.5
    return float(roc_auc_score(y_true, probabilities))


def train_upset_tracker(
    frame: pd.DataFrame | None = None,
    *,
    artifact_root: Path = Path("ml"),
    version: str = "v1.0",
) -> TrainingResult:
    """Train, evaluate, and persist the Upset Tracker model."""
    training_frame = _normalize_feature_columns(
        frame if frame is not None else load_features_from_snowflake()
    )
    train_df, test_df = temporal_train_test_split(training_frame)

    x_train = _feature_matrix(train_df)
    y_train = train_df[TARGET_COLUMN].astype(int)
    x_test = _feature_matrix(test_df)
    y_test = test_df[TARGET_COLUMN].astype(int)

    model = _new_model()
    model.fit(x_train, y_train)

    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = model.predict(x_test)
    metrics = {"roc_auc": _safe_roc_auc(y_test, probabilities)}

    model_dir = artifact_root / "models"
    evaluation_dir = artifact_root / "evaluation"
    model_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / f"upset_tracker_{version}.joblib"
    metrics_path = evaluation_dir / "metrics.json"
    roc_auc_path = evaluation_dir / "roc_auc.txt"
    calibration_curve_path = evaluation_dir / "calibration_curve.png"
    confusion_matrix_path = evaluation_dir / "confusion_matrix.png"

    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    roc_auc_path.write_text(f"ROC-AUC: {metrics['roc_auc']:.4f}\n")

    fig, ax = plt.subplots()
    CalibrationDisplay.from_predictions(y_test, probabilities, ax=ax, n_bins=5)
    fig.savefig(calibration_curve_path, dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots()
    ConfusionMatrixDisplay.from_predictions(y_test, predictions, ax=ax)
    fig.savefig(confusion_matrix_path, dpi=150)
    plt.close(fig)

    return TrainingResult(
        model_path=model_path,
        metrics_path=metrics_path,
        roc_auc_path=roc_auc_path,
        calibration_curve_path=calibration_curve_path,
        confusion_matrix_path=confusion_matrix_path,
        metrics=metrics,
    )


def main() -> None:
    """CLI entrypoint for local training."""
    train_upset_tracker()


if __name__ == "__main__":
    main()
