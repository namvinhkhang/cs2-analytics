"""Models for unofficial HLTV map-stat round history.

These models consume JSON exported by the optional HLTV mapstats cache helper.
We store the resulting rows as best-effort source data under `hltv_unofficial`
so downstream marts can expose provenance clearly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WinnerSide = Literal["t", "ct"]

CT_OUTCOMES = {"ct_win", "bomb_defused", "stopwatch"}
T_OUTCOMES = {"t_win", "bomb_exploded"}


class HLTVTeam(BaseModel):
    """Team object from the unofficial HLTV mapstats payload."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str


class HLTVEvent(BaseModel):
    """Event object from the unofficial HLTV mapstats payload."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    name: str | None = None


class HLTVRoundOutcome(BaseModel):
    """One round-history item from the HLTV mapstats payload."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    outcome: str
    score: str | None = None
    round_number: int | None = Field(default=None, alias="round")
    winner: int | None = None
    is_overtime: bool | None = Field(default=None, alias="isOvertime")
    t_team: int | None = Field(default=None, alias="tTeam")
    ct_team: int | None = Field(default=None, alias="ctTeam")

    @property
    def winner_side(self) -> WinnerSide:
        """Map HLTV outcome icons to the winning side."""
        normalized = self.outcome.strip().casefold()
        if normalized in CT_OUTCOMES:
            return "ct"
        if normalized in T_OUTCOMES:
            return "t"
        raise ValueError(f"Unsupported HLTV round outcome: {self.outcome}")

    def winner_team_id(self, *, team1_id: int, team2_id: int) -> int:
        """Return the team ID that won this round."""
        if self.winner == 1:
            return team1_id
        if self.winner == 2:
            return team2_id
        if self.t_team is None or self.ct_team is None:
            raise ValueError("Round winner requires either winner or tTeam/ctTeam fields.")
        return self.ct_team if self.winner_side == "ct" else self.t_team


class HLTVSideAssignment(BaseModel):
    """T/CT side assignment for a half or overtime half."""

    model_config = ConfigDict(extra="ignore")

    team1: str
    team2: str

    def side_for_team(self, team_number: int) -> WinnerSide:
        """Return normalized side for team1 or team2."""
        raw_side = self.team1 if team_number == 1 else self.team2
        side = raw_side.strip().casefold()
        if side not in {"t", "ct"}:
            raise ValueError(f"Unsupported HLTV side value: {raw_side}")
        return side  # type: ignore[return-value]


