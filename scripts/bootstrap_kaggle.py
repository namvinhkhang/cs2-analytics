#!/usr/bin/env python3
"""One-time Kaggle CSV bootstrap script.

Downloads the HLTV historical CS2 match dataset from Kaggle, converts CSVs
to Parquet, and uploads to S3 under raw/kaggle/matches/year=.../month=.../day=.../

Usage:
    uv run python scripts/bootstrap_kaggle.py

Required environment variables (set in .env or shell):
    CS2_KAGGLE_USERNAME   -- Kaggle username
    CS2_KAGGLE_KEY        -- Kaggle API key
    CS2_AWS_S3_BUCKET     -- S3 bucket for raw data
    CS2_AWS_REGION        -- AWS region (default: us-east-1)

Note: This is a one-time operation. Re-running overwrites existing S3 objects
at the same path (idempotent).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Add project src to path when running as a script directly with:
#   uv run python scripts/bootstrap_kaggle.py
# This ensures the cs2_analytics package is importable without requiring
# a full `pip install -e .` in the current environment.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cs2_analytics.ingestion.kaggle import KaggleBootstrapIngester
from cs2_analytics.utils.config import settings
import structlog

logger = structlog.get_logger()


def main() -> None:
    """Run the Kaggle bootstrap."""
    ingester = KaggleBootstrapIngester(
        bucket=settings.aws_s3_bucket,
        region=settings.aws_region,
    )

    ingest_date = date.today()
    logger.info(
        "kaggle_bootstrap_starting",
        date=ingest_date.isoformat(),
        bucket=settings.aws_s3_bucket,
    )

    total = ingester.download_and_ingest(
        username=settings.kaggle_username,
        key=settings.kaggle_key,
        ingest_date=ingest_date,
    )

    logger.info("kaggle_bootstrap_finished", total_records=total)
    print(f"Bootstrap complete: {total} match records written to s3://{settings.aws_s3_bucket}/raw/kaggle/")


if __name__ == "__main__":
    main()
