#!/usr/bin/env python3
"""Bootstrap modern CS2 data from the public CS API into S3.

Uploads:
- raw/csapi/team_rankings/... from /rankings/
- raw/csapi/player_stats/... from /matches/ and /matches/{matchid}/stats
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from cs2_analytics.ingestion.csapi import CSAPIClient
from cs2_analytics.utils.config import settings

logger = structlog.get_logger()


def _read_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    """Read an integer environment override with a defensive fallback."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_using_default", name=name, value=raw_value, default=default)
        return default
    return max(value, minimum)


def _read_optional_int_env(name: str) -> int | None:
    """Read an optional integer environment override."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        return int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_ignored", name=name, value=raw_value)
        return None


def _read_float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    """Read a float environment override with a defensive fallback."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning(
            "invalid_float_env_using_default",
            name=name,
            value=raw_value,
            default=default,
        )
        return default
    return max(value, minimum)


def _read_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment override."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    logger.warning("invalid_bool_env_using_default", name=name, value=raw_value, default=default)
    return default


def _output_filename(offset: int, max_matches: int | None) -> str:
    """Choose an S3 object name that is safe for chunked bootstraps."""
    explicit_filename = os.environ.get("CS2_CSAPI_OUTPUT_FILENAME")
    if explicit_filename is not None and explicit_filename.strip():
        return explicit_filename.strip()
    if offset > 0 or max_matches is not None:
        match_count = "all" if max_matches is None else str(max_matches)
        return f"matches_offset_{offset}_count_{match_count}.parquet"
    return "data.parquet"


async def _run() -> tuple[int, int, int]:
    """Fetch modern ranking/player stat snapshots and upload them to S3."""
    ingest_date = date.today()
    match_limit = _read_int_env("CS2_CSAPI_MATCH_LIMIT", 100, minimum=1)
    match_offset = _read_int_env("CS2_CSAPI_MATCH_OFFSET", 0, minimum=0)
    match_pages = _read_int_env("CS2_CSAPI_MATCH_PAGES", 30, minimum=1)
    max_matches = _read_optional_int_env("CS2_CSAPI_MAX_MATCHES")
    request_delay_seconds = _read_float_env(
        "CS2_CSAPI_REQUEST_DELAY_SECONDS",
        1.0,
        minimum=0.0,
    )
    progress_interval = _read_int_env("CS2_CSAPI_PROGRESS_INTERVAL", 10, minimum=0)
    refresh_current_profiles = _read_bool_env("CS2_CSAPI_REFRESH_CURRENT_PROFILES", True)
    output_filename = _output_filename(match_offset, max_matches)

    logger.info(
        "csapi_bootstrap_config",
        match_limit=match_limit,
        match_offset=match_offset,
        match_pages=match_pages,
        max_matches=max_matches,
        request_delay_seconds=request_delay_seconds,
        progress_interval=progress_interval,
        refresh_current_profiles=refresh_current_profiles,
        output_filename=output_filename,
    )

    async with CSAPIClient() as client:
        ranking_count = await client.ingest_team_rankings(
            bucket=settings.aws_s3_bucket,
            ingest_date=ingest_date,
            region=settings.aws_region,
        )
        match_count = await client.ingest_matches(
            bucket=settings.aws_s3_bucket,
            ingest_date=ingest_date,
            limit=match_limit,
            offset=match_offset,
            pages=match_pages,
            max_matches=max_matches,
            request_delay_seconds=request_delay_seconds,
            progress_interval=progress_interval,
            output_filename=output_filename,
            region=settings.aws_region,
        )
        player_count = await client.ingest_player_stats(
            bucket=settings.aws_s3_bucket,
            ingest_date=ingest_date,
            limit=match_limit,
            offset=match_offset,
            pages=match_pages,
            max_matches=max_matches,
            request_delay_seconds=request_delay_seconds,
            progress_interval=progress_interval,
            output_filename=output_filename,
            refresh_current_profiles=refresh_current_profiles,
            region=settings.aws_region,
        )
    return ranking_count, match_count, player_count


def main() -> None:
    """Run CS API bootstrap."""
    logger.info("csapi_bootstrap_starting", bucket=settings.aws_s3_bucket)
    ranking_count, match_count, player_count = asyncio.run(_run())
    logger.info(
        "csapi_bootstrap_finished",
        team_rankings=ranking_count,
        matches=match_count,
        player_stats=player_count,
    )
    print(
        "CS API bootstrap complete: "
        f"{ranking_count} rankings, {match_count} matches, "
        f"and {player_count} player stats written "
        f"to s3://{settings.aws_s3_bucket}/raw/csapi/"
    )


if __name__ == "__main__":
    main()
