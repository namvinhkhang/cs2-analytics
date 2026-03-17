"""Shared Airflow DAG failure alert callback using Slack webhooks.

Usage in DAG definition:
    from utils.slack_alerts import on_failure_callback

    @dag(
        ...
        on_failure_callback=on_failure_callback,
    )
    def my_dag() -> None:
        ...

Requires CS2_SLACK_WEBHOOK_URL environment variable (injected via env_file: .env in docker-compose).

Note: SlackWebhookHook in apache-airflow-providers-slack>=8.x requires an Airflow Connection ID
and no longer accepts a raw webhook_url. Since this project avoids Airflow Connections (locked
decision), we POST directly to the webhook URL using requests instead.
"""
from __future__ import annotations

import os
from typing import Any

import requests
import structlog

log = structlog.get_logger()


def on_failure_callback(context: dict[str, Any]) -> None:
    """Send a Slack alert when any task in the DAG fails.

    Called automatically by Airflow when on_failure_callback is set at DAG level.
    Reads CS2_SLACK_WEBHOOK_URL from environment — raises KeyError if missing
    (intentional: alerting is broken without it, fail loudly).

    Args:
        context: Airflow task context dict provided by the Airflow runtime.
    """
    # Extract fields from Airflow task instance context
    ti = context["ti"]
    dag_id: str = ti.dag_id
    task_id: str = ti.task_id
    run_id: str = context["run_id"]
    log_url: str = ti.log_url
    exception: str = str(context.get("exception", "No exception captured"))

    # Format Slack message with all diagnostic fields
    message = (
        f":red_circle: *DAG Failure*\n"
        f"`DAG`   {dag_id}\n"
        f"`Task`  {task_id}\n"
        f"`Run`   {run_id}\n"
        f"`Error` {exception}\n"
        f"<{log_url}|View Logs>"
    )

    # Read webhook URL directly from env var — no Airflow Connections used per locked decision.
    # POST directly via requests: SlackWebhookHook in providers-slack>=8.x only accepts a
    # slack_webhook_conn_id (Airflow Connection), not a raw URL.
    webhook_url: str = os.environ["CS2_SLACK_WEBHOOK_URL"]
    response = requests.post(
        webhook_url,
        json={"text": message},
        timeout=10,
    )
    response.raise_for_status()

    log.info("slack_failure_alert_sent", dag_id=dag_id, task_id=task_id)
