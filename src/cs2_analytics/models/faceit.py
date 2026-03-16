"""FACEIT API v4 raw Pydantic v2 models.

Source models use extra="ignore" to silently tolerate undocumented API fields
that FACEIT may add at any time without a version bump.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict


class FACEITMatch(BaseModel):
    """Raw FACEIT match model. Maps to canonical Match via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    match_id: str
    game: str
    region: str
    competition_name: str
    teams: dict[str, Any]
    results: dict[str, Any] | None = None
    finished_at: int | None = None  # UNIX epoch seconds

    def to_canonical(self) -> "Match":
        """Map FACEIT match fields to the shared canonical Match schema."""
        # Import inside method to avoid circular import if canonical ever grows
        from cs2_analytics.models.canonical import Match

        # Extract team IDs from nested faction structure with safe fallback
        faction1 = self.teams.get("faction1", {})
        faction2 = self.teams.get("faction2", {})
        team_a_id: str = faction1.get("faction_id", "unknown")
        team_b_id: str = faction2.get("faction_id", "unknown")

        # Extract winner from results if present
        winner_id: str | None = None
        if self.results is not None:
            winner_id = self.results.get("winner")

        # Convert UNIX epoch to ISO date string
        played_at: str = "unknown"
        if self.finished_at is not None:
            played_at = (
                datetime.fromtimestamp(self.finished_at, tz=timezone.utc).date().isoformat()
            )

        return Match(
            match_id=self.match_id,
            source="faceit",
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            winner_id=winner_id,
            played_at=played_at,
        )


class FACEITPlayer(BaseModel):
    """Raw FACEIT player profile model. Maps to canonical Player via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    player_id: str
    nickname: str
    country: str | None = None
    skill_level: int | None = None
    faceit_elo: int | None = None

    def to_canonical(
        self,
        *,
        match_id: str | None = None,
        kills: int | None = None,
        deaths: int | None = None,
        adr: float | None = None,
        kd_ratio: float | None = None,
        kast: float | None = None,
        recorded_at: str,
    ) -> "Player":
        """Map FACEIT player profile to the shared canonical Player schema.

        Per-match stats (kills, deaths, adr, kd_ratio, kast) are injected by the
        ingestion client when building per-match player stat records.
        """
        from cs2_analytics.models.canonical import Player

        return Player(
            player_id=self.player_id,
            source="faceit",
            display_name=self.nickname,
            nationality=self.country,
            elo=self.faceit_elo,
            kills=kills,
            deaths=deaths,
            adr=adr,
            kd_ratio=kd_ratio,
            kast=kast,
            match_id=match_id,
            recorded_at=recorded_at,
        )


# Re-export Match and Player types used as return annotations
# (only needed here to satisfy type checkers without a top-level import)
from cs2_analytics.models.canonical import Match, Player  # noqa: E402, F401
