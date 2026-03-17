"""Shared Airflow DAG failure alert callback using Slack webhooks.

Usage in DAG definition:
    from airflow.dags.utils.slack_alerts import on_failure_callback

    @dag(
        ...
        on_failure_callback=on_failure_callback,
    )
    def my_dag() -> None:
        ...

Requires CS2_SLACK_WEBHOOK_URL environment variable (injected via env_file: .env in docker-compose).
"""
from __future__ import annotations

import os
from typing import Any

import structlog
from airflow.providers.slack.hooks.slack_webhook import SlackWebhookHook

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

    # Read webhook URL directly from env var — no Airflow Connections used per locked decision
    webhook_url: str = os.environ["CS2_SLACK_WEBHOOK_URL"]
    hook = SlackWebhookHook(webhook_url=webhook_url)
    hook.send(text=message)

    log.info("slack_failure_alert_sent", dag_id=dag_id, task_id=task_id)
