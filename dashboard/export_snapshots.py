"""Command-line export for dashboard mart snapshots."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dashboard.lib.snowflake import DEFAULT_SNAPSHOT_DIR, export_mart_snapshot

DEFAULT_MARTS = ("mart_upset_features", "mart_hidden_gems")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Snowflake marts to local dashboard Parquet snapshots.",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=DEFAULT_SNAPSHOT_DIR,
        help="Directory where Parquet snapshots are written.",
    )
    parser.add_argument(
        "--mart",
        action="append",
        dest="marts",
        help="Mart name to export. May be passed multiple times.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Export selected dashboard marts from Snowflake."""
    args = _parser().parse_args(argv)
    marts = tuple(args.marts or DEFAULT_MARTS)
    for mart_name in marts:
        snapshot = export_mart_snapshot(mart_name, snapshot_dir=args.snapshot_dir)
        print(f"exported {snapshot.name}: {len(snapshot.frame):,} rows -> {snapshot.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
