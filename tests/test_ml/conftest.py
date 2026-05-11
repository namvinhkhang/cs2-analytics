"""Shared synthetic fixtures for Upset Tracker ML tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def upset_feature_frame() -> pd.DataFrame:
    """Return a deterministic mart_upset_features-like frame with both classes."""
    rows: list[dict[str, object]] = []
    for idx in range(40):
        is_upset = 1 if idx % 5 == 0 else 0
        rows.append(
            {
                "match_id": f"m-{idx:03d}",
                "played_at": pd.Timestamp("2024-01-01") + pd.Timedelta(days=idx),
                "ranking_delta": 5 + (idx % 11),
                "score_diff": -4 if is_upset else 4,
                "total_rounds": 24 + (idx % 10),
                "is_overtime": idx % 8 == 0,
                "is_cross_region": idx % 3 == 0,
                "team_a_ranking": 1 + (idx % 30),
                "team_b_ranking": 20 + (idx % 50),
                "is_upset": is_upset,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def ml_artifact_root(tmp_path: Path) -> Path:
    """Temporary artifact root matching the ml/ directory layout."""
    return tmp_path / "ml"
