from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_refresh_workflow_has_required_schedule_and_steps() -> None:
    workflow = REPO_ROOT / ".github" / "workflows" / "dashboard-refresh.yml"

    text = workflow.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "17 10 * * *" in text
    assert "43 11 * * 1" in text
    assert "contents: write" in text
    assert "uv run python scripts/bootstrap_csapi.py --profile" in text
    assert "uv run dbt deps --project-dir dbt_project" in text
    assert "uv run dbt run --select" in text
    assert "uv run dbt test --select" in text
    assert "uv run python -m ml.train" in text
    assert "uv run python -m dashboard.export_snapshots" in text
    assert "dashboard/snapshots" in text
    assert "SNOWFLAKE_PRIVATE_KEY" in text
    assert "CS2_AWS_S3_BUCKET" in text
    assert "AWS_ACCESS_KEY_ID" in text


def test_dashboard_refresh_workflow_is_not_gitignored() -> None:
    workflow = ".github/workflows/dashboard-refresh.yml"

    result = subprocess.run(
        ["git", "check-ignore", workflow],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr
