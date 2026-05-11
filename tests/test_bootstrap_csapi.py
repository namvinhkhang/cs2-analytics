"""Unit tests for CS API bootstrap profile selection."""
from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from types import SimpleNamespace, TracebackType
from typing import Any, ClassVar

import pytest

from scripts import bootstrap_csapi

_DAGS_DIR = str(Path(__file__).parent.parent / "airflow" / "dags")
if _DAGS_DIR not in sys.path:
    sys.path.insert(0, _DAGS_DIR)


class FakeCSAPIClient:
    """Async context manager that records bootstrap ingestion calls."""

    calls: ClassVar[list[tuple[str, dict[str, Any]]]] = []

    async def __aenter__(self) -> FakeCSAPIClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def ingest_team_rankings(self, **kwargs: Any) -> int:
        self.calls.append(("team_rankings", kwargs))
        return 11

    async def ingest_matches(self, **kwargs: Any) -> int:
        self.calls.append(("matches", kwargs))
        return 22

    async def ingest_player_stats(self, **kwargs: Any) -> int:
        self.calls.append(("player_stats", kwargs))
        return 33


@pytest.fixture(autouse=True)
def clean_csapi_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Profile tests should not inherit local bootstrap tuning from the shell."""
    for key in list(os.environ):
        if key.startswith("CS2_CSAPI_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def fake_bootstrap_client(monkeypatch: pytest.MonkeyPatch) -> type[FakeCSAPIClient]:
    FakeCSAPIClient.calls = []
    monkeypatch.setattr(bootstrap_csapi, "CSAPIClient", FakeCSAPIClient)
    monkeypatch.setattr(
        bootstrap_csapi,
        "_s3_key_exists",
        lambda bucket, key, region: False,
        raising=False,
    )
    monkeypatch.setattr(
        bootstrap_csapi,
        "settings",
        SimpleNamespace(aws_s3_bucket="test-bucket", aws_region="us-east-1"),
    )
    return FakeCSAPIClient


def _call_kwargs(
    calls: list[tuple[str, dict[str, Any]]],
    call_name: str,
) -> dict[str, Any]:
    return dict(next(kwargs for name, kwargs in calls if name == call_name))


def test_daily_profile_uses_bounded_defaults_and_refreshes_profiles(
    fake_bootstrap_client: type[FakeCSAPIClient],
) -> None:
    result = asyncio.run(bootstrap_csapi.run_profile("daily"))

    assert result == (11, 22, 33)
    assert [name for name, _ in fake_bootstrap_client.calls] == [
        "team_rankings",
        "matches",
        "player_stats",
    ]

    match_kwargs = _call_kwargs(fake_bootstrap_client.calls, "matches")
    player_kwargs = _call_kwargs(fake_bootstrap_client.calls, "player_stats")

    assert match_kwargs["limit"] == 50
    assert match_kwargs["offset"] == 0
    assert match_kwargs["pages"] == 3
    assert match_kwargs["max_matches"] == 150
    assert player_kwargs["limit"] == 50
    assert player_kwargs["pages"] == 3
    assert player_kwargs["max_matches"] == 150
    assert player_kwargs["refresh_current_profiles"] is True


def test_weekly_profile_uses_deeper_window_for_hidden_gem_rollups(
    fake_bootstrap_client: type[FakeCSAPIClient],
) -> None:
    result = asyncio.run(bootstrap_csapi.run_profile("weekly"))

    assert result == (11, 22, 33)

    match_kwargs = _call_kwargs(fake_bootstrap_client.calls, "matches")
    player_kwargs = _call_kwargs(fake_bootstrap_client.calls, "player_stats")

    assert match_kwargs["limit"] == 100
    assert match_kwargs["offset"] == 0
    assert match_kwargs["pages"] == 30
    assert match_kwargs["max_matches"] == 3000
    assert match_kwargs["progress_interval"] == 25
    assert player_kwargs["limit"] == 100
    assert player_kwargs["pages"] == 30
    assert player_kwargs["max_matches"] == 3000
    assert player_kwargs["refresh_current_profiles"] is True


def test_backfill_profile_requires_explicit_opt_in(
    fake_bootstrap_client: type[FakeCSAPIClient],
) -> None:
    with pytest.raises(ValueError, match="requires explicit opt-in"):
        asyncio.run(bootstrap_csapi.run_profile("backfill"))

    assert fake_bootstrap_client.calls == []


def test_backfill_profile_uses_larger_resumable_chunks_when_allowed(
    fake_bootstrap_client: type[FakeCSAPIClient],
) -> None:
    result = asyncio.run(bootstrap_csapi.run_profile("backfill", allow_backfill=True))

    assert result == (11, 22, 33)

    match_kwargs = _call_kwargs(fake_bootstrap_client.calls, "matches")
    player_kwargs = _call_kwargs(fake_bootstrap_client.calls, "player_stats")

    assert match_kwargs["limit"] == 100
    assert match_kwargs["offset"] == 0
    assert match_kwargs["pages"] == 100
    assert match_kwargs["max_matches"] == 10_000
    assert match_kwargs["progress_interval"] == 50
    assert "offset_0_count_10000" in match_kwargs["output_filename"]
    assert player_kwargs["limit"] == 100
    assert player_kwargs["pages"] == 100
    assert player_kwargs["max_matches"] == 10_000
    assert player_kwargs["refresh_current_profiles"] is False


def test_profile_specific_environment_overrides_win_over_global_defaults(
    fake_bootstrap_client: type[FakeCSAPIClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CS2_CSAPI_MATCH_PAGES", "9")
    monkeypatch.setenv("CS2_CSAPI_DAILY_MATCH_PAGES", "2")
    monkeypatch.setenv("CS2_CSAPI_DAILY_MAX_MATCHES", "75")
    monkeypatch.setenv("CS2_CSAPI_DAILY_REQUEST_DELAY_SECONDS", "0")
    monkeypatch.setenv("CS2_CSAPI_DAILY_OUTPUT_FILENAME", "daily-test.parquet")

    asyncio.run(bootstrap_csapi.run_profile("daily"))

    match_kwargs = _call_kwargs(fake_bootstrap_client.calls, "matches")
    player_kwargs = _call_kwargs(fake_bootstrap_client.calls, "player_stats")

    assert match_kwargs["pages"] == 2
    assert match_kwargs["max_matches"] == 75
    assert match_kwargs["request_delay_seconds"] == 0
    assert match_kwargs["output_filename"] == "daily-test.parquet"
    assert player_kwargs["pages"] == 2
    assert player_kwargs["max_matches"] == 75
    assert player_kwargs["output_filename"] == "daily-test.parquet"


def test_profile_skips_existing_s3_outputs_without_overwriting(
    fake_bootstrap_client: type[FakeCSAPIClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled reruns should not overwrite already-written raw profile objects."""

    def existing_key(_bucket: str, key: str, _region: str) -> bool:
        return any(
            marker in key
            for marker in (
                "/team_rankings/",
                "/matches/",
                "/player_stats/",
            )
        )

    monkeypatch.setattr(bootstrap_csapi, "_s3_key_exists", existing_key, raising=False)

    result = asyncio.run(bootstrap_csapi.run_profile("daily"))

    assert result == (0, 0, 0)
    assert fake_bootstrap_client.calls == []


