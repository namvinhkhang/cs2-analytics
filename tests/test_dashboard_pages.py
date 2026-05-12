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
        REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py",
    ],
)
def test_dashboard_page_exposes_render_without_running_streamlit(page_path: Path) -> None:
    """Visible dashboard pages should import cleanly and expose render()."""
    assert page_path.exists()

    module = _load_module(page_path)

    render = getattr(module, "render", None)
    assert isinstance(render, Callable)

@pytest.mark.parametrize(
    "page_path",
    [
        REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py",
        REPO_ROOT / "dashboard" / "pages" / "2_Hidden_Gem_Scout.py",
        REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py",
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


def test_upset_tracker_display_frame_renders_binary_flags_as_booleans() -> None:
    """The table should render binary labels readably without changing source data."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "1_Upset_Tracker.py")
    frame = pd.DataFrame(
        [
            {
                "match_id": "2394126",
                "team_a_name": "Spirit",
                "team_b_name": "The MongolZ",
                "is_cross_region": 1,
                "is_upset": 0,
            }
        ]
    )

    display = module._display_frame(frame)

    assert display.loc[0, "is_cross_region"] is True
    assert display.loc[0, "is_upset"] is False
    assert frame.loc[0, "is_cross_region"] == 1
    assert frame.loc[0, "is_upset"] == 0


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


def test_choke_profile_minimum_map_filter_uses_sample_quality_and_team_controls() -> None:
    """The Choke page should filter by stable sample context before ranking rates."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py")
    frame = pd.DataFrame(
        [
            {
                "team_id": "1",
                "team_name": "Stable Team",
                "maps_analyzed": 55,
                "sample_quality": "stable",
                "lead_blown_rate": 0.2,
            },
            {
                "team_id": "2",
                "team_name": "Limited Team",
                "maps_analyzed": 9,
                "sample_quality": "limited",
                "lead_blown_rate": 0.6,
            },
        ]
    )

    class FakeControl:
        def __init__(self, index: int) -> None:
            self.index = index

        def slider(self, _label: str, **kwargs: object) -> int:
            assert kwargs["value"] == 20
            return 20

        def multiselect(
            self,
            label: str,
            options: list[str],
            default: list[str],
        ) -> list[str]:
            if label == "Sample quality":
                return ["stable"]
            if label == "Teams":
                return default
            raise AssertionError(label)

        def selectbox(self, _label: str, options: list[str]) -> str:
            return options[0]

    class FakeStreamlit:
        def columns(self, count: int) -> list[FakeControl]:
            assert count == 4
            return [FakeControl(index) for index in range(count)]

    filtered, selected_metric = module._filter_teams(frame, FakeStreamlit())

    assert selected_metric == "Lead-blown rate"
    assert filtered["team_name"].tolist() == ["Stable Team"]


def test_choke_profile_display_frame_hides_raw_ids_when_team_names_exist() -> None:
    """The public Choke table should show teams, not provider keys."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py")
    frame = pd.DataFrame(
        [
            {
                "team_id": "7020",
                "team_name": "Spirit",
                "world_ranking": 2,
                "sample_quality": "stable",
                "maps_analyzed": 50,
                "largest_lead": 9,
                "leads_blown": 2,
                "lead_blown_rate": 0.2,
                "halftime_leads_lost": 1,
                "comebacks": 3,
                "ot_wins": 2,
                "ot_losses": 1,
                "close_map_wins": 6,
                "close_maps_analyzed": 10,
            }
        ]
    )

    display = module._display_frame(frame)

    assert "team_id" not in display.columns
    assert display.loc[0, "team"] == "Spirit"
    assert display.loc[0, "overtime_record"] == "2-1"
    assert display.loc[0, "close_map_record"] == "6-4"


def test_choke_profile_small_sample_warning_renders_for_limited_dataset() -> None:
    """A mostly limited snapshot should warn users before showing pressure rates."""
    module = _load_module(REPO_ROOT / "dashboard" / "pages" / "3_Choke_Clutch_Profile.py")
    frame = pd.DataFrame(
        {
            "team_name": ["A", "B", "C"],
            "sample_quality": ["limited", "limited", "directional"],
        }
    )
    warnings: list[str] = []

    class FakeStreamlit:
        def warning(self, message: str) -> None:
            warnings.append(message)

    module._render_sample_warning(FakeStreamlit(), frame)

    assert warnings
    assert "Most teams are still limited" in warnings[0]


def test_home_page_links_to_choke_profile_snapshot_and_page() -> None:
    """The dashboard home page should surface all three v1 product features."""
    text = (REPO_ROOT / "dashboard" / "Home.py").read_text(encoding="utf-8")

    assert "mart_choke_profile" in text
    assert "pages/3_Choke_Clutch_Profile.py" in text
    assert "Choke/Clutch Profile" in text
