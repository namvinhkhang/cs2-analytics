"""Regression tests for files the Airflow runtime must be able to import."""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE_PATH = Path("airflow/Dockerfile")
COMPOSE_PATH = Path("airflow/docker-compose.yml")


def test_airflow_image_includes_bootstrap_scripts_package() -> None:
    """CS API profile DAG tasks import scripts.bootstrap_csapi at task runtime."""
    dockerfile = DOCKERFILE_PATH.read_text()

    assert "COPY --chown=airflow:0 scripts /opt/cs2-analytics/scripts" in dockerfile
    assert 'ENV PYTHONPATH="/opt/cs2-analytics:/opt/cs2-analytics/src:${PYTHONPATH}"' in dockerfile


def test_airflow_compose_mounts_bootstrap_scripts_for_dev_iteration() -> None:
    """The local Airflow stack should see script edits without rebuilding."""
    compose = COMPOSE_PATH.read_text()

    assert "PYTHONPATH: /opt/cs2-analytics:/opt/cs2-analytics/src" in compose
    assert "../scripts:/opt/cs2-analytics/scripts" in compose


def test_bootstrap_script_imports_with_container_like_pythonpath() -> None:
    """Airflow workers import DAG task dependencies from mounted repo root and src."""
    env = {
        **os.environ,
        "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT / 'src'}",
        "CS2_FACEIT_API_KEY": "test_faceit_key",
        "CS2_PANDASCORE_API_KEY": "test_pandascore_key",
        "CS2_AWS_S3_BUCKET": "test-bucket",
        "CS2_AWS_REGION": "us-east-1",
    }

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts.bootstrap_csapi import run_profile; print(run_profile.__name__)",
        ],
        cwd="/tmp",
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )

    assert result.stdout.strip() == "run_profile"
