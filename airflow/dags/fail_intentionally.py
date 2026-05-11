"""Dev DAG — intentionally fails to smoke-test the Slack webhook alert.

Use to verify CS2_SLACK_WEBHOOK_URL is correctly configured before relying
on production DAG failure alerts.

Trigger manually: airflow dags trigger fail_intentionally
Expected result: task fails, Slack message appears in configured channel.
"""
from __future__ import annotations

import pendulum
from airflow.decorators import dag, task
from utils.slack_alerts import on_failure_callback


@dag(
    dag_id="fail_intentionally",
    schedule=None,  # Manual trigger only — not scheduled
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    catchup=False,
    on_failure_callback=on_failure_callback,
    tags=["cs2", "dev"],
)
def fail_intentionally_dag() -> None:
    """DAG that always fails — used to verify Slack webhook alerting is live."""

    @task()
    def raise_error() -> None:
        """Intentionally raises ValueError to trigger on_failure_callback."""
        raise ValueError("Intentional failure — testing Slack webhook alert")

    raise_error()


fail_intentionally_dag()
