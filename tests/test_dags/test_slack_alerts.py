"""Unit tests for Slack failure alert callback.

Tests that on_failure_callback formats the Slack message correctly and
POSTs to the webhook URL with the right content.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch


def test_on_failure_callback_sends_slack_message() -> None:
    """on_failure_callback POSTs a Slack message containing dag_id, task_id, run_id."""
    from utils.slack_alerts import on_failure_callback

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

    # Patch requests.post — the callback POSTs directly to the webhook URL
    # (SlackWebhookHook in providers-slack>=8.x requires a Connection ID, not a raw URL)
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with patch.dict(os.environ, {"CS2_SLACK_WEBHOOK_URL": "https://hooks.slack.com/test_webhook"}):
        with patch("utils.slack_alerts.requests.post", return_value=mock_response) as mock_post:
            on_failure_callback(context)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    # Verify URL is the webhook URL from env
    assert mock_post.call_args.args[0] == "https://hooks.slack.com/test_webhook"
    # Verify message body contains the key diagnostic fields
    sent_text: str = call_kwargs["json"]["text"]
    assert "cs2_daily_matches" in sent_text
    assert "ingest_faceit_matches" in sent_text
    assert "manual__2024-01-01T00:00:00+00:00" in sent_text
