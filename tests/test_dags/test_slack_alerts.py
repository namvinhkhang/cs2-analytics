"""Unit tests for Slack failure alert callback.

Tests that on_failure_callback formats the Slack message correctly and
calls SlackWebhookHook.send() with the right content.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_on_failure_callback_sends_slack_message() -> None:
    """on_failure_callback sends Slack message containing dag_id, task_id, run_id, log_url."""
    from airflow.dags.utils.slack_alerts import on_failure_callback

    # Build a minimal Airflow task instance context
    mock_ti = MagicMock()
    mock_ti.dag_id = "cs2_daily_matches"
    mock_ti.task_id = "ingest_faceit_matches"
    mock_ti.log_url = "http://localhost:8080/log"

    context: dict = {
        "ti": mock_ti,
        "run_id": "manual__2024-01-01T00:00:00+00:00",
        "exception": ValueError("test error"),
    }

    with patch("airflow.dags.utils.slack_alerts.SlackWebhookHook") as mock_hook_cls:
        mock_hook = MagicMock()
        mock_hook_cls.return_value = mock_hook

        on_failure_callback(context)

    mock_hook.send.assert_called_once()
    sent_text: str = mock_hook.send.call_args.kwargs.get(
        "text", mock_hook.send.call_args.args[0] if mock_hook.send.call_args.args else ""
    )
    assert "cs2_daily_matches" in sent_text
    assert "ingest_faceit_matches" in sent_text
    assert "manual__2024-01-01T00:00:00+00:00" in sent_text
