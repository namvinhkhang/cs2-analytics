"""Airflow DAG: cs2_tournament_sync — sync active CS2 tournament match data daily.

Ingests tournament match data from Liquipedia into S3 as Parquet.
Applies S3 key existence idempotency: skips if today's Parquet already exists.

Note: Raw tournament/placement objects are count-only in Phase 1 (no canonical S3 schema yet).
This DAG ingests tournament-context matches via LiquipediaClient.ingest_matches().

Schedule: daily (@daily — midnight UTC)
Retry: 3 attempts with 5-minute exponential backoff
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

from airflow.dags.utils.slack_alerts import on_failure_callback

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


async def _ingest_tournament_matches(settings: object) -> int:
    """Run Liquipedia tournament match ingestion asynchronously.

    Calls LiquipediaClient.ingest_matches() — note that ingest_tournaments()
    and ingest_placements() are count-only in Phase 1 (no canonical schema yet).
    """
    from cs2_analytics.ingestion.liquipedia import LiquipediaClient
    from cs2_analytics.utils.config import Settings

    # asyncio.sleep(2.0) is inside LiquipediaClient fetch methods — do NOT add extra sleep here
    s: Settings = settings  # type: ignore[assignment]
    async with LiquipediaClient(api_key=s.liquipedia_api_key) as client:
        return await client.ingest_matches(bucket=s.aws_s3_bucket, region=s.aws_region)


@dag(
    dag_id="cs2_tournament_sync",
    schedule="@daily",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_failure_callback=on_failure_callback,
    tags=["cs2", "ingestion"],
    default_args={
        "retries": 3,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def cs2_tournament_sync_dag() -> None:
    """Sync active CS2 tournament match data from Liquipedia into S3."""

    @task()
    def ingest_tournament_matches() -> int:
        """Ingest Liquipedia tournament matches for today — skip if already in S3."""
        # Import Settings inside task body to avoid module-level import errors at DagBag load time
        from cs2_analytics.utils.config import Settings

        settings = Settings()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/matches/liquipedia/{today}/matches.parquet"

        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists__skipping", key=s3_key)
            return 0

        count = asyncio.run(_ingest_tournament_matches(settings))
        log.info("tournament_matches_ingestion_complete", count=count, date=today)
        return count

    ingest_tournament_matches()


cs2_tournament_sync_dag()
