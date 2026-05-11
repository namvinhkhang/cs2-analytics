#!/usr/bin/env python3
"""Bootstrap modern CS2 data from the public CS API into S3.

Uploads:
- raw/csapi/team_rankings/... from /rankings/
- raw/csapi/player_stats/... from /matches/ and /matches/{matchid}/stats
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from cs2_analytics.ingestion.csapi import CSAPIClient
from cs2_analytics.utils.config import settings

logger = structlog.get_logger()


async def _run() -> tuple[int, int]:
    """Fetch modern ranking/player stat snapshots and upload them to S3."""
    ingest_date = date.today()
    async with CSAPIClient() as client:
        ranking_count = await client.ingest_team_rankings(
            bucket=settings.aws_s3_bucket,
            ingest_date=ingest_date,
            region=settings.aws_region,
        )
        player_count = await client.ingest_player_stats(
            bucket=settings.aws_s3_bucket,
            ingest_date=ingest_date,
            limit=100,
            pages=30,
            request_delay_seconds=1,
            region=settings.aws_region,
        )
    return ranking_count, player_count


def main() -> None:
    """Run CS API bootstrap."""
    logger.info("csapi_bootstrap_starting", bucket=settings.aws_s3_bucket)
    ranking_count, player_count = asyncio.run(_run())
    logger.info(
        "csapi_bootstrap_finished",
        team_rankings=ranking_count,
        player_stats=player_count,
    )
    print(
        "CS API bootstrap complete: "
        f"{ranking_count} rankings and {player_count} player stats written "
        f"to s3://{settings.aws_s3_bucket}/raw/csapi/"
    )


if __name__ == "__main__":
    main()