class HLTVMatchMapStats(BaseModel):
    """Single-map stats payload from the unofficial HLTV mapstats helper."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    match_id: int = Field(alias="matchId")
    map_name: str = Field(alias="map")
    date_ms: int = Field(alias="date")
    team1: HLTVTeam
    team2: HLTVTeam
    event: HLTVEvent | None = None
    start_sides: HLTVSideAssignment | None = Field(default=None, alias="startSides")
    overtime_start_sides: list[HLTVSideAssignment] = Field(
        default_factory=list,
        alias="overtimeStartSides",
    )
    round_history: list[HLTVRoundOutcome] = Field(alias="roundHistory")

    def _team_name(self, team_id: int) -> str | None:
        """Resolve a source team ID to its display name."""
        if team_id == self.team1.id:
            return self.team1.name
        if team_id == self.team2.id:
            return self.team2.name
        return None

    def _team_id(self, team_number: int) -> int:
        """Return a non-null team ID for team1 or team2."""
        team = self.team1 if team_number == 1 else self.team2
        if team.id is None:
            raise ValueError(f"HLTV team{team_number} is missing an ID.")
        return team.id

    def _side_assignment(self, round_number: int) -> HLTVSideAssignment | None:
        """Resolve T/CT assignment for regulation and overtime rounds."""
        if self.start_sides is None:
            return None
        if round_number <= 12:
            return self.start_sides
        if round_number <= 24:
            return HLTVSideAssignment(
                team1=self.start_sides.team2,
                team2=self.start_sides.team1,
            )

        overtime_half_index = (round_number - 25) // 3
        if overtime_half_index < len(self.overtime_start_sides):
            return self.overtime_start_sides[overtime_half_index]
        return None

    def _round_side_context(
        self,
        round_outcome: HLTVRoundOutcome,
        round_number: int,
    ) -> tuple[int, int, WinnerSide]:
        """Return T team ID, CT team ID, and winner side for a round."""
        team1_id = self._team_id(1)
        team2_id = self._team_id(2)

        if round_outcome.t_team is not None and round_outcome.ct_team is not None:
            return round_outcome.t_team, round_outcome.ct_team, round_outcome.winner_side

        assignment = self._side_assignment(round_number)
        if assignment is None:
            raise ValueError(
                f"Round {round_number} needs startSides/overtimeStartSides to derive side context."
            )

        team1_side = assignment.side_for_team(1)
        t_team_id = team1_id if team1_side == "t" else team2_id
        ct_team_id = team1_id if team1_side == "ct" else team2_id
        winner_team_id = round_outcome.winner_team_id(team1_id=team1_id, team2_id=team2_id)
        winner_side: WinnerSide = "t" if winner_team_id == t_team_id else "ct"
        return t_team_id, ct_team_id, winner_side

    @staticmethod
    def _score_parts(score: str | None) -> tuple[int, int] | None:
        """Parse HLTV score strings like `16-19` into team1/team2 scores."""
        if not score or "-" not in score:
            return None
        left, right = score.split("-", maxsplit=1)
        return int(left), int(right)

    def _played_at(self) -> str:
        """Convert HLTV's millisecond timestamp to an ISO date string."""
        return datetime.fromtimestamp(self.date_ms / 1000, tz=UTC).date().isoformat()

    def to_round_records(self, *, ingested_at: str) -> list[dict[str, Any]]:
        """Normalize round history into one compact raw warehouse row per round."""
        team1_id = self._team_id(1)
        team2_id = self._team_id(2)
        team_scores = {team1_id: 0, team2_id: 0}
        records: list[dict[str, Any]] = []

        for index, round_outcome in enumerate(self.round_history, start=1):
            round_number = round_outcome.round_number or index
            t_team_id, ct_team_id, winner_side = self._round_side_context(
                round_outcome,
                round_number,
            )
            winner_team_id = round_outcome.winner_team_id(team1_id=team1_id, team2_id=team2_id)
            if winner_team_id not in team_scores:
                raise ValueError(
                    f"Round {index} winner team {winner_team_id} is not one of the map teams."
                )
            score_parts = self._score_parts(round_outcome.score)
            if score_parts is None:
                team_scores[winner_team_id] += 1
            else:
                team_scores[team1_id], team_scores[team2_id] = score_parts

            t_team_name = self._team_name(t_team_id)
            ct_team_name = self._team_name(ct_team_id)
            winner_team_name = self._team_name(winner_team_id)

            records.append(
                {
                    "source": "hltv_unofficial",
                    "map_stats_id": str(self.id),
                    "match_id": str(self.match_id),
                    "event_id": (
                        str(self.event.id) if self.event and self.event.id is not None else None
                    ),
                    "event_name": self.event.name if self.event else None,
                    "map_name": self.map_name,
                    "played_at": self._played_at(),
                    "round_number": round_number,
                    "t_team_id": str(t_team_id),
                    "t_team_name": t_team_name,
                    "ct_team_id": str(ct_team_id),
                    "ct_team_name": ct_team_name,
                    "winner_side": winner_side,
                    "winner_team_id": str(winner_team_id),
                    "winner_team_name": winner_team_name,
                    "team1_id": str(team1_id),
                    "team1_name": self.team1.name,
                    "team2_id": str(team2_id),
                    "team2_name": self.team2.name,
                    "score_team1_after": team_scores[team1_id],
                    "score_team2_after": team_scores[team2_id],
                    "reported_score": round_outcome.score,
                    "round_outcome": round_outcome.outcome,
                    "is_overtime": (
                        round_outcome.is_overtime
                        if round_outcome.is_overtime is not None
                        else round_number > 24
                    ),
                    "ingested_at": ingested_at,
                }
            )

        return records
