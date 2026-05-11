from __future__ import annotations

from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch

from dashboard import export_snapshots
from dashboard.lib.snowflake import MartSnapshot


def test_export_snapshot_cli_exports_selected_marts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    exported: list[tuple[str, Path]] = []

    def fake_export_mart_snapshot(
        mart_name: str,
        *,
        snapshot_dir: Path,
        sql: str | None = None,
    ) -> MartSnapshot:
        assert sql is None
        path = snapshot_dir / f"{mart_name}.parquet"
        exported.append((mart_name, snapshot_dir))
        return MartSnapshot(
            name=mart_name,
            frame=pd.DataFrame({"id": [1, 2]}),
            loaded_at=None,
            path=path,
        )

    monkeypatch.setattr(
        "dashboard.export_snapshots.export_mart_snapshot",
        fake_export_mart_snapshot,
    )

    exit_code = export_snapshots.main(
        [
            "--snapshot-dir",
            str(tmp_path),
            "--mart",
            "mart_upset_features",
            "--mart",
            "mart_hidden_gems",
        ]
    )

    assert exit_code == 0
    assert exported == [
        ("mart_upset_features", tmp_path),
        ("mart_hidden_gems", tmp_path),
    ]
