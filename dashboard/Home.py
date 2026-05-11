"""Streamlit home page for the CS2 analytics dashboard."""

# ruff: noqa: N999 - Streamlit expects the entry page to be named Home.py.

from __future__ import annotations

from typing import Any

import pandas as pd


def _format_number(value: Any) -> str:
    """Keep dashboard metrics readable when mart columns contain nullable values."""
    if pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}" if isinstance(value, int) else str(value)


def _latest_timestamp(frame: pd.DataFrame, column: str) -> str:
    if column not in frame.columns or frame.empty:
        return "n/a"
    latest = pd.to_datetime(frame[column], errors="coerce").max()
    if pd.isna(latest):
        return "n/a"
    return str(latest.date())


def _render_freshness(st: Any, snapshots: list[Any]) -> None:
    from dashboard.lib.snowflake import data_freshness

    try:
        freshness = data_freshness(snapshots)
    except Exception as exc:
        st.caption(f"Freshness unavailable: {exc}")
        return

    if isinstance(freshness, pd.DataFrame) and not freshness.empty:
        st.dataframe(freshness, hide_index=True, width="stretch")
        return
    st.caption(_format_number(freshness))


def render() -> None:
    """Render the public Streamlit dashboard home page."""
    import streamlit as st

    from dashboard.lib.snowflake import load_mart_snapshot_cached

    st.set_page_config(page_title="CS2 Analytics", layout="wide")
    st.title("CS2 Analytics")

    upset_snapshot = load_mart_snapshot_cached("mart_upset_features")
    gems_snapshot = load_mart_snapshot_cached("mart_hidden_gems")
    upset_frame = upset_snapshot.frame
    gems_frame = gems_snapshot.frame

    upset_count = (
        int(upset_frame["is_upset"].fillna(False).sum()) if "is_upset" in upset_frame else 0
    )
    upset_rate = upset_count / len(upset_frame) if len(upset_frame) else 0.0

    metric_cols = st.columns(4)
    metric_cols[0].metric("Upset matches", _format_number(upset_count))
    metric_cols[1].metric("Upset rate", f"{upset_rate:.1%}")
    metric_cols[2].metric("Hidden gems", _format_number(len(gems_frame)))
    metric_cols[3].metric("Latest match", _latest_timestamp(upset_frame, "played_at"))

    st.subheader("Products")
    product_cols = st.columns(2)
    with product_cols[0]:
        st.page_link("pages/1_Upset_Tracker.py", label="Upset Tracker")
    with product_cols[1]:
        st.page_link("pages/2_Hidden_Gem_Scout.py", label="Hidden Gem Scout")

    st.subheader("Cached mart snapshots")
    snapshot_cols = st.columns(2)
    with snapshot_cols[0]:
        st.metric("mart_upset_features rows", _format_number(len(upset_frame)))
        st.caption("Upset Tracker source")
    with snapshot_cols[1]:
        st.metric("mart_hidden_gems rows", _format_number(len(gems_frame)))
        st.caption("Hidden Gem Scout source")

    st.subheader("Data freshness")
    _render_freshness(st, [upset_snapshot, gems_snapshot])


if __name__ == "__main__":
    render()
