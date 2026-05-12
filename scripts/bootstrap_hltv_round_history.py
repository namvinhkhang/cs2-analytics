#!/usr/bin/env python3
"""Bootstrap unofficial HLTV round history from cached mapstats JSON exports.

This script does not scrape HLTV directly. Use the optional Node helper to cache
JSON files slowly and respectfully, then run this script to persist compact
round-history Parquet for Snowflake/dbt ingestion.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from cs2_analytics.ingestion.hltv import (
    parse_hltv_map_stats_files,
    write_round_history_parquet,
    write_round_history_to_s3,
)
from cs2_analytics.utils.config import settings

logger = structlog.get_logger()


def _parse_date(value: str) -> date:
    """Parse YYYY-MM-DD dates for deterministic raw partitioning."""
    return date.fromisoformat(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert cached HLTV mapstats JSON exports to round-history Parquet.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing one HLTV mapstats JSON export per map.",
    )
    parser.add_argument(
        "--ingest-date",
        type=_parse_date,
        default=date.today(),
        help="Raw partition date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="Optional local Parquet output path for inspection or manual upload.",
    )
    parser.add_argument(
        "--upload-s3",
        action="store_true",
        help="Upload parsed rows to S3 using the raw/hltv_unofficial/round_history layout.",
    )
    parser.add_argument(
        "--bucket",
        default=settings.aws_s3_bucket,
        help="S3 bucket for --upload-s3. Defaults to CS2_AWS_S3_BUCKET.",
    )
    parser.add_argument(
        "--region",
        default=settings.aws_region,
        help="AWS region for --upload-s3. Defaults to CS2_AWS_REGION.",
    )
    parser.add_argument(
        "--filename",
        default="data.parquet",
        help="Raw object filename for --upload-s3.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the cached HLTV round-history bootstrap."""
    args = _parser().parse_args(argv)
    paths = sorted(args.input_dir.glob("*.json"))
    if not paths:
        raise SystemExit(f"No JSON files found in {args.input_dir}")

    records = parse_hltv_map_stats_files(paths, ingested_at=args.ingest_date)
    if args.output_path is not None:
        write_round_history_parquet(records, args.output_path)
        print(f"wrote {len(records):,} HLTV round rows -> {args.output_path}")

    if args.upload_s3:
        key = write_round_history_to_s3(
            records,
            bucket=args.bucket,
            ingest_date=args.ingest_date,
            filename=args.filename,
            region=args.region,
        )
        print(f"uploaded {len(records):,} HLTV round rows -> s3://{args.bucket}/{key}")

    if args.output_path is None and not args.upload_s3:
        raise SystemExit("Choose --output-path, --upload-s3, or both.")

    logger.info("hltv_round_history_bootstrap_complete", files=len(paths), records=len(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
