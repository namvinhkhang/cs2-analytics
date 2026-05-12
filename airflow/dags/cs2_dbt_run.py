"""Airflow DAG: cs2_dbt_run — refresh Snowflake warehouse daily.

Pipeline: COPY INTO raw tables from S3 stage >> dbt run >> dbt test.
Schedule: daily at 08:00 UTC (after match ingestion completes).
Uses key-pair auth for Snowflake (password auth deprecated Nov 2025).
"""
from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast

import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from airflow.utils.context import Context
from utils.slack_alerts import on_failure_callback

# COPY INTO SQL statements — one per raw source table.
# These load new Parquet files from the S3 external stage into Snowflake raw tables.
# ON_ERROR = CONTINUE: skip bad files and continue; PURGE = FALSE: keep raw S3 data intact.
COPY_INTO_STATEMENTS = [
    """COPY INTO CS2_ANALYTICS.RAW.raw_faceit_matches
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/faceit/matches/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_pandascore_matches
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/pandascore/matches/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_csapi_matches
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/csapi/matches/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_csapi_team_rankings
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/csapi/team_rankings/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_csapi_player_stats
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/csapi/player_stats/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_valve_team_regions
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/valve/team_regions/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_hltv_round_history
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/hltv_unofficial/round_history/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_faceit_players
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/faceit/players/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_pandascore_players
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/pandascore/players/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
    """COPY INTO CS2_ANALYTICS.RAW.raw_liquipedia_teams
       FROM @CS2_ANALYTICS.RAW.cs2_raw_stage/liquipedia/teams/
       FILE_FORMAT = (TYPE = PARQUET)
       MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
       ON_ERROR = CONTINUE PURGE = FALSE""",
]

# dbt project path inside Docker container (baked in via Dockerfile COPY)
DBT_PROJECT_DIR = "/opt/cs2-analytics/dbt_project"


@dag(
    dag_id="cs2_dbt_run",
    schedule="0 8 * * *",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_failure_callback=cast(Callable[[Context], None], on_failure_callback),
    tags=["cs2", "warehouse"],
    default_args={
        "retries": 2,
        "retry_delay": pendulum.duration(minutes=5),
        "retry_exponential_backoff": True,
    },
)
def cs2_dbt_run_dag() -> None:
    """Refresh Snowflake warehouse: COPY INTO raw tables then dbt run + test."""

    @task()
    def copy_into_raw() -> int:
        """Execute COPY INTO for all raw source tables from S3 stage.

        Uses snowflake-connector-python with RSA key-pair authentication.
        Key-pair auth is required — Snowflake ended password auth for service accounts Nov 2025.
        Returns count of COPY INTO statements executed.
        """
        # Import inside task body to avoid module-level import errors when Snowflake
        # connector is absent at DagBag load time (follows Pitfall 3 pattern from RESEARCH.md)
        import snowflake.connector

        # Read connection params from env vars (set in docker-compose environment block)
        account = os.environ["SNOWFLAKE_ACCOUNT"]
        user = os.environ["SNOWFLAKE_USER"]
        private_key_path = os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"]
        database = os.environ["SNOWFLAKE_DATABASE"]

        conn = snowflake.connector.connect(
            account=account,
            user=user,
            authenticator="SNOWFLAKE_JWT",
            private_key_file=private_key_path,
            warehouse=warehouse,
            database=database,
        )

        try:
            cursor = conn.cursor()
            # Execute each COPY INTO sequentially — Snowflake deduplicates on file load_id
            for stmt in COPY_INTO_STATEMENTS:
                cursor.execute(stmt)
            return len(COPY_INTO_STATEMENTS)
        finally:
            conn.close()

    # dbt run: transform staging >> intermediate >> marts (BashOperator per RESEARCH.md Pattern 8)
    # --profiles-dir avoids Pitfall 3 (dbt defaults to ~/.dbt/ which is absent in container)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir {DBT_PROJECT_DIR}",
    )

    # dbt test: validate schema tests (not_null, unique, relationships) + singular tests
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt test --profiles-dir {DBT_PROJECT_DIR}",
    )

    # Pipeline: load raw data >> transform through dbt layers >> validate with dbt tests
    copy_into_raw() >> dbt_run >> dbt_test


cs2_dbt_run_dag()
