"""Liquipedia API v3 raw Pydantic v2 models.

Source models use extra="ignore" to silently tolerate undocumented API fields.
Liquipedia's REST API v3 returns structured JSON for 10 CS2 data types.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LiquipediaTeam(BaseModel):
    """Raw Liquipedia team record. Maps to canonical Team via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    pagename: str  # unique Liquipedia page identifier, used as team_id
    name: str
    region: str | None = None

    def to_canonical(self, *, ingested_at: str) -> Team:
        """Map Liquipedia team fields to the shared canonical Team schema."""
        from cs2_analytics.models.canonical import Team

        return Team(
            team_id=self.pagename,
            source="liquipedia",
            name=self.name,
            region=self.region,
            ingested_at=ingested_at,
        )


class LiquipediaPlayer(BaseModel):
    """Raw Liquipedia player record. Maps to canonical Player via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    pagename: str  # unique Liquipedia page identifier, used as player_id
    id: str  # in-game name / display handle
    name: str | None = None  # real name (may be absent)
    nationality: str | None = None
    teampagename: str | None = None  # current team pagename, used as team_id

    def to_canonical(self, *, recorded_at: str) -> Player:
        """Map Liquipedia player fields to the shared canonical Player schema."""
        from cs2_analytics.models.canonical import Player

        return Player(
            player_id=self.pagename,
            source="liquipedia",
            display_name=self.id,  # use the in-game handle as display name
            team_id=self.teampagename,
            nationality=self.nationality,
            recorded_at=recorded_at,
        )


class LiquipediaMatch(BaseModel):
    """Raw Liquipedia match record. Maps to canonical Match via to_canonical()."""

    model_config = ConfigDict(extra="ignore")

    match2id: str  # Liquipedia's unique match identifier
    team1: str | None = None
    team2: str | None = None
    winner: str | None = None  # pagename of the winning team (or None if no result)
    date: str | None = None  # ISO-8601 date string from Liquipedia
    tournament: str | None = None  # tournament pagename for context

    def to_canonical(self) -> Match:
        """Map Liquipedia match fields to the shared canonical Match schema."""
        from cs2_analytics.models.canonical import Match

        return Match(
            match_id=self.match2id,
            source="liquipedia",
            team_a_id=self.team1 or "unknown",
            team_b_id=self.team2 or "unknown",
            winner_id=self.winner,
            played_at=self.date or "unknown",
        )


class LiquipediaTournament(BaseModel):
    """Raw Liquipedia tournament record — no canonical mapping needed.

    Tournament metadata is stored as reference data, not converted to canonical.
    """

    model_config = ConfigDict(extra="ignore")

    pagename: str
    name: str
    startdate: str | None = None
    enddate: str | None = None
    prizepool: str | None = None
    tier: str | None = None  # "S", "A", "B", etc.


class LiquipediaPlacement(BaseModel):
    """Raw Liquipedia team placement record for a specific tournament."""

    model_config = ConfigDict(extra="ignore")

    pagename: str
    tournament: str | None = None  # tournament pagename
    place: str | None = None  # final placement, e.g. "1", "2", "3-4"
    team: str | None = None  # team pagename


# Re-export canonical types used in return annotations for type checker satisfaction
from cs2_analytics.models.canonical import Match, Player, Team  # noqa: E402, F401
