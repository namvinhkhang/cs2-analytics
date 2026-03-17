"""pytest conftest for DAG tests — extends root conftest with Airflow-specific fixtures.

Sets CS2_SLACK_WEBHOOK_URL before DagBag loads any DAG file. DagBag imports DAG
modules at instantiation time, so env vars must be set before fixture runs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from airflow.models import DagBag

# Add project root to sys.path so airflow's pkgutil.extend_path can discover
# the local airflow/dags/ namespace alongside the installed airflow package.
_PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Re-extend airflow.__path__ now that project root is on sys.path
import airflow as _airflow  # noqa: E402
import pkgutil as _pkgutil  # noqa: E402
_airflow.__path__ = list(_pkgutil.extend_path(_airflow.__path__, _airflow.__name__))

# Extend root conftest dummy env with Airflow-specific vars.
# Must run before DagBag is instantiated in any test.
os.environ.setdefault("CS2_SLACK_WEBHOOK_URL", "https://hooks.slack.com/test_webhook")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    """Load all DAGs from airflow/dags/ — use for structural tests."""
    return DagBag(dag_folder="airflow/dags", include_examples=False)
