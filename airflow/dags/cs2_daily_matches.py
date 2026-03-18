"""Airflow DAG: cs2_daily_matches — ingest CS2 match results every 6 hours.

Ingests from FACEIT and PandaScore in parallel using Phase 1 async clients.
Applies S3 key existence idempotency: skips ingestion if today's Parquet already exists.

Schedule: every 6 hours (0 */6 * * *)
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

from utils.slack_alerts import on_failure_callback

log = structlog.get_logger()


def _s3_key_exists(bucket: str, key: str) -> bool:
    """Return True if key exists in S3 bucket, False otherwise.

    Uses head_object to check key existence without downloading the object.
    Raises ClientError for non-404 errors (e.g., permission denied).
    """
    s3 = boto3.client("s3")
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "404":
            return False
        raise


async def _ingest_faceit(settings: object) -> int:
    """Run FACEIT match ingestion asynchronously for today's date.

    Calls FACEITClient.ingest_matches with an empty match_ids list —
    in production this list would be populated by a prior step that fetches
    today's scheduled match IDs from the FACEIT tournament API.
    Returns total matches written to S3.
    """
    from datetime import date as _date

    from cs2_analytics.ingestion.faceit import FACEITClient
    from cs2_analytics.utils.config import Settings

    s: Settings = settings  # type: ignore[assignment]
    today = _date.today()
    async with FACEITClient(api_key=s.faceit_api_key) as client:
        # match_ids is empty — populated by a pre-fetch step in a future plan
        match_count, _ = await client.ingest_matches(
            match_ids=[],
            bucket=s.aws_s3_bucket,
            ingest_date=today,
            region=s.aws_region,
        )
        return match_count


async def _ingest_pandascore(settings: object) -> int:
    """Run PandaScore match ingestion asynchronously for today's date.

    Fetches recent past matches from the PandaScore /csgo/matches/past endpoint
    and writes canonical Match records to S3 in Parquet format.
    Returns count of matches written to S3.
    """
    from datetime import date as _date

    from cs2_analytics.ingestion.pandascore import PandaScoreClient
    from cs2_analytics.utils.config import Settings

    s: Settings = settings  # type: ignore[assignment]
    today = _date.today()
    async with PandaScoreClient(api_key=s.pandascore_api_key) as client:
        return await client.ingest_matches(
            bucket=s.aws_s3_bucket,
            ingest_date=today,
            region=s.aws_region,
        )


@dag(
    dag_id="cs2_daily_matches",
    schedule="0 */6 * * *",
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
def cs2_daily_matches_dag() -> None:
    """Ingest CS2 match results from FACEIT and PandaScore into S3."""

    @task()
    def ingest_faceit_matches() -> int:
        """Ingest FACEIT match stats for today — skip if Parquet already in S3."""
        # Import Settings inside task body — avoids module-level import errors
        # when env vars are absent at DagBag load time (Pitfall 3 from RESEARCH.md)
        from cs2_analytics.utils.config import Settings

        settings = Settings()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/matches/faceit/{today}/matches.parquet"

        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists__skipping", key=s3_key)
            return 0

        count = asyncio.run(_ingest_faceit(settings))
        log.info("faceit_ingestion_complete", count=count, date=today)
        return count

    @task()
    def ingest_pandascore_matches() -> int:
        """Ingest PandaScore match results for today — skip if Parquet already in S3."""
        # Import Settings inside task body — avoids module-level import errors
        # when env vars are absent at DagBag load time (Pitfall 3 from RESEARCH.md)
        from cs2_analytics.utils.config import Settings

        settings = Settings()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        s3_key = f"raw/matches/pandascore/{today}/matches.parquet"

        if _s3_key_exists(settings.aws_s3_bucket, s3_key):
            log.info("s3_key_already_exists__skipping", key=s3_key)
            return 0

        count = asyncio.run(_ingest_pandascore(settings))
        log.info("pandascore_ingestion_complete", count=count, date=today)
        return count

    # Both tasks are independent — TaskFlow runs them in parallel by default
    ingest_faceit_matches()
    ingest_pandascore_matches()


cs2_daily_matches_dag()
