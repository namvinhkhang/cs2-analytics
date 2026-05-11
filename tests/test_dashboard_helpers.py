from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch

from dashboard.lib import ml
from dashboard.lib.snowflake import (
    MartSnapshot,
    data_freshness,
    export_mart_snapshot,
    load_mart_snapshot,
    load_mart_snapshot_cached,
    query_snowflake,
    snapshot_path,
)


def test_snapshot_path_and_load_mart_snapshot_read_parquet(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "match_id": ["m1", "m2"],
            "ranking_delta": [4, -3],
            "is_cross_region": [True, False],
        }
    )
    path = snapshot_path("mart_upset_features", snapshot_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)

    snapshot = load_mart_snapshot("mart_upset_features", snapshot_dir=tmp_path)

    assert snapshot.name == "mart_upset_features"
    assert snapshot.path == path
    assert snapshot.loaded_at is not None
    pd.testing.assert_frame_equal(snapshot.frame, frame)


def test_load_mart_snapshot_normalizes_snowflake_column_names(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "MATCH_ID": ["m1"],
            "RANKING_DELTA": [12],
            "IS_CROSS_REGION": [True],
        }
    )
    path = snapshot_path("mart_upset_features", snapshot_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)

    snapshot = load_mart_snapshot("mart_upset_features", snapshot_dir=tmp_path)

    assert list(snapshot.frame.columns) == ["match_id", "ranking_delta", "is_cross_region"]


def test_load_mart_snapshot_cached_works_without_streamlit_app(tmp_path: Path) -> None:
    frame = pd.DataFrame({"player_id": [1], "display_name": ["icy"]})
    path = snapshot_path("mart_hidden_gems", snapshot_dir=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)

    snapshot = load_mart_snapshot_cached("mart_hidden_gems", snapshot_dir=tmp_path, ttl_seconds=10)

    assert isinstance(snapshot, MartSnapshot)
    pd.testing.assert_frame_equal(snapshot.frame, frame)


def test_data_freshness_summarizes_snapshot_metadata(tmp_path: Path) -> None:
    loaded_at = pd.Timestamp("2026-05-11T12:00:00Z").to_pydatetime()
    snapshots = [
        MartSnapshot(
            name="mart_upset_features",
            frame=pd.DataFrame({"match_id": ["m1", "m2"]}),
            loaded_at=loaded_at,
            path=tmp_path / "mart_upset_features.parquet",
        )
    ]

    freshness = data_freshness(snapshots)

    assert freshness.to_dict(orient="records") == [
        {
            "product": "mart_upset_features",
            "rows": 2,
            "loaded_at": loaded_at,
            "snapshot_path": str(tmp_path / "mart_upset_features.parquet"),
        }
    ]


