"""Streamlit page for Upset Tracker watchlist signals."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd

DISPLAY_COLUMNS = [
    "upset_probability",
    "played_at",
    "match_id",
    "map_name",
    "team_a_id",
    "team_b_id",
    "team_a_ranking",
    "team_b_ranking",
    "ranking_delta",
    "team_a_region",
    "team_b_region",
    "is_cross_region",
    "is_upset",
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


def _match_labels(frame: pd.DataFrame) -> list[str]:
    if "match_id" not in frame.columns:
        return frame.index.astype(str).tolist()

    labels = pd.to_numeric(frame["match_id"], errors="coerce").astype("Int64").astype("string")
    fallback = pd.Series(frame.index.astype(str), index=frame.index, dtype="string")
    return labels.mask(labels == "<NA>").fillna(fallback).astype(str).tolist()


def _filter_matches(frame: pd.DataFrame, st: Any) -> pd.DataFrame:
    filtered = frame.copy()

    region_values = _sorted_values(filtered, "team_a_region") + _sorted_values(
        filtered,
        "team_b_region",
    )
    regions = sorted(set(region_values))
    maps = _sorted_values(filtered, "map_name")

    controls = st.columns(4)
    selected_regions = controls[0].multiselect("Regions", regions, default=regions)
    selected_maps = controls[1].multiselect("Maps", maps, default=maps)
    min_delta = controls[2].slider(
        "Ranking delta floor",
        min_value=0,
        max_value=_max_int(filtered, "ranking_delta"),
        value=0,
    )
    signal_view = controls[3].selectbox("Outcome label", ["All", "Upsets only", "Non-upsets"])

    if selected_regions and {"team_a_region", "team_b_region"}.issubset(filtered.columns):
        filtered = filtered[
            filtered["team_a_region"].isin(selected_regions)
            | filtered["team_b_region"].isin(selected_regions)
        ]
    if selected_maps and "map_name" in filtered.columns:
        filtered = filtered[filtered["map_name"].isin(selected_maps)]
    if "ranking_delta" in filtered.columns:
        filtered = filtered[filtered["ranking_delta"].fillna(0) >= min_delta]
    if signal_view != "All" and "is_upset" in filtered.columns:
        target = signal_view == "Upsets only"
        filtered = filtered[filtered["is_upset"].fillna(False).astype(bool) == target]

    if "upset_probability" in filtered.columns:
        filtered = filtered.sort_values("upset_probability", ascending=False)
    elif "played_at" in filtered.columns:
        filtered = filtered.sort_values("played_at", ascending=False)
    return filtered


def _explanation_value(explanation: Any, key: str, default: Any = None) -> Any:
    if isinstance(explanation, dict):
        return explanation.get(key, default)
    return getattr(explanation, key, default)


def _render_model_signal(st: Any, row: pd.Series) -> None:
    from dashboard.lib.ml import explain_upset_row, load_model_card, load_threshold

    threshold = float(load_threshold())
    model_card = load_model_card()
    explanation = explain_upset_row(row)
    probability = float(_explanation_value(explanation, "probability", 0.0))
    attributions = _explanation_value(explanation, "attributions", [])
    signal_label = "Watchlist signal" if probability >= threshold else "Below watchlist threshold"

    signal_cols = st.columns(3)
    signal_cols[0].metric("Model upset score", f"{probability:.1%}")
    signal_cols[1].metric("Watchlist threshold", f"{threshold:.1%}")
    signal_cols[2].metric("Signal", signal_label)
    st.caption(getattr(model_card, "title", "Upset Tracker model"))

    metrics = getattr(model_card, "metrics", {})
    if metrics:
        metric_frame = pd.DataFrame(
            [{"metric": key, "value": value} for key, value in metrics.items()]
        )
        st.dataframe(metric_frame, hide_index=True, width="stretch")

    if attributions:
        attribution_frame = pd.DataFrame(attributions)
        if "shap_value" in attribution_frame.columns:
            attribution_frame = attribution_frame.reindex(
                attribution_frame["shap_value"].abs().sort_values(ascending=False).index
            )
        st.dataframe(attribution_frame, hide_index=True, width="stretch")


def render() -> None:
    """Render the Upset Tracker Streamlit page."""
    import streamlit as st

    from dashboard.lib.ml import score_upset_frame
    from dashboard.lib.snowflake import load_mart_snapshot_cached

    st.set_page_config(page_title="Upset Tracker", layout="wide")
    st.title("Upset Tracker")

    frame = load_mart_snapshot_cached("mart_upset_features").frame
    if frame.empty:
        st.warning("No cached upset mart rows available.")
        return
    try:
        frame = score_upset_frame(frame).sort_values("upset_probability", ascending=False)
    except Exception as exc:
        st.warning(f"Model scoring unavailable: {exc}")

    filtered = _filter_matches(frame, st)
    if filtered.empty:
        st.info("No matches found for the selected filters.")
        return

    summary_cols = st.columns(4)
    upset_count = int(filtered["is_upset"].fillna(False).sum()) if "is_upset" in filtered else 0
    cross_region = (
        int(filtered["is_cross_region"].fillna(False).sum()) if "is_cross_region" in filtered else 0
    )
    summary_cols[0].metric("Visible matches", f"{len(filtered):,}")
    summary_cols[1].metric("Historical upset labels", f"{upset_count:,}")
    summary_cols[2].metric("Cross-region matches", f"{cross_region:,}")
    summary_cols[3].metric(
        "Median ranking delta",
        f"{filtered['ranking_delta'].median():.1f}" if "ranking_delta" in filtered else "n/a",
    )

    table_columns = _available_columns(filtered, DISPLAY_COLUMNS)
    st.dataframe(filtered[table_columns], hide_index=True, width="stretch")

    match_labels = _match_labels(filtered)
    selected_label = st.selectbox("Signal detail", match_labels)
    selected_position = match_labels.index(selected_label)
    selected_row = filtered.iloc[selected_position]
    _render_model_signal(st, selected_row)


if __name__ == "__main__":
    render()
