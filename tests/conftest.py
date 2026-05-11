"""pytest conftest — shared fixtures and env setup for all tests.

The cs2_analytics.utils.config module instantiates Settings() at import time.
This conftest ensures the required CS2_* env vars are set before any test
module is imported, preventing ValidationError from crashing the test session.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Set dummy env vars before any test module imports cs2_analytics.utils.config.
# These values are intentionally fake — no real API calls are made in unit tests.
# ---------------------------------------------------------------------------
_DUMMY_ENV: dict[str, str] = {
    "CS2_FACEIT_API_KEY": "test_faceit_key",
    "CS2_PANDASCORE_API_KEY": "test_pandascore_key",
    "CS2_LIQUIPEDIA_API_KEY": "test_liquipedia_key",
    "CS2_AWS_S3_BUCKET": "test-bucket",
    "CS2_AWS_REGION": "us-east-1",
}

for _key, _val in _DUMMY_ENV.items():
    os.environ.setdefault(_key, _val)


@pytest.fixture(autouse=False)
def dummy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture that patches all CS2_* env vars with dummy values for isolated tests."""
    for key, val in _DUMMY_ENV.items():
        monkeypatch.setenv(key, val)
