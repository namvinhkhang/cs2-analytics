"""Tests for the HLTV unofficial round-history bootstrap CLI."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import bootstrap_hltv_round_history


def test_bootstrap_hltv_round_history_writes_local_parquet_from_json_cache(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "hltv-json"
    output_path = tmp_path / "round_history.parquet"
    input_dir.mkdir()
    (input_dir / "49968.json").write_text(
        json.dumps(
            {
                "id": 49968,
                "matchId": 2306295,
                "map": "Mirage",
                "date": 1713139200000,
                "team1": {"id": 6667, "name": "FaZe"},
                "team2": {"id": 4608, "name": "Natus Vincere"},
                "roundHistory": [
                    {"outcome": "ct_win", "score": "1-0", "tTeam": 6667, "ctTeam": 4608},
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = bootstrap_hltv_round_history.main(
        [
            "--input-dir",
            str(input_dir),
            "--output-path",
            str(output_path),
            "--ingest-date",
            "2026-05-11",
        ]
    )

    assert exit_code == 0
    assert output_path.exists()
