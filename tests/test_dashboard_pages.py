"""Smoke tests for Streamlit dashboard page modules."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path) -> ModuleType:
    """Import a page file by path without relying on Streamlit's page runner."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "page_path",
    [
        REPO_ROOT / "dashboard" / "Home.py",
        REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py",
        REPO_ROOT / "dashboard" / "pages" / "2_Hidden_Gem_Scout.py",
    ],
)
def test_dashboard_page_exposes_render_without_running_streamlit(page_path: Path) -> None:
    """Visible dashboard pages should import cleanly and expose render()."""
    assert page_path.exists()

    module = _load_module(page_path)

    render = getattr(module, "render", None)
    assert isinstance(render, Callable)


def test_choke_clutch_page_is_not_present() -> None:
    """Workstream 3 excludes Choke/Clutch until its page is implemented."""
    page_path = REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py"

    assert not page_path.exists()


@pytest.mark.parametrize(
    "page_path",
    [
        REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py",
        REPO_ROOT / "dashboard" / "pages" / "2_Hidden_Gem_Scout.py",
    ],
)
def test_numeric_filter_slider_maximum_is_always_above_minimum(page_path: Path) -> None:
    """Empty or missing columns should not create invalid Streamlit slider bounds."""
    module = _load_module(page_path)

    assert module._max_int(pd.DataFrame(), "missing") == 1


def test_upset_tracker_match_labels_fall_back_to_row_index() -> None:
    """Null match IDs should not crash the Streamlit signal selector."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py")
    frame = pd.DataFrame({"match_id": [2387419, None]}, index=[10, 11])

    assert module._match_labels(frame) == ["2387419", "11"]


def test_upset_tracker_display_frame_uses_team_names_instead_of_raw_ids() -> None:
    """The match table should show readable teams once the mart exports names."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py")
    frame = pd.DataFrame(
        [
            {
                "upset_probability": 0.72,
                "played_at": "2026-05-10",
                "match_id": "2394126",
                "team_a_id": "7020",
                "team_a_name": "Spirit",
                "team_b_id": "6248",
                "team_b_name": "The MongolZ",
                "team_a_region": None,
                "team_b_region": "Asia",
                "ranking_delta": 3,
            }
        ]
    )

    display = module._display_frame(frame)

    assert "team_a_id" not in display.columns
    assert "team_b_id" not in display.columns
    assert display.loc[0, "team_a"] == "Spirit"
    assert display.loc[0, "team_b"] == "The MongolZ"
    assert display.loc[0, "team_a_region"] == "Unknown"


def test_upset_tracker_display_frame_hides_series_level_map_name() -> None:
    """Series-grain Upset Tracker rows should not show an always-null map field."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py")
    frame = pd.DataFrame(
        [
            {
                "upset_probability": 0.72,
                "played_at": "2026-05-10",
                "match_id": "2394126",
                "team_a_name": "Spirit",
                "team_b_name": "The MongolZ",
                "map_name": None,
                "ranking_delta": 3,
            }
        ]
    )

    display = module._display_frame(frame)

    assert "map_name" not in display.columns


def test_upset_tracker_filters_do_not_render_map_selector() -> None:
    """The page should not expose map filters while Upset Tracker is series-grain."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py")
    frame = pd.DataFrame(
        [
            {
                "match_id": "2394126",
                "team_a_region": "Europe",
                "team_b_region": "Asia",
                "map_name": None,
                "ranking_delta": 3,
                "is_upset": 0,
            }
        ]
    )

    class FakeControl:
        def multiselect(self, label: str, options: list[str], default: list[str]) -> list[str]:
            assert label != "Maps"
            return default

        def slider(self, *_args: object, **kwargs: object) -> int:
            return int(kwargs["value"])

        def selectbox(self, _label: str, options: list[str]) -> str:
            return options[0]

    class FakeStreamlit:
        def columns(self, count: int) -> list[FakeControl]:
            assert count == 3
            return [FakeControl() for _ in range(count)]

    filtered = module._filter_matches(frame, FakeStreamlit())

    assert len(filtered) == 1


def test_hidden_gem_display_frame_hides_player_and_team_ids_when_names_exist() -> None:
    """Player/team IDs are technical keys and should not crowd the public table."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "2_Hidden_Gem_Scout.py")
    frame = pd.DataFrame(
        [
            {
                "player_id": "22473",
                "display_name": "qlocuu",
                "team_id": "13314",
                "team_name": "ECLOT",
                "world_ranking": 88,
                "prospect_score": 77.7,
            }
        ]
    )

    display = module._display_frame(frame)

    assert "player_id" not in display.columns
    assert "team_id" not in display.columns
    assert display.loc[0, "player"] == "qlocuu"
    assert display.loc[0, "team"] == "ECLOT"
