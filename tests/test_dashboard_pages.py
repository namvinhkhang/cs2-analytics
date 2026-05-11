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
