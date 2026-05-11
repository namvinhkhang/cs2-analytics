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


def _normalize_region(value: Any) -> str:
    """Display missing or placeholder regions honestly on dashboard charts."""
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    if not text or text.casefold() == "global":
        return "Unknown"
    return text


def _daily_upset_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate match labels into a date series for the home page chart."""
    required = {"played_at", "is_upset"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame(columns=["date", "matches", "upsets"])

    chart_frame = frame.copy()
    chart_frame["date"] = pd.to_datetime(chart_frame["played_at"], errors="coerce").dt.date
    chart_frame = chart_frame.dropna(subset=["date"])
    if chart_frame.empty:
        return pd.DataFrame(columns=["date", "matches", "upsets"])

    return (
        chart_frame.assign(upsets=chart_frame["is_upset"].fillna(False).astype(bool).astype(int))
        .groupby("date", as_index=False)
        .agg(matches=("is_upset", "size"), upsets=("upsets", "sum"))
        .tail(14)
    )


def _region_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Build a compact region distribution from both match sides."""
    region_columns = [column for column in ("team_a_region", "team_b_region") if column in frame]
    if frame.empty or not region_columns:
        return pd.DataFrame(columns=["region", "team_slots"])
    regions = pd.concat([frame[column].map(_normalize_region) for column in region_columns])
    return (
        regions.value_counts()
        .rename_axis("region")
        .reset_index(name="team_slots")
        .sort_values("team_slots", ascending=False)
    )


def _top_gems_frame(frame: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    """Return a readable top-prospect preview for the home page."""
    if frame.empty or "prospect_score" not in frame.columns:
        return pd.DataFrame()
    preview = frame.copy()
    if "display_name" in preview.columns:
        preview["player"] = preview["display_name"]
    if "team_name" in preview.columns:
        preview["team"] = preview["team_name"]
    elif "team_id" in preview.columns:
        preview["team"] = preview["team_id"].map(lambda value: f"Team {value}")
    columns = [
        column
        for column in ("player", "team", "world_ranking", "prospect_score", "trend_direction")
        if column in preview.columns
    ]
    return preview.nlargest(min(limit, len(preview)), "prospect_score")[columns]


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

    st.set_page_config(
        page_title="CS2 Analytics",
        page_icon=":material/query_stats:",
        layout="wide",
    )
    st.title("CS2 Analytics")
    st.caption("CS2-era scouting and upset signals from cached warehouse marts.")

    upset_snapshot = load_mart_snapshot_cached("mart_upset_features")
    gems_snapshot = load_mart_snapshot_cached("mart_hidden_gems")
    upset_frame = upset_snapshot.frame
    gems_frame = gems_snapshot.frame

    upset_count = (
        int(upset_frame["is_upset"].fillna(False).sum()) if "is_upset" in upset_frame else 0
    )
    upset_rate = upset_count / len(upset_frame) if len(upset_frame) else 0.0

    with st.container(horizontal=True):
        st.metric("Upset matches", _format_number(upset_count), border=True)
        st.metric("Upset rate", f"{upset_rate:.1%}", border=True)
        st.metric("Hidden gems", _format_number(len(gems_frame)), border=True)
        st.metric("Latest match", _latest_timestamp(upset_frame, "played_at"), border=True)

    product_cols = st.columns(2)
    with product_cols[0].container(border=True, height="stretch"):
        st.subheader(":material/crisis_alert: Upset Tracker")
        st.metric("Mart rows", _format_number(len(upset_frame)))
        daily_upsets = _daily_upset_frame(upset_frame)
        if daily_upsets.empty:
            st.caption("No match trend available.")
        else:
            st.bar_chart(
                daily_upsets,
                x="date",
                y=["matches", "upsets"],
                x_label="Match date",
                y_label="Matches",
                width="stretch",
            )
        st.page_link(
            "pages/1_Upset_Tracker.py",
            label="Open Upset Tracker",
            icon=":material/open_in_new:",
        )

    with product_cols[1].container(border=True, height="stretch"):
        st.subheader(":material/person_search: Hidden Gem Scout")
        st.metric("Prospects", _format_number(len(gems_frame)))
        trend_column = "trend_direction"
        if trend_column in gems_frame.columns and not gems_frame.empty:
            trend_frame = (
                gems_frame[trend_column]
                .fillna("unknown")
                .value_counts()
                .rename_axis("trend")
                .reset_index(name="prospects")
            )
            st.bar_chart(
                trend_frame,
                x="trend",
                y="prospects",
                x_label="Trend",
                y_label="Prospects",
                width="stretch",
            )
        else:
            st.caption("No prospect trend available.")
        st.page_link(
            "pages/2_Hidden_Gem_Scout.py",
            label="Open Hidden Gem Scout",
            icon=":material/open_in_new:",
        )

    chart_cols = st.columns([1, 1])
    with chart_cols[0].container(border=True, height="stretch"):
        st.subheader("Match region coverage")
        region_breakdown = _region_frame(upset_frame)
        if region_breakdown.empty:
            st.caption("Region coverage unavailable.")
        else:
            st.bar_chart(
                region_breakdown,
                x="region",
                y="team_slots",
                x_label="Region",
                y_label="Team slots",
                width="stretch",
            )

    with chart_cols[1].container(border=True, height="stretch"):
        st.subheader("Top prospect preview")
        top_gems = _top_gems_frame(gems_frame)
        if top_gems.empty:
            st.caption("No prospects available.")
        else:
            st.dataframe(
                top_gems,
                hide_index=True,
                width="stretch",
                column_config={
                    "player": st.column_config.TextColumn("Player", pinned=True),
                    "team": st.column_config.TextColumn("Team"),
                    "prospect_score": st.column_config.ProgressColumn(
                        "Score",
                        min_value=0,
                        max_value=105,
                        format="%.1f",
                    ),
                },
            )

    with st.container(border=True):
        st.subheader("Cached mart snapshots")
        _render_freshness(st, [upset_snapshot, gems_snapshot])


if __name__ == "__main__":
    render()
