"""pytest conftest for DAG tests — extends root conftest with Airflow-specific fixtures.

Sets CS2_SLACK_WEBHOOK_URL before DagBag loads any DAG file. DagBag imports DAG
modules at instantiation time, so env vars must be set before fixture runs.
"""
from __future__ import annotations

import os

import pytest
from airflow.models import DagBag

# Extend root conftest dummy env with Airflow-specific vars.
# Must run before DagBag is instantiated in any test.
os.environ.setdefault("CS2_SLACK_WEBHOOK_URL", "https://hooks.slack.com/test_webhook")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    """Load all DAGs from airflow/dags/ — use for structural tests."""
    return DagBag(dag_folder="airflow/dags", include_examples=False)