def test_profile_skips_only_existing_s3_outputs(
    fake_bootstrap_client: type[FakeCSAPIClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed partial profile can resume missing objects without rewriting existing ones."""

    def existing_key(_bucket: str, key: str, _region: str) -> bool:
        return "/team_rankings/" in key

    monkeypatch.setattr(bootstrap_csapi, "_s3_key_exists", existing_key, raising=False)

    result = asyncio.run(bootstrap_csapi.run_profile("daily"))

    assert result == (0, 22, 33)
    assert [name for name, _ in fake_bootstrap_client.calls] == [
        "matches",
        "player_stats",
    ]


def test_main_reports_invalid_env_profile_as_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CS2_CSAPI_PROFILE", "nightly")

    with pytest.raises(SystemExit, match="Unknown CS API bootstrap profile"):
        bootstrap_csapi.main([])


def test_main_does_not_mask_runtime_value_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def broken_run(_profile: str, *, allow_backfill: bool = False) -> tuple[int, int, int]:
        raise ValueError("bad upstream payload")

    monkeypatch.setattr(bootstrap_csapi, "_run", broken_run)

    with pytest.raises(ValueError, match="bad upstream payload"):
        bootstrap_csapi.main(["--profile", "daily"])


def test_daily_airflow_dag_wires_daily_csapi_profile() -> None:
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder="airflow/dags", include_examples=False)
    assert not dagbag.import_errors

    dag = dagbag.dags.get("cs2_daily_matches")
    assert dag is not None

    task = dag.get_task("ingest_csapi_daily_profile")
    task_source = inspect.getsource(task.python_callable)
    assert 'run_profile("daily")' in task_source


def test_weekly_airflow_dag_wires_weekly_csapi_profile() -> None:
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder="airflow/dags", include_examples=False)
    assert not dagbag.import_errors

    dag = dagbag.dags.get("cs2_weekly_rankings")
    assert dag is not None

    task = dag.get_task("ingest_csapi_weekly_profile")
    task_source = inspect.getsource(task.python_callable)
    assert 'run_profile("weekly")' in task_source


def test_weekly_airflow_dag_wires_valve_region_ingestion() -> None:
    from airflow.models import DagBag

    dagbag = DagBag(dag_folder="airflow/dags", include_examples=False)
    assert not dagbag.import_errors

    dag = dagbag.dags.get("cs2_weekly_rankings")
    assert dag is not None

    task = dag.get_task("ingest_valve_team_regions")
    task_source = inspect.getsource(task.python_callable)
    assert "ingest_latest_team_regions" in task_source
    assert "build_valve_team_regions_s3_key" in task_source
