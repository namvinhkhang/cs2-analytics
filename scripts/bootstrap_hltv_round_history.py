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
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
import structlog
from botocore.exceptions import ClientError

from cs2_analytics.ingestion.hltv import (
    parse_hltv_map_stats_files,
    write_round_history_parquet,
    write_round_history_to_s3,
)
from cs2_analytics.utils.config import settings
from cs2_analytics.utils.s3 import build_s3_key

logger = structlog.get_logger()


@dataclass(frozen=True)
class BatchSummary:
    """Operator-facing counters for one cached HLTV batch conversion."""

    scanned_files: int
    valid_map_files: int
    skipped_files: int
    round_rows: int


def _parse_date(value: str) -> date:
    """Parse YYYY-MM-DD dates for deterministic raw partitioning."""
    return date.fromisoformat(value)


def _validate_safe_filename(filename: str) -> str:
    """Reject filenames that could escape the raw partition directory."""
    if not filename.strip():
        raise ValueError("filename must not be empty")
    if "/" in filename or "\\" in filename or Path(filename).name != filename:
        raise ValueError("filename must not contain path separators")
    return filename


def _resolve_upload_filename(
    *,
    filename: str | None,
    batch_id: str | None,
) -> str:
    """Choose a non-overwriting raw object filename for HLTV batch uploads."""
    if filename is not None:
        return _validate_safe_filename(filename)
    if batch_id is not None:
        return _validate_safe_filename(f"batch_{batch_id}.parquet")

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    return f"round_history_{timestamp}.parquet"


def _s3_key_exists(bucket: str, key: str, region: str) -> bool:
    """Return True when a raw HLTV batch object already exists in S3."""
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _batch_summary(paths: Sequence[Path], records: list[dict[str, Any]]) -> BatchSummary:
    """Summarize parsed cache health without requiring a second JSON pass."""
    valid_map_ids = {
        str(record["map_stats_id"])
        for record in records
        if record.get("map_stats_id") is not None
    }
    valid_map_files = len(valid_map_ids)
    scanned_files = len(paths)
    return BatchSummary(
        scanned_files=scanned_files,
        valid_map_files=valid_map_files,
        skipped_files=max(scanned_files - valid_map_files, 0),
        round_rows=len(records),
    )


def _print_batch_summary(summary: BatchSummary, *, destination: str | None) -> None:
    """Print a compact batch summary for manual runs and Airflow logs."""
    print(f"scanned {summary.scanned_files:,} JSON files")
    print(f"parsed {summary.valid_map_files:,} valid maps")
    print(f"skipped {summary.skipped_files:,} invalid or empty files")
    print(f"wrote {summary.round_rows:,} round rows")
    if destination is not None:
        print(f"destination {destination}")


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
        help="Explicit raw object filename for --upload-s3. Must not contain path separators.",
    )
    parser.add_argument(
        "--batch-id",
        help="Human-readable batch ID for --upload-s3, written as batch_<id>.parquet.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the cached HLTV round-history bootstrap."""
    args = _parser().parse_args(argv)
    paths = sorted(args.input_dir.glob("*.json"))
    if not paths:
        raise SystemExit(f"No JSON files found in {args.input_dir}")

    records = parse_hltv_map_stats_files(paths, ingested_at=args.ingest_date)
    summary = _batch_summary(paths, records)
    destination: str | None = None
    if args.output_path is not None:
        write_round_history_parquet(records, args.output_path)
        destination = str(args.output_path)

    if args.upload_s3:
        upload_filename = _resolve_upload_filename(filename=args.filename, batch_id=args.batch_id)
        key = build_s3_key(
            "hltv_unofficial",
            "round_history",
            args.ingest_date.year,
            args.ingest_date.month,
            args.ingest_date.day,
            filename=upload_filename,
        )
        destination = f"s3://{args.bucket}/{key}"
        if _s3_key_exists(args.bucket, key, args.region):
            logger.info(
                "hltv_round_history_output_exists_skipping",
                bucket=args.bucket,
                key=key,
            )
            _print_batch_summary(summary, destination=destination)
            return 0
        key = write_round_history_to_s3(
            records,
            bucket=args.bucket,
            ingest_date=args.ingest_date,
            filename=upload_filename,
            region=args.region,
        )
        destination = f"s3://{args.bucket}/{key}" if key is not None else None

    if args.output_path is None and not args.upload_s3:
        raise SystemExit("Choose --output-path, --upload-s3, or both.")

    _print_batch_summary(summary, destination=destination)
    logger.info(
        "hltv_round_history_bootstrap_complete",
        files=summary.scanned_files,
        valid_maps=summary.valid_map_files,
        skipped_files=summary.skipped_files,
        records=summary.round_rows,
        destination=destination,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
