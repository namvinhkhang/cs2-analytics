"""HLTV unofficial round-history ingestion helpers.

The live fetching layer is intentionally decoupled from parsing. A small Node
helper can export HLTV mapstats JSON to disk, and this Python module turns those
cached payloads into compact Parquet rows. That keeps reruns gentle on HLTV and
lets the warehouse ingest a stable, auditable raw contract.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import structlog
from pydantic import ValidationError

from cs2_analytics.models.hltv import HLTVMatchMapStats
from cs2_analytics.utils.parquet import HLTV_ROUND_HISTORY_SCHEMA
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

logger = structlog.get_logger()


def parse_hltv_map_stats_files(
    paths: Iterable[Path],
    *,
    ingested_at: date,
) -> list[dict[str, Any]]:
    """Parse cached HLTV mapstats JSON exports into raw round rows."""
    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stats = HLTVMatchMapStats.model_validate(payload)
            map_records = stats.to_round_records(ingested_at=ingested_at.isoformat())
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.warning(
                "hltv_map_stats_file_skipped",
                path=str(path),
                reason=str(exc),
            )
            continue

        if not map_records:
            logger.warning("hltv_map_stats_file_skipped_empty_round_history", path=str(path))
            continue

        records.extend(map_records)
        logger.info(
            "hltv_map_stats_file_parsed",
            path=str(path),
            map_stats_id=str(stats.id),
            rounds=len(map_records),
        )
    return records


def write_round_history_parquet(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write normalized HLTV round-history rows to a local Parquet file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(records, schema=HLTV_ROUND_HISTORY_SCHEMA)
    pq.write_table(table, output_path, compression="snappy")


def write_round_history_to_s3(
    records: list[dict[str, Any]],
    *,
    bucket: str,
    ingest_date: date,
    filename: str = "data.parquet",
    region: str = "us-east-1",
) -> str | None:
    """Persist normalized HLTV round history to the existing raw S3 layout."""
    if not records:
        logger.info("hltv_round_history_no_records")
        return None

    key = build_s3_key(
        "hltv_unofficial",
        "round_history",
        ingest_date.year,
        ingest_date.month,
        ingest_date.day,
        filename=filename,
    )
    write_parquet_to_s3(
        records=records,
        schema=HLTV_ROUND_HISTORY_SCHEMA,
        bucket=bucket,
        key=key,
        region=region,
    )
    return key
