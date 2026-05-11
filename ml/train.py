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
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

FEATURE_COLUMNS: list[str] = [
    "ranking_delta",
    "is_cross_region",
    "team_a_ranking",
    "team_b_ranking",
]
BOOLEAN_FEATURE_COLUMNS: list[str] = ["is_cross_region"]
TARGET_COLUMN = "is_upset"
DATE_COLUMN = "played_at"
DEFAULT_DECISION_THRESHOLD = 0.5
DECISION_THRESHOLD_BETA = 0.75


@dataclass(frozen=True)
class TrainingResult:
    """Paths and metrics produced by one training run."""

    model_path: Path
    metrics_path: Path
    roc_auc_path: Path
    threshold_path: Path
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


def temporal_train_validation_test_split(
    frame: pd.DataFrame,
    *,
    validation_fraction: float = 0.2,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by `played_at` into train, validation, and newest holdout rows."""
    if frame.empty:
        raise ValueError("training frame cannot be empty")
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    if validation_fraction + test_fraction >= 1:
        raise ValueError("validation_fraction + test_fraction must be below 1")

    ordered = frame.sort_values(DATE_COLUMN).reset_index(drop=True)
    if len(ordered) < 3:
        raise ValueError("training frame must contain at least 3 rows")

    test_size = max(1, int(len(ordered) * test_fraction))
    validation_size = max(1, int(len(ordered) * validation_fraction))
    if validation_size + test_size >= len(ordered):
        validation_size = max(1, min(validation_size, len(ordered) - 2))
        test_size = max(1, min(test_size, len(ordered) - validation_size - 1))

    train_end = len(ordered) - validation_size - test_size
    validation_end = len(ordered) - test_size
    return (
        ordered.iloc[:train_end].copy(),
        ordered.iloc[train_end:validation_end].copy(),
        ordered.iloc[validation_end:].copy(),
    )


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
    for column in BOOLEAN_FEATURE_COLUMNS:
        features[column] = features[column].fillna(False).astype(bool).astype(int)
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


def best_fbeta_threshold(
    y_true: pd.Series,
    probabilities: Any,
    *,
    beta: float = DECISION_THRESHOLD_BETA,
    max_positive_rate: float | None = None,
) -> float:
    """Pick the probability threshold that maximizes F-beta on validation data."""
    if y_true.nunique() < 2:
        return DEFAULT_DECISION_THRESHOLD

    _, _, thresholds = precision_recall_curve(y_true, probabilities)
    if len(thresholds) == 0:
        return DEFAULT_DECISION_THRESHOLD

    best_threshold = DEFAULT_DECISION_THRESHOLD
    best_score = -1.0
    for threshold in thresholds:
        predictions = (probabilities >= threshold).astype(int)
        if max_positive_rate is not None and float(predictions.mean()) > max_positive_rate:
            continue
        score = float(fbeta_score(y_true, predictions, beta=beta, zero_division=0))
        if score > best_score:
            best_score = score
            best_threshold = float(threshold)
    return best_threshold


def _classification_metrics(
    y_true: pd.Series,
    probabilities: Any,
    *,
    threshold: float,
) -> dict[str, float]:
    """Compute threshold-aware holdout metrics for the positive upset class."""
    predictions = (probabilities >= threshold).astype(int)
    return {
        "roc_auc": _safe_roc_auc(y_true, probabilities),
        "decision_threshold": float(threshold),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "fbeta": float(
            fbeta_score(
                y_true,
                predictions,
                beta=DECISION_THRESHOLD_BETA,
                zero_division=0,
            )
        ),
        "f2": float(fbeta_score(y_true, predictions, beta=2.0, zero_division=0)),
        "threshold_beta": float(DECISION_THRESHOLD_BETA),
        "predicted_positive_rate": float(predictions.mean()),
    }


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
    train_df, validation_df, test_df = temporal_train_validation_test_split(training_frame)

    x_train = _feature_matrix(train_df)
    y_train = train_df[TARGET_COLUMN].astype(int)
    x_validation = _feature_matrix(validation_df)
    y_validation = validation_df[TARGET_COLUMN].astype(int)
    x_test = _feature_matrix(test_df)
    y_test = test_df[TARGET_COLUMN].astype(int)

    model = _new_model()
    model.fit(x_train, y_train)

    validation_probabilities = model.predict_proba(x_validation)[:, 1]
    decision_threshold = best_fbeta_threshold(
        y_validation,
        validation_probabilities,
        max_positive_rate=float(y_validation.mean()),
    )
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= decision_threshold).astype(int)
    metrics = _classification_metrics(
        y_test,
        probabilities,
        threshold=decision_threshold,
    )
    metrics["validation_positive_rate_cap"] = float(y_validation.mean())

    model_dir = artifact_root / "models"
    evaluation_dir = artifact_root / "evaluation"
    model_dir.mkdir(parents=True, exist_ok=True)
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    model_path = model_dir / f"upset_tracker_{version}.joblib"
    metrics_path = evaluation_dir / "metrics.json"
    roc_auc_path = evaluation_dir / "roc_auc.txt"
    threshold_path = evaluation_dir / "decision_threshold.txt"
    calibration_curve_path = evaluation_dir / "calibration_curve.png"
    confusion_matrix_path = evaluation_dir / "confusion_matrix.png"

    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    roc_auc_path.write_text(f"ROC-AUC: {metrics['roc_auc']:.4f}\n")
    threshold_path.write_text(f"{decision_threshold:.10f}\n")

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
        threshold_path=threshold_path,
        calibration_curve_path=calibration_curve_path,
        confusion_matrix_path=confusion_matrix_path,
        metrics=metrics,
    )


def main() -> None:
    """CLI entrypoint for local training."""
    train_upset_tracker()


if __name__ == "__main__":
    main()
