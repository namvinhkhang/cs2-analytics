"""CS API source models for modern CS2 rankings and player stats.

CS API exposes public, no-key endpoints backed by current CS2 pro data:
VRS-style team rankings and match-level player performance stats.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cs2_analytics.models.canonical import Team


class CSAPITeamRanking(BaseModel):
    """One team row from the CS API `/rankings/` snapshot."""

    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    rank: int
    rank_diff: int
    points: int
    points_diff: int
    ranking_date: str

    def to_canonical_team(self) -> Team:
        """Map the public VRS-style ranking row into the shared Team schema."""
        return Team(
            team_id=str(self.id),
            source="csapi",
            name=self.name,
            region=None,
            world_ranking=self.rank,
            ingested_at=self.ranking_date,
        )

    def to_ranking_record(self) -> dict[str, Any]:
        """Return a denormalized ranking record preserving points and deltas."""
        return {
            "team_id": str(self.id),
            "source": "csapi",
            "name": self.name,
            # CS API rankings do not expose geography, so keep this null instead of
            # turning every team into a misleading Global region.
            "region": None,
            "world_ranking": self.rank,
            "vrs_points": self.points,
            "rank_diff": self.rank_diff,
            "points_diff": self.points_diff,
            "ranking_date": self.ranking_date,
            "ingested_at": self.ranking_date,
        }


class CSAPIMatch(BaseModel):
    """One series-level row from the CS API `/matches/` endpoint."""

    model_config = ConfigDict(extra="ignore")

    id: int
    team1: dict[str, Any]
    team2: dict[str, Any]
    maps: list[dict[str, Any]] = []
    best_of: int | None = None
    date: str
    event: str | None = None
    winner: dict[str, Any] | None = None

    @staticmethod
    def _string_value(data: dict[str, Any], key: str) -> str | None:
        """Read a stringified value from a nested CS API object."""
        value = data.get(key)
        return str(value) if value is not None else None

    @staticmethod
    def _int_value(data: dict[str, Any], key: str) -> int | None:
        """Read an integer value from a nested CS API object."""
        value = data.get(key)
        return int(value) if value is not None else None

    def to_match_record(self) -> dict[str, Any]:
        """Return a canonical series-level match row for ranking-compatible marts."""
        winner_id = self._string_value(self.winner, "id") if self.winner is not None else None
        return {
            "match_id": str(self.id),
            "source": "csapi",
            "team_a_id": self._string_value(self.team1, "id") or "unknown",
            "team_b_id": self._string_value(self.team2, "id") or "unknown",
            "winner_id": winner_id,
            "played_at": self.date,
            "map_name": None,
            "score_a": self._int_value(self.team1, "score"),
            "score_b": self._int_value(self.team2, "score"),
            "is_overtime": None,
            "team_a_ranking": self._int_value(self.team1, "rank"),
            "team_b_ranking": self._int_value(self.team2, "rank"),
        }


class CSAPIPlayerStat(BaseModel):
    """Player stat row from CS API match stats."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    name: str
    team_id: int | None = None
    team_name: str | None = None
    k: float
    d: float
    swing: float
    adr: float
    kast: float
    rating: float
    matches_played: int = Field(alias="N")

    def to_player_stat_record(
        self,
        *,
        recorded_at: str,
        row_key: str | None = None,
    ) -> dict[str, Any]:
        """Return a warehouse-ready player stat record.

        Match-driven ingestion passes the CS API match ID as ``row_key`` so
        downstream trend marts can group player rows by real match date.
        """
        kd_ratio = self.k / self.d if self.d > 0 else None
        return {
            "player_id": str(self.id),
            "source": "csapi",
            "display_name": self.name,
            "team_id": str(self.team_id) if self.team_id is not None else None,
            "team_name": self.team_name,
            "nationality": None,
            "kills": self.k,
            "deaths": self.d,
            "adr": self.adr,
            "kd_ratio": kd_ratio,
            "kast": self.kast,
            "rating": self.rating,
            "swing": self.swing,
            "matches_played": self.matches_played,
            "elo": None,
            "match_id": row_key or f"csapi:{recorded_at}:{self.id}",
            "recorded_at": recorded_at,
        }
