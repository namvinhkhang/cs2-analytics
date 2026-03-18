"""Airflow DAG: cs2_weekly_rankings — sync CS2 team and player rankings weekly.

Ingests team and player data from Liquipedia into S3 as Parquet.
Applies S3 key existence idempotency: skips if this week's Parquet already exists.

Schedule: weekly (@weekly — Sunday midnight UTC)
Retry: 3 attempts with 10-minute exponential backoff
Alerting: Slack webhook via on_failure_callback on any task failure
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import boto3
import pendulum
import structlog
from airflow.decorators import dag, task
from botocore.exceptions import ClientError

from utils.slack_alerts import on_failure_callback

log = structlog.get_logger()


def _s3_key_exists(bucket: str, key: str) -> bool:
    """Return True if key exists in S3 bucket, False otherwise.

    Uses head_object to check existence without downloading.
    Raises ClientError for non-404 errors (e.g., 403 Forbidden).
    """
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise


async def _ingest_rankings(settings: object) -> int:
    """Run Liquipedia team rankings ingestion asynchronously."""
    from cs2_analytics.ingestion.liquipedia import LiquipediaClient
    from cs2_analytics.utils.config import Settings

    # asyncio.sleep(2.0) is inside LiquipediaClient fetch methods — do NOT add extra sleep here
    s: Settings = settings  # type: ignore[assignment]
    async with LiquipediaClient(api_key=s.liquipedia_api_key) as client:
        return await client.ingest_teams(bucket=s.aws_s3_bucket, region=s.aws_region)


async def _ingest_player_rankings(settings: object) -> int:
    """Run Liquipedia player rankings ingestion asynchronously."""
    from cs2_analytics.ingestion.liquipedia import LiquipediaClient
    from cs2_analytics.utils.config import Settings

    # asyncio.sleep(2.0) is inside LiquipediaClient fetch methods — do NOT add extra sleep here
    s: Settings = settings  # type: ignore[assignment]
    async with LiquipediaClient(api_key=s.liquipedia_api_key) as client:
        return await client.ingest_players(bucket=s.aws_s3_bucket, region=s.aws_region)


@dag(
    dag_id="cs2_weekly_rankings",
    schedule="@weekly",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_failure_callback=on_failure_callback,
    tags=["cs2", "ingestion"],
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=10),
        "retry_exponential_backoff": True,
    },
)
def cs2_weekly_rankings_dag() -> None:
    """Sync CS2 team and player rankings from Liquipedia into S3."""

    @task()
    def ingest_team_rankings() -> int:
        """Ingest Liquipedia team rankings for this week — skip if already in S3."""
        # Import Settings inside task body to avoid module-level import errors at DagBag load time
        from cs2_analytics.utils.config import Settings

        settings = Settings()
        this_monday = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/teams/liquipedia/{this_monday}/teams.parquet"

        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists__skipping", key=s3_key)
            return 0

        count = asyncio.run(_ingest_rankings(settings))
        log.info("team_rankings_ingestion_complete", count=count, date=this_monday)
        return count

    @task()
    def ingest_player_rankings() -> int:
        """Ingest Liquipedia player rankings for this week — skip if already in S3."""
        from cs2_analytics.utils.config import Settings

        settings = Settings()
        this_monday = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/players/liquipedia/{this_monday}/players.parquet"

        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists__skipping", key=s3_key)
            return 0

        count = asyncio.run(_ingest_player_rankings(settings))
        log.info("player_rankings_ingestion_complete", count=count, date=this_monday)
        return count

    # Both tasks are independent — run in parallel
    ingest_team_rankings()
    ingest_player_rankings()


cs2_weekly_rankings_dag()
