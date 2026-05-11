"""Parquet serialization utilities for CS2 analytics ingestion pipeline.

Explicit pyarrow schemas prevent schema drift when batches contain None values
(pyarrow cannot infer nullable flags from an all-None column without a schema hint).
All three canonical entity schemas mirror the field contracts in models/canonical.py exactly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
from pydantic import BaseModel

# --- Explicit pyarrow schemas ---
# nullable=False for required model fields; nullable=True for Optional fields.
# Using pa.int64() for integer counts (not pa.int32()) — safe for large ELO/ranking values.
# Using pa.float64() for float stats — matches Python float precision.

MATCH_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("match_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("team_a_id", pa.string(), nullable=False),
        pa.field("team_b_id", pa.string(), nullable=False),
        pa.field("winner_id", pa.string(), nullable=True),
        pa.field("played_at", pa.string(), nullable=False),
        pa.field("map_name", pa.string(), nullable=True),
        # Phase 3 additions — score_a/score_b for lead-blown / comeback rate dbt marts
        pa.field("score_a", pa.int64(), nullable=True),
        pa.field("score_b", pa.int64(), nullable=True),
        pa.field("is_overtime", pa.bool_(), nullable=True),
        pa.field("team_a_ranking", pa.int64(), nullable=True),
        pa.field("team_b_ranking", pa.int64(), nullable=True),
    ]
)

PLAYER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("player_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("display_name", pa.string(), nullable=False),
        pa.field("team_id", pa.string(), nullable=True),
        pa.field("nationality", pa.string(), nullable=True),
        # Performance stats — nullable because profile records omit per-match stats
        pa.field("kills", pa.int64(), nullable=True),
        pa.field("deaths", pa.int64(), nullable=True),
        pa.field("adr", pa.float64(), nullable=True),
        pa.field("kd_ratio", pa.float64(), nullable=True),
        pa.field("kast", pa.float64(), nullable=True),
        pa.field("elo", pa.int64(), nullable=True),  # FACEIT-specific ELO rating
        pa.field("match_id", pa.string(), nullable=True),
        pa.field("recorded_at", pa.string(), nullable=False),
    ]
)

TEAM_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("team_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("region", pa.string(), nullable=True),
        pa.field("world_ranking", pa.int64(), nullable=True),
        pa.field("ingested_at", pa.string(), nullable=False),
    ]
)

CSAPI_TEAM_RANKING_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("team_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("name", pa.string(), nullable=False),
        pa.field("region", pa.string(), nullable=True),
        pa.field("world_ranking", pa.int64(), nullable=False),
        pa.field("vrs_points", pa.int64(), nullable=True),
        pa.field("rank_diff", pa.int64(), nullable=True),
        pa.field("points_diff", pa.int64(), nullable=True),
        pa.field("ranking_date", pa.string(), nullable=False),
        pa.field("ingested_at", pa.string(), nullable=False),
    ]
)

CSAPI_PLAYER_STATS_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("player_id", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("display_name", pa.string(), nullable=False),
        pa.field("team_id", pa.string(), nullable=True),
        pa.field("team_name", pa.string(), nullable=True),
        pa.field("nationality", pa.string(), nullable=True),
        pa.field("kills", pa.float64(), nullable=True),
        pa.field("deaths", pa.float64(), nullable=True),
        pa.field("adr", pa.float64(), nullable=True),
        pa.field("kd_ratio", pa.float64(), nullable=True),
        pa.field("kast", pa.float64(), nullable=True),
        pa.field("rating", pa.float64(), nullable=True),
        pa.field("swing", pa.float64(), nullable=True),
        pa.field("matches_played", pa.int64(), nullable=True),
        pa.field("elo", pa.int64(), nullable=True),
        pa.field("match_id", pa.string(), nullable=True),
        pa.field("recorded_at", pa.string(), nullable=False),
    ]
)

KAGGLE_PLAYER_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("player_id", pa.string(), nullable=False),
        pa.field("display_name", pa.string(), nullable=False),
        pa.field("team_id", pa.string(), nullable=True),
        pa.field("opponent_id", pa.string(), nullable=True),
        pa.field("country", pa.string(), nullable=True),
        pa.field("match_id", pa.string(), nullable=True),
        pa.field("event_id", pa.string(), nullable=True),
        pa.field("event_name", pa.string(), nullable=True),
        pa.field("best_of", pa.int64(), nullable=True),
        pa.field("map_1", pa.string(), nullable=True),
        pa.field("map_2", pa.string(), nullable=True),
        pa.field("map_3", pa.string(), nullable=True),
        pa.field("kills", pa.int64(), nullable=True),
        pa.field("assists", pa.int64(), nullable=True),
        pa.field("deaths", pa.int64(), nullable=True),
        pa.field("headshots", pa.int64(), nullable=True),
        pa.field("flash_assists", pa.float64(), nullable=True),
        pa.field("kast", pa.float64(), nullable=True),
        pa.field("kd_diff", pa.int64(), nullable=True),
        pa.field("adr", pa.float64(), nullable=True),
        pa.field("fk_diff", pa.int64(), nullable=True),
        pa.field("rating", pa.float64(), nullable=True),
        pa.field("recorded_at", pa.string(), nullable=True),
    ]
)

KAGGLE_MAP_VETO_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("match_id", pa.string(), nullable=False),
        pa.field("event_id", pa.string(), nullable=True),
        pa.field("played_at", pa.string(), nullable=True),
        pa.field("team_a_id", pa.string(), nullable=True),
        pa.field("team_b_id", pa.string(), nullable=True),
        pa.field("inverted_teams", pa.bool_(), nullable=True),
        pa.field("best_of", pa.int64(), nullable=True),
        pa.field("system", pa.string(), nullable=True),
        pa.field("t1_removed_1", pa.string(), nullable=True),
        pa.field("t1_removed_2", pa.string(), nullable=True),
        pa.field("t1_removed_3", pa.string(), nullable=True),
        pa.field("t2_removed_1", pa.string(), nullable=True),
        pa.field("t2_removed_2", pa.string(), nullable=True),
        pa.field("t2_removed_3", pa.string(), nullable=True),
        pa.field("t1_picked_1", pa.string(), nullable=True),
        pa.field("t2_picked_1", pa.string(), nullable=True),
        pa.field("left_over", pa.string(), nullable=True),
    ]
)

KAGGLE_ECONOMY_SCHEMA: pa.Schema = pa.schema(
    [
        pa.field("source", pa.string(), nullable=False),
        pa.field("match_id", pa.string(), nullable=False),
        pa.field("event_id", pa.string(), nullable=True),
        pa.field("played_at", pa.string(), nullable=True),
        pa.field("team_a_id", pa.string(), nullable=True),
        pa.field("team_b_id", pa.string(), nullable=True),
        pa.field("best_of", pa.int64(), nullable=True),
        pa.field("map_name", pa.string(), nullable=True),
        pa.field("team_a_start_side", pa.string(), nullable=True),
        pa.field("team_b_start_side", pa.string(), nullable=True),
        pa.field("rounds_json", pa.string(), nullable=False),
    ]
)


def models_to_records(models: Sequence[BaseModel]) -> list[dict[str, Any]]:
    """Convert a list of Pydantic models to plain dicts for pyarrow.

    Uses model_dump() which serializes Optional fields to None correctly.
    The resulting list is suitable for pa.Table.from_pylist(records, schema=...).
    """
    return [m.model_dump() for m in models]
