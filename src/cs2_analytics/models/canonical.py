"""Canonical Pydantic v2 models shared across all ingestion sources.

These models define the schema contract that every source client maps to.
All canonical models use extra="forbid" — any unknown field causes a ValidationError
at validation time, enforcing schema stability for downstream dbt models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Match(BaseModel):
    """Canonical match model written to Parquet by every ingestion client.

    The played_at field is an ISO-8601 date string used as the Hive partition key.
    """

    # Reject any field not declared here — downstream schema must stay stable
    model_config = ConfigDict(extra="forbid")

    match_id: str
    source: str  # "faceit" | "liquipedia" | "pandascore" | "kaggle"
    team_a_id: str
    team_b_id: str
    winner_id: str | None
    played_at: str  # ISO-8601 date string, e.g. "2024-01-15"
    map_name: str | None = None


class Player(BaseModel):
    """Canonical player model written to Parquet by FACEIT and PandaScore clients.

    All stat fields are optional because:
    - Profile records may not carry per-match stats.
    - Per-match stat records populate kills/deaths/adr/kd_ratio/kast.
    - ELO is FACEIT-specific and absent from PandaScore responses.
    """

    model_config = ConfigDict(extra="forbid")

    player_id: str
    source: str
    display_name: str
    team_id: str | None = None
    nationality: str | None = None

    # Performance stats — all optional; populated for per-match stat records
    kills: int | None = None
    deaths: int | None = None
    adr: float | None = None
    kd_ratio: float | None = None
    kast: float | None = None
    elo: int | None = None  # FACEIT ELO rating

    # Context fields
    match_id: str | None = None  # populated for per-match stat records
    recorded_at: str  # ISO-8601 date string


class Team(BaseModel):
    """Canonical team model written to Parquet by Liquipedia and PandaScore clients."""

    model_config = ConfigDict(extra="forbid")

    team_id: str
    source: str
    name: str
    region: str | None = None
    world_ranking: int | None = None
    ingested_at: str  # ISO-8601 date string
