"""Streamlit page for Hidden Gem Scout filters and trend views."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

DISPLAY_COLUMNS = [
    "display_name",
    "player_id",
    "team_id",
    "world_ranking",
    "player_tier",
    "comparison_tier",
    "matches_played",
    "recent_90_day_maps_played",
    "stats_above_tier_threshold",
    "prospect_score",
    "trend_direction",
    "recent_90_day_gap_to_tier_above",
    "previous_90_day_gap_to_tier_above",
    "gap_delta_to_tier_above",
]


def _available_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def _sorted_values(frame: pd.DataFrame, column: str) -> list[Any]:
    if column not in frame.columns:
        return []
    values = [value for value in frame[column].dropna().unique().tolist()]
    return sorted(values, key=str)


def _max_int(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 1
    value = pd.to_numeric(frame[column], errors="coerce").max()
    return max(int(value), 1) if pd.notna(value) else 1


def _filter_players(frame: pd.DataFrame, st: Any) -> pd.DataFrame:
    filtered = frame.copy()
    tiers = _sorted_values(filtered, "player_tier")
    teams = _sorted_values(filtered, "team_id")
    trends = _sorted_values(filtered, "trend_direction")

    top_controls = st.columns(4)
    selected_tiers = top_controls[0].multiselect("Tier", tiers, default=tiers)
    selected_teams = top_controls[1].multiselect("Team", teams, default=teams)
    selected_trends = top_controls[2].multiselect("Trend", trends, default=trends)
    min_stats = top_controls[3].slider(
        "Stats above threshold",
        min_value=0,
        max_value=_max_int(filtered, "stats_above_tier_threshold"),
        value=0,
    )

    sample_floor = st.slider(
        "Recent map sample floor",
        min_value=0,
        max_value=_max_int(filtered, "recent_90_day_maps_played"),
        value=_max_int(filtered, "minimum_recent_90_day_maps"),
    )

    if selected_tiers and "player_tier" in filtered.columns:
        filtered = filtered[filtered["player_tier"].isin(selected_tiers)]
    if selected_teams and "team_id" in filtered.columns:
        filtered = filtered[filtered["team_id"].isin(selected_teams)]
    if selected_trends and "trend_direction" in filtered.columns:
        filtered = filtered[filtered["trend_direction"].isin(selected_trends)]
    if "stats_above_tier_threshold" in filtered.columns:
        filtered = filtered[filtered["stats_above_tier_threshold"].fillna(0) >= min_stats]
    if "recent_90_day_maps_played" in filtered.columns:
        filtered = filtered[filtered["recent_90_day_maps_played"].fillna(0) >= sample_floor]

    if "prospect_score" in filtered.columns:
        filtered = filtered.sort_values("prospect_score", ascending=False)
    return filtered


def _render_gap_chart(st: Any, frame: pd.DataFrame) -> None:
    import plotly.express as px

    gap_columns = [
        "display_name",
        "recent_90_day_gap_to_tier_above",
        "previous_90_day_gap_to_tier_above",
    ]
    if frame.empty or not set(gap_columns).issubset(frame.columns):
        st.caption("Benchmark gap chart unavailable.")
        return

    chart_frame = frame.nlargest(min(len(frame), 15), "prospect_score").copy()
    melted = chart_frame.melt(
        id_vars=["display_name"],
        value_vars=["previous_90_day_gap_to_tier_above", "recent_90_day_gap_to_tier_above"],
        var_name="window",
        value_name="gap_to_tier_above",
    )
    melted["window"] = melted["window"].replace(
        {
            "previous_90_day_gap_to_tier_above": "Previous 90 days",
            "recent_90_day_gap_to_tier_above": "Recent 90 days",
        }
    )

    fig = px.bar(
        melted,
        x="display_name",
        y="gap_to_tier_above",
        color="window",
        barmode="group",
        labels={"display_name": "Player", "gap_to_tier_above": "Gap to tier-above benchmark"},
    )
    fig.update_layout(height=420, margin={"l": 8, "r": 8, "t": 24, "b": 8})
    st.plotly_chart(fig, width="stretch")


def render() -> None:
    """Render the Hidden Gem Scout Streamlit page."""
    import streamlit as st

    from dashboard.lib.snowflake import load_mart_snapshot_cached

    st.set_page_config(page_title="Hidden Gem Scout", layout="wide")
    st.title("Hidden Gem Scout")

    frame = load_mart_snapshot_cached("mart_hidden_gems").frame
    if frame.empty:
        st.warning("No cached hidden gem mart rows available.")
        return

    filtered = _filter_players(frame, st)
    if filtered.empty:
        st.info("No prospects found for the selected filters.")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Visible prospects", f"{len(filtered):,}")
    metric_cols[1].metric(
        "Median prospect score",
        f"{filtered['prospect_score'].median():.1f}" if "prospect_score" in filtered else "n/a",
    )
    metric_cols[2].metric(
        "Median recent maps",
        f"{filtered['recent_90_day_maps_played'].median():.0f}"
        if "recent_90_day_maps_played" in filtered
        else "n/a",
    )
    metric_cols[3].metric(
        "Positive trend",
        f"{int((filtered['trend_direction'] == 'gap_growing').sum()):,}"
        if "trend_direction" in filtered
        else "n/a",
    )

    _render_gap_chart(st, filtered)

    table_columns = _available_columns(filtered, DISPLAY_COLUMNS)
    st.dataframe(filtered[table_columns], hide_index=True, width="stretch")


if __name__ == "__main__":
    render()
