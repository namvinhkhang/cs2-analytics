"""Tests for the HLTV unofficial round-history bootstrap CLI."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cs2_analytics.utils.s3 import build_s3_key
from scripts import bootstrap_hltv_round_history


def _write_valid_mapstats(path: Path, *, map_stats_id: int = 49968) -> None:
    """Write one compact cached HLTV payload that produces one round row."""
    path.write_text(
        json.dumps(
            {
                "id": map_stats_id,
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


def test_bootstrap_hltv_round_history_writes_local_parquet_from_json_cache(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "hltv-json"
    output_path = tmp_path / "round_history.parquet"
    input_dir.mkdir()
    _write_valid_mapstats(input_dir / "49968.json")

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


def test_batch_id_builds_safe_upload_filename() -> None:
    filename = bootstrap_hltv_round_history._resolve_upload_filename(
        filename=None,
        batch_id="current_sample_001",
    )

    assert filename == "batch_current_sample_001.parquet"


def test_upload_without_filename_uses_unique_timestamped_filename() -> None:
    filename = bootstrap_hltv_round_history._resolve_upload_filename(
        filename=None,
        batch_id=None,
    )

    assert filename.startswith("round_history_")
    assert filename.endswith(".parquet")
    assert filename != "data.parquet"


@pytest.mark.parametrize(
    "unsafe",
    ["nested/data.parquet", "../data.parquet", "nested\\data.parquet"],
)
def test_upload_filename_rejects_path_separators(unsafe: str) -> None:
    with pytest.raises(ValueError, match="filename must not contain path separators"):
        bootstrap_hltv_round_history._resolve_upload_filename(
            filename=unsafe,
            batch_id=None,
        )


def test_upload_skips_existing_s3_batch_without_overwriting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "hltv-json"
    input_dir.mkdir()
    _write_valid_mapstats(input_dir / "49968.json")
    mock_write = MagicMock()
    expected_key = build_s3_key(
        "hltv_unofficial",
        "round_history",
        2026,
        5,
        11,
        filename="batch_current_sample_001.parquet",
    )

    monkeypatch.setattr(bootstrap_hltv_round_history, "write_round_history_to_s3", mock_write)
    monkeypatch.setattr(
        bootstrap_hltv_round_history,
        "_s3_key_exists",
        lambda bucket, key, region: key == expected_key,
    )
    monkeypatch.setattr(
        bootstrap_hltv_round_history,
        "settings",
        SimpleNamespace(aws_s3_bucket="test-bucket", aws_region="us-east-1"),
    )

    exit_code = bootstrap_hltv_round_history.main(
        [
            "--input-dir",
            str(input_dir),
            "--ingest-date",
            "2026-05-11",
            "--upload-s3",
            "--batch-id",
            "current_sample_001",
        ]
    )

    assert exit_code == 0
    assert mock_write.call_count == 0


def test_batch_summary_counts_invalid_json_without_blocking_valid_map(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "hltv-json"
    output_path = tmp_path / "round_history.parquet"
    input_dir.mkdir()
    _write_valid_mapstats(input_dir / "49968.json")
    (input_dir / "invalid.json").write_text("{not-json", encoding="utf-8")

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
    output = capsys.readouterr().out
    assert "scanned 2 JSON files" in output
    assert "parsed 1 valid maps" in output
    assert "skipped 1 invalid or empty files" in output
    assert "wrote 1 round rows" in output


def test_upload_empty_batch_does_not_report_fake_s3_none_destination(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "hltv-json"
    input_dir.mkdir()
    (input_dir / "invalid.json").write_text("{not-json", encoding="utf-8")
    mock_write = MagicMock(return_value=None)

    monkeypatch.setattr(bootstrap_hltv_round_history, "write_round_history_to_s3", mock_write)
    monkeypatch.setattr(
        bootstrap_hltv_round_history,
        "_s3_key_exists",
        lambda bucket, key, region: False,
    )
    monkeypatch.setattr(
        bootstrap_hltv_round_history,
        "settings",
        SimpleNamespace(aws_s3_bucket="test-bucket", aws_region="us-east-1"),
    )

    exit_code = bootstrap_hltv_round_history.main(
        [
            "--input-dir",
            str(input_dir),
            "--ingest-date",
            "2026-05-11",
            "--upload-s3",
            "--batch-id",
            "empty_batch",
        ]
    )

    assert exit_code == 0
    assert mock_write.call_count == 1
    output = capsys.readouterr().out
    assert "wrote 0 round rows" in output
    assert "s3://test-bucket/None" not in output
