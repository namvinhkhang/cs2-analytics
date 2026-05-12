"""Streamlit page for team pressure profiles from HLTV round history."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

DISPLAY_COLUMNS = [
    "team",
    "world_ranking",
    "sample_quality",
    "maps_analyzed",
    "rounds_analyzed",
    "largest_lead",
    "maps_with_5plus_lead",
    "leads_blown",
    "lead_blown_rate",
    "halftime_leads_lost",
    "comebacks",
    "halftime_comeback_rate",
    "overtime_record",
    "ot_win_rate",
    "close_map_record",
    "close_map_win_rate",
]

SAMPLE_QUALITY_ORDER = ["limited", "directional", "stable"]
METRIC_OPTIONS: dict[str, str] = {
    "Lead-blown rate": "lead_blown_rate",
    "Halftime comeback rate": "halftime_comeback_rate",
    "Overtime win rate": "ot_win_rate",
    "Close-map win rate": "close_map_win_rate",
}


def _readable_value(value: Any, fallback: str = "Unknown") -> str:
    """Return a compact dashboard label for nullable mart values."""
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _team_label(row: pd.Series) -> str:
    """Prefer team names, with a technical ID fallback for old snapshots."""
    name = row.get("team_name")
    if not pd.isna(name) and str(name).strip():
        return str(name)
    team_id = row.get("team_id")
    if not pd.isna(team_id) and str(team_id).strip():
        return f"Team {team_id}"
    return "Unknown team"


def _available_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in frame.columns]


def _sorted_values(frame: pd.DataFrame, column: str) -> list[Any]:
    if column not in frame.columns:
        return []
    values = [value for value in frame[column].dropna().unique().tolist()]
    return sorted(values, key=str)


def _ordered_sample_qualities(frame: pd.DataFrame) -> list[str]:
    available = set(_sorted_values(frame, "sample_quality"))
    ordered = [quality for quality in SAMPLE_QUALITY_ORDER if quality in available]
    extras = sorted(available.difference(SAMPLE_QUALITY_ORDER))
    return ordered + extras


def _max_int(frame: pd.DataFrame, column: str) -> int:
    if column not in frame.columns or frame.empty:
        return 1
    value = pd.to_numeric(frame[column], errors="coerce").max()
    return max(int(value), 1) if pd.notna(value) else 1


def _rate_text(value: Any) -> str:
    """Format nullable rates without turning missing denominators into zeroes."""
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return "n/a" if pd.isna(numeric) else f"{float(numeric):.1%}"


def _record_text(wins: Any, losses: Any) -> str:
    if pd.isna(wins) or pd.isna(losses):
        return "n/a"
    return f"{int(wins)}-{int(losses)}"


def _close_map_record(row: pd.Series) -> str:
    wins = row.get("close_map_wins")
    total = row.get("close_maps_analyzed", row.get("close_maps"))
    if pd.isna(wins) or pd.isna(total):
        return "n/a"
    return _record_text(wins, max(int(total) - int(wins), 0))


def _prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Add readable aliases and record strings while preserving raw mart columns."""
    prepared = frame.copy()
    if {"team_name", "team_id"}.intersection(prepared.columns):
        prepared["team"] = prepared.apply(_team_label, axis=1)
    if {"ot_wins", "ot_losses"}.issubset(prepared.columns):
        prepared["overtime_record"] = prepared.apply(
            lambda row: _record_text(row.get("ot_wins"), row.get("ot_losses")),
            axis=1,
        )
    if {"close_map_wins", "close_maps_analyzed"}.intersection(prepared.columns):
        prepared["close_map_record"] = prepared.apply(_close_map_record, axis=1)
    return prepared


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the public pressure table without raw provider IDs."""
    prepared = _prepare_frame(frame)
    return prepared[_available_columns(prepared, DISPLAY_COLUMNS)]


def _filter_teams(frame: pd.DataFrame, st: Any) -> tuple[pd.DataFrame, str]:
    """Apply page controls and return filtered teams plus the selected metric label."""
    filtered = _prepare_frame(frame)
    qualities = _ordered_sample_qualities(filtered)
    default_qualities = [quality for quality in qualities if quality != "limited"] or qualities
    teams = _sorted_values(filtered, "team")

    controls = st.columns(4)
    min_maps = controls[0].slider(
        "Minimum maps",
        min_value=0,
        max_value=max(_max_int(filtered, "maps_analyzed"), 20),
        value=20,
    )
    selected_qualities = controls[1].multiselect(
        "Sample quality",
        qualities,
        default=default_qualities,
    )
    selected_teams = controls[2].multiselect("Teams", teams, default=teams)
    selected_metric = controls[3].selectbox("Metric", list(METRIC_OPTIONS))

    if "maps_analyzed" in filtered.columns:
        map_counts = pd.to_numeric(filtered["maps_analyzed"], errors="coerce").fillna(0)
        filtered = filtered[map_counts >= min_maps]
    if selected_qualities and "sample_quality" in filtered.columns:
        filtered = filtered[filtered["sample_quality"].isin(selected_qualities)]
    if selected_teams and "team" in filtered.columns:
        filtered = filtered[filtered["team"].isin(selected_teams)]

    metric_column = METRIC_OPTIONS[selected_metric]
    if metric_column in filtered.columns:
        filtered = filtered.sort_values(metric_column, ascending=False, na_position="last")
    return filtered, selected_metric


def _render_sample_warning(st: Any, frame: pd.DataFrame) -> None:
    """Warn when the snapshot is too sparse for stable team comparisons."""
    if frame.empty or "sample_quality" not in frame.columns:
        return
    limited_share = (frame["sample_quality"] == "limited").mean()
    if limited_share > 0.5:
        st.warning(
            "Most teams are still limited samples. Treat pressure rates as directional "
            "until more HLTV mapstats batches are loaded."
        )


def _metric_median(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return "n/a"
    return _rate_text(pd.to_numeric(frame[column], errors="coerce").median())


def _render_kpis(st: Any, frame: pd.DataFrame) -> None:
    with st.container(horizontal=True):
        st.metric(
            "Maps analyzed",
            f"{int(pd.to_numeric(frame.get('maps_analyzed'), errors='coerce').sum()):,}"
            if "maps_analyzed" in frame
            else "n/a",
            border=True,
        )
        st.metric(
            "Rounds analyzed",
            f"{int(pd.to_numeric(frame.get('rounds_analyzed'), errors='coerce').sum()):,}"
            if "rounds_analyzed" in frame
            else "n/a",
            border=True,
        )
        st.metric("Lead-blown rate", _metric_median(frame, "lead_blown_rate"), border=True)
        st.metric(
            "Halftime comeback",
            _metric_median(frame, "halftime_comeback_rate"),
            border=True,
        )
        st.metric("Overtime win rate", _metric_median(frame, "ot_win_rate"), border=True)
        st.metric("Close-map win rate", _metric_median(frame, "close_map_win_rate"), border=True)


def _chart_frame(frame: pd.DataFrame, metric_column: str) -> pd.DataFrame:
    if frame.empty or metric_column not in frame.columns:
        return pd.DataFrame()
    chart_frame = frame.copy()
    chart_frame[metric_column] = pd.to_numeric(chart_frame[metric_column], errors="coerce")
    return chart_frame.dropna(subset=[metric_column]).head(20)


def _render_charts(st: Any, frame: pd.DataFrame, selected_metric: str) -> None:
    import plotly.express as px

    metric_column = METRIC_OPTIONS[selected_metric]
    chart_cols = st.columns(2)
    with chart_cols[0].container(border=True, height="stretch"):
        st.subheader(selected_metric)
        bar_frame = _chart_frame(frame, metric_column)
        if bar_frame.empty:
            st.caption("Rate chart unavailable for the selected sample.")
        else:
            fig = px.bar(
                bar_frame,
                x="team",
                y=metric_column,
                color="sample_quality" if "sample_quality" in bar_frame else None,
                labels={"team": "Team", metric_column: selected_metric},
            )
            fig.update_layout(height=420, margin={"l": 8, "r": 8, "t": 24, "b": 8})
            st.plotly_chart(fig, width="stretch")

    with chart_cols[1].container(border=True, height="stretch"):
        st.subheader("Comeback vs lead pressure")
        required = {"team", "lead_blown_rate", "halftime_comeback_rate"}
        if frame.empty or not required.issubset(frame.columns):
            st.caption("Scatter plot unavailable for this snapshot.")
        else:
            scatter_frame = frame.copy()
            scatter_frame["lead_blown_rate"] = pd.to_numeric(
                scatter_frame["lead_blown_rate"],
                errors="coerce",
            )
            scatter_frame["halftime_comeback_rate"] = pd.to_numeric(
                scatter_frame["halftime_comeback_rate"],
                errors="coerce",
            )
            scatter_frame = scatter_frame.dropna(
                subset=["lead_blown_rate", "halftime_comeback_rate"]
            )
            if scatter_frame.empty:
                st.caption("Scatter plot unavailable for this snapshot.")
            else:
                fig = px.scatter(
                    scatter_frame,
                    x="lead_blown_rate",
                    y="halftime_comeback_rate",
                    hover_name="team",
                    color="sample_quality" if "sample_quality" in scatter_frame else None,
                    labels={
                        "lead_blown_rate": "Lead-blown rate",
                        "halftime_comeback_rate": "Halftime comeback rate",
                    },
                )
                fig.update_layout(height=420, margin={"l": 8, "r": 8, "t": 24, "b": 8})
                st.plotly_chart(fig, width="stretch")


def render() -> None:
    """Render the Choke/Clutch Profile Streamlit page."""
    import streamlit as st

    from dashboard.lib.snowflake import load_mart_snapshot_cached

    st.set_page_config(page_title="Choke/Clutch Profile", layout="wide")
    st.title("Choke/Clutch Profile")
    st.caption(
        "Source: hltv_unofficial. Metrics are team/map pressure signals from round history, "
        "not player clutch or bracket-elimination stats. The sample is growing toward 5k maps."
    )

    snapshot = load_mart_snapshot_cached("mart_choke_profile")
    frame = snapshot.frame
    if frame.empty:
        st.warning("No cached Choke Profile rows available.")
        return

    _render_sample_warning(st, frame)
    filtered, selected_metric = _filter_teams(frame, st)
    if filtered.empty:
        st.info("No teams found for the selected filters.")
        return

    _render_kpis(st, filtered)
    _render_charts(st, filtered, selected_metric)

    st.dataframe(
        _display_frame(filtered),
        hide_index=True,
        width="stretch",
        column_config={
            "team": st.column_config.TextColumn("Team", pinned=True),
            "lead_blown_rate": st.column_config.ProgressColumn(
                "Lead-blown rate",
                min_value=0,
                max_value=1,
                format="%.1f",
            ),
            "halftime_comeback_rate": st.column_config.ProgressColumn(
                "Halftime comeback",
                min_value=0,
                max_value=1,
                format="%.1f",
            ),
            "ot_win_rate": st.column_config.ProgressColumn(
                "OT win rate",
                min_value=0,
                max_value=1,
                format="%.1f",
            ),
            "close_map_win_rate": st.column_config.ProgressColumn(
                "Close-map win rate",
                min_value=0,
                max_value=1,
                format="%.1f",
            ),
        },
    )


if __name__ == "__main__":
    render()