def test_export_mart_snapshot_writes_query_result(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    queried: dict[str, str] = {}
    frame = pd.DataFrame({"match_id": ["m1"], "is_upset": [True]})

    def fake_query_snowflake(sql: str) -> pd.DataFrame:
        queried["sql"] = sql
        return frame

    monkeypatch.setattr("dashboard.lib.snowflake.query_snowflake", fake_query_snowflake)

    snapshot = export_mart_snapshot("mart_upset_features", snapshot_dir=tmp_path)

    assert queried["sql"] == "select * from CS2_ANALYTICS.MARTS.mart_upset_features"
    assert snapshot.path == snapshot_path("mart_upset_features", snapshot_dir=tmp_path)
    pd.testing.assert_frame_equal(pd.read_parquet(snapshot.path), frame)


def test_query_snowflake_uses_environment_credentials(monkeypatch: MonkeyPatch) -> None:
    connections: list[dict[str, str]] = []

    class FakeCursor:
        def execute(self, sql: str) -> None:
            assert sql == "select 1"

        def fetch_pandas_all(self) -> pd.DataFrame:
            return pd.DataFrame({"value": [1]})

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            connections.append({"closed": "true"})

    def fake_connect(**kwargs: str) -> FakeConnection:
        connections.append(kwargs)
        return FakeConnection()

    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct")
    monkeypatch.setenv("SNOWFLAKE_USER", "user")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", "/tmp/key.p8")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "warehouse")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "database")
    monkeypatch.setattr("snowflake.connector.connect", fake_connect)

    result = query_snowflake("select 1")

    pd.testing.assert_frame_equal(result, pd.DataFrame({"value": [1]}))
    assert connections[0]["account"] == "acct"
    assert connections[0]["authenticator"] == "SNOWFLAKE_JWT"
    assert connections[-1] == {"closed": "true"}


def test_load_model_card_reads_markdown_and_metrics(tmp_path: Path) -> None:
    card_path = tmp_path / "MODEL_CARD.md"
    metrics_path = tmp_path / "metrics.json"
    card_path.write_text("# Upset Tracker\n\nModel details.\n", encoding="utf-8")
    metrics_path.write_text(json.dumps({"roc_auc": 0.72, "count": 3, "label": "holdout"}))

    card = ml.load_model_card(card_path, metrics_path=metrics_path)

    assert card.title == "Upset Tracker"
    assert card.body == "# Upset Tracker\n\nModel details.\n"
    assert card.metrics == {"roc_auc": 0.72, "count": 3.0}


def test_load_threshold_reads_saved_cutoff(tmp_path: Path) -> None:
    threshold_path = tmp_path / "decision_threshold.txt"
    threshold_path.write_text("0.3841\n", encoding="utf-8")

    assert ml.load_threshold(threshold_path) == 0.3841


def test_explain_upset_row_builds_feature_frame(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    @dataclass(frozen=True)
    class FakeExplanation:
        probability: float
        prediction: int
        threshold: float
        attributions: list[dict[str, float | str]]

    def fake_explain_prediction(
        *,
        model_path: Path,
        feature_row: pd.DataFrame,
        threshold_path: Path | None = None,
    ) -> FakeExplanation:
        captured["model_path"] = model_path
        captured["threshold_path"] = threshold_path
        captured["feature_row"] = feature_row.copy()
        return FakeExplanation(0.8, 1, 0.4, [])

    monkeypatch.setattr("ml.predict.explain_prediction", fake_explain_prediction)
    row = pd.Series(
        {
            "ranking_delta": 12,
            "is_cross_region": True,
            "team_a_ranking": 3,
            "team_b_ranking": 15,
            "score_diff": 10,
        }
    )
    model_path = tmp_path / "model.joblib"
    threshold_path = tmp_path / "threshold.txt"

    explanation = ml.explain_upset_row(row, model_path=model_path, threshold_path=threshold_path)

    assert explanation.prediction == 1
    assert captured["model_path"] == model_path
    assert captured["threshold_path"] == threshold_path
    pd.testing.assert_frame_equal(
        captured["feature_row"],
        pd.DataFrame(
            [
                {
                    "ranking_delta": 12,
                    "is_cross_region": True,
                    "team_a_ranking": 3,
                    "team_b_ranking": 15,
                }
            ]
        ),
    )


def test_score_upset_frame_adds_probability_column(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeModel:
        def predict_proba(self, features: pd.DataFrame) -> list[list[float]]:
            assert features.to_dict(orient="records") == [
                {
                    "ranking_delta": 12,
                    "is_cross_region": 1,
                    "team_a_ranking": 3,
                    "team_b_ranking": 15,
                },
                {
                    "ranking_delta": 4,
                    "is_cross_region": 0,
                    "team_a_ranking": 7,
                    "team_b_ranking": 11,
                },
            ]
            return [[0.2, 0.8], [0.7, 0.3]]

    def fake_load(model_path: Path) -> FakeModel:
        assert model_path == tmp_path / "model.joblib"
        return FakeModel()

    monkeypatch.setattr("dashboard.lib.ml.joblib.load", fake_load)
    frame = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "ranking_delta": 12,
                "is_cross_region": True,
                "team_a_ranking": 3,
                "team_b_ranking": 15,
            },
            {
                "match_id": "m2",
                "ranking_delta": 4,
                "is_cross_region": False,
                "team_a_ranking": 7,
                "team_b_ranking": 11,
            },
        ]
    )

    scored = ml.score_upset_frame(frame, model_path=tmp_path / "model.joblib")

    assert scored["upset_probability"].tolist() == [0.8, 0.3]
    assert scored["match_id"].tolist() == ["m1", "m2"]
