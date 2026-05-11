"""Tests for canonical (Match, Player, Team) and per-source Pydantic v2 models.

Covers:
- canonical models use extra="forbid" (reject unknown fields)
- source models use extra="ignore" (silently drop unknown fields)
- to_canonical() methods return correctly typed canonical instances
- Optional stat fields can all be None
"""

from __future__ import annotations

import pydantic_core
import pytest


class TestCanonicalMatch:
    """Canonical Match model tests."""

    def test_match_valid(self) -> None:
        """Match with all required fields succeeds."""
        from cs2_analytics.models.canonical import Match

        m = Match(
            match_id="m1",
            source="faceit",
            team_a_id="t1",
            team_b_id="t2",
            winner_id=None,
            played_at="2024-01-15",
        )
        assert m.match_id == "m1"
        assert m.source == "faceit"
        assert m.winner_id is None
        assert m.map_name is None  # optional, defaults to None

    def test_match_extra_field_raises(self) -> None:
        """Match rejects unknown fields (extra='forbid')."""
        from cs2_analytics.models.canonical import Match

        with pytest.raises(pydantic_core.ValidationError):
            Match(
                match_id="m1",
                source="faceit",
                team_a_id="t1",
                team_b_id="t2",
                winner_id=None,
                played_at="2024-01-15",
                unknown_field="should_fail",
            )

    def test_match_missing_required_field_raises(self) -> None:
        """Match raises ValidationError when required field is missing."""
        from cs2_analytics.models.canonical import Match

        with pytest.raises(pydantic_core.ValidationError):
            Match(match_id="m1")  # type: ignore[call-arg]

    def test_match_with_map_name(self) -> None:
        """Match with optional map_name succeeds."""
        from cs2_analytics.models.canonical import Match

        m = Match(
            match_id="m1",
            source="liquipedia",
            team_a_id="a",
            team_b_id="b",
            winner_id="a",
            played_at="2024-06-01",
            map_name="de_dust2",
        )
        assert m.map_name == "de_dust2"


class TestCanonicalPlayer:
    """Canonical Player model tests."""

    def test_player_all_optional_stats_none(self) -> None:
        """Player with all None optional stat fields is valid."""
        from cs2_analytics.models.canonical import Player

        p = Player(
            player_id="p1",
            source="faceit",
            display_name="s1mple",
            recorded_at="2024-01-15",
        )
        # All optional stat fields should be None
        assert p.kills is None
        assert p.deaths is None
        assert p.adr is None
        assert p.kd_ratio is None
        assert p.kast is None
        assert p.elo is None
        assert p.match_id is None
        assert p.team_id is None
        assert p.nationality is None

    def test_player_extra_field_raises(self) -> None:
        """Player rejects unknown fields (extra='forbid')."""
        from cs2_analytics.models.canonical import Player

        with pytest.raises(pydantic_core.ValidationError):
            Player(
                player_id="p1",
                source="faceit",
                display_name="s1mple",
                recorded_at="2024-01-15",
                bad_field="oops",
            )

    def test_player_with_all_stats(self) -> None:
        """Player with all stat fields populated succeeds."""
        from cs2_analytics.models.canonical import Player

        p = Player(
            player_id="p1",
            source="pandascore",
            display_name="NiKo",
            team_id="t1",
            nationality="BA",
            kills=25,
            deaths=18,
            adr=85.5,
            kd_ratio=1.39,
            kast=73.2,
            elo=3200,
            match_id="m1",
            recorded_at="2024-01-15",
        )
        assert p.kills == 25
        assert p.adr == 85.5


class TestCanonicalTeam:
    """Canonical Team model tests."""

    def test_team_world_ranking_none_is_valid(self) -> None:
        """Team with world_ranking=None is valid."""
        from cs2_analytics.models.canonical import Team

        t = Team(
            team_id="team1",
            source="liquipedia",
            name="Natus Vincere",
            ingested_at="2024-01-15",
        )
        assert t.world_ranking is None
        assert t.region is None

    def test_team_extra_field_raises(self) -> None:
        """Team rejects unknown fields (extra='forbid')."""
        from cs2_analytics.models.canonical import Team

        with pytest.raises(pydantic_core.ValidationError):
            Team(
                team_id="t1",
                source="liquipedia",
                name="NaVi",
                ingested_at="2024-01-15",
                unknown="bad",
            )


class TestFACEITModels:
    """FACEITMatch and FACEITPlayer model tests."""

    def test_faceit_match_accepts_extra_fields(self) -> None:
        """FACEITMatch silently drops unknown extra fields."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Open",
            teams={},
            extra_undocumented="ignored",
        )
        assert m.match_id == "abc"

    def test_faceit_match_to_canonical_returns_match(self) -> None:
        """FACEITMatch.to_canonical() returns a Match instance."""
        from cs2_analytics.models.canonical import Match
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Open",
            teams={
                "faction1": {"faction_id": "team-a"},
                "faction2": {"faction_id": "team-b"},
            },
            finished_at=1705276800,  # 2024-01-15T00:00:00 UTC exactly
        )
        canonical = m.to_canonical()
        assert isinstance(canonical, Match)
        assert canonical.source == "faceit"
        assert canonical.match_id == "abc"
        assert canonical.team_a_id == "team-a"
        assert canonical.team_b_id == "team-b"
        assert canonical.winner_id is None  # no results
        assert canonical.played_at == "2024-01-15"

    def test_faceit_match_to_canonical_with_results(self) -> None:
        """FACEITMatch.to_canonical() maps winner when results present."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="xyz",
            game="cs2",
            region="EU",
            competition_name="Pro League",
            teams={
                "faction1": {"faction_id": "team-a"},
                "faction2": {"faction_id": "team-b"},
            },
            results={"winner": "faction1"},
            finished_at=1705276800,  # 2024-01-15T00:00:00 UTC
        )
        canonical = m.to_canonical()
        assert canonical.winner_id == "faction1"

    def test_faceit_match_to_canonical_missing_team_keys(self) -> None:
        """FACEITMatch.to_canonical() falls back to 'unknown' for missing team keys."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Open",
            teams={},  # empty teams dict
        )
        canonical = m.to_canonical()
        assert canonical.team_a_id == "unknown"
        assert canonical.team_b_id == "unknown"

    def test_faceit_player_to_canonical_returns_player(self) -> None:
        """FACEITPlayer.to_canonical() returns a Player instance."""
        from cs2_analytics.models.canonical import Player
        from cs2_analytics.models.faceit import FACEITPlayer

        p = FACEITPlayer(
            player_id="p123",
            nickname="s1mple",
            country="UA",
            faceit_elo=3500,
        )
        canonical = p.to_canonical(recorded_at="2024-01-15")
        assert isinstance(canonical, Player)
        assert canonical.player_id == "p123"
        assert canonical.display_name == "s1mple"
        assert canonical.source == "faceit"
        assert canonical.nationality == "UA"
        assert canonical.elo == 3500


class TestLiquipediaModels:
    """Liquipedia source model tests."""

    def test_liquipedia_team_to_canonical(self) -> None:
        """LiquipediaTeam.to_canonical() returns a Team instance."""
        from cs2_analytics.models.canonical import Team
        from cs2_analytics.models.liquipedia import LiquipediaTeam

        lt = LiquipediaTeam(pagename="Natus_Vincere", name="Natus Vincere", region="CIS")
        canonical = lt.to_canonical(ingested_at="2024-01-15")
        assert isinstance(canonical, Team)
        assert canonical.team_id == "Natus_Vincere"
        assert canonical.source == "liquipedia"
        assert canonical.name == "Natus Vincere"
        assert canonical.region == "CIS"

    def test_liquipedia_player_to_canonical(self) -> None:
        """LiquipediaPlayer.to_canonical() returns a Player instance."""
        from cs2_analytics.models.canonical import Player
        from cs2_analytics.models.liquipedia import LiquipediaPlayer

        lp = LiquipediaPlayer(
            pagename="s1mple",
            id="s1mple",
            nationality="UA",
            teampagename="Natus_Vincere",
        )
        canonical = lp.to_canonical(recorded_at="2024-01-15")
        assert isinstance(canonical, Player)
        assert canonical.player_id == "s1mple"
        assert canonical.source == "liquipedia"
        assert canonical.team_id == "Natus_Vincere"

    def test_liquipedia_match_to_canonical(self) -> None:
        """LiquipediaMatch.to_canonical() returns a Match instance."""
        from cs2_analytics.models.canonical import Match
        from cs2_analytics.models.liquipedia import LiquipediaMatch

        lm = LiquipediaMatch(
            match2id="lp_match_123",
            team1="NaVi",
            team2="G2",
            winner="NaVi",
            date="2024-01-15",
            tournament="IEM_Katowice",
        )
        canonical = lm.to_canonical()
        assert isinstance(canonical, Match)
        assert canonical.match_id == "lp_match_123"
        assert canonical.source == "liquipedia"
        assert canonical.team_a_id == "NaVi"
        assert canonical.winner_id == "NaVi"

    def test_liquipedia_match_accepts_extra_fields(self) -> None:
        """LiquipediaMatch silently ignores extra API fields."""
        from cs2_analytics.models.liquipedia import LiquipediaMatch

        lm = LiquipediaMatch(match2id="x", extra_field="ignored")
        assert lm.match2id == "x"

    def test_liquipedia_tournament_model(self) -> None:
        """LiquipediaTournament can be instantiated with required fields."""
        from cs2_analytics.models.liquipedia import LiquipediaTournament

        t = LiquipediaTournament(pagename="IEM_Katowice_2024", name="IEM Katowice 2024")
        assert t.pagename == "IEM_Katowice_2024"
        assert t.tier is None  # optional

    def test_liquipedia_placement_model(self) -> None:
        """LiquipediaPlacement can be instantiated."""
        from cs2_analytics.models.liquipedia import LiquipediaPlacement

        p = LiquipediaPlacement(pagename="NaVi_IEM_Katowice", tournament="IEM_Katowice_2024")
        assert p.pagename == "NaVi_IEM_Katowice"


class TestPandaScoreModels:
    """PandaScore source model tests."""

    def test_pandascore_match_to_canonical(self) -> None:
        """PandaScoreMatch.to_canonical() returns a Match instance."""
        from cs2_analytics.models.canonical import Match
        from cs2_analytics.models.pandascore import PandaScoreMatch

        psm = PandaScoreMatch(
            id=12345,
            name="NaVi vs G2",
            status="finished",
            begin_at="2024-01-15T12:00:00Z",
            opponents=[
                {"opponent": {"id": 101, "name": "NaVi"}},
                {"opponent": {"id": 202, "name": "G2"}},
            ],
            winner={"id": 101},
        )
        canonical = psm.to_canonical()
        assert isinstance(canonical, Match)
        assert canonical.match_id == "12345"
        assert canonical.source == "pandascore"
        assert canonical.team_a_id == "101"
        assert canonical.team_b_id == "202"
        assert canonical.winner_id == "101"
        assert canonical.played_at == "2024-01-15"

    def test_pandascore_match_no_opponents(self) -> None:
        """PandaScoreMatch.to_canonical() handles empty opponents list."""
        from cs2_analytics.models.pandascore import PandaScoreMatch

        psm = PandaScoreMatch(id=1, name="test", status="not_started")
        canonical = psm.to_canonical()
        assert canonical.team_a_id == "unknown"
        assert canonical.team_b_id == "unknown"
        assert canonical.winner_id is None
        assert canonical.played_at == "unknown"

    def test_pandascore_match_accepts_extra_fields(self) -> None:
        """PandaScoreMatch silently ignores unknown API fields."""
        from cs2_analytics.models.pandascore import PandaScoreMatch

        psm = PandaScoreMatch(
            id=1,
            name="test",
            status="finished",
            new_api_field="future_addition",
        )
        assert psm.id == 1

    def test_pandascore_player_to_canonical(self) -> None:
        """PandaScorePlayer.to_canonical() returns a Player instance."""
        from cs2_analytics.models.canonical import Player
        from cs2_analytics.models.pandascore import PandaScorePlayer

        psp = PandaScorePlayer(
            id=999,
            name="NiKo",
            nationality="BA",
            current_team={"id": 5, "name": "G2"},
        )
        canonical = psp.to_canonical(kills=28, deaths=15, recorded_at="2024-01-15")
        assert isinstance(canonical, Player)
        assert canonical.player_id == "999"
        assert canonical.display_name == "NiKo"
        assert canonical.source == "pandascore"
        assert canonical.nationality == "BA"
        assert canonical.kills == 28


class TestMatchScoreFields:
    """Tests for canonical Match score_a, score_b, is_overtime fields (Phase 3 additions)."""

    def test_match_score_fields_default_none(self) -> None:
        """Match without score fields has score_a=None, score_b=None, is_overtime=None."""
        from cs2_analytics.models.canonical import Match

        m = Match(
            match_id="m1",
            source="faceit",
            team_a_id="t1",
            team_b_id="t2",
            winner_id=None,
            played_at="2024-01-15",
        )
        assert m.score_a is None
        assert m.score_b is None
        assert m.is_overtime is None

    def test_match_with_scores(self) -> None:
        """Match with score_a=16, score_b=13, is_overtime=False stores values correctly."""
        from cs2_analytics.models.canonical import Match

        m = Match(
            match_id="m1",
            source="faceit",
            team_a_id="t1",
            team_b_id="t2",
            winner_id="t1",
            played_at="2024-01-15",
            score_a=16,
            score_b=13,
            is_overtime=False,
        )
        assert m.score_a == 16
        assert m.score_b == 13
        assert m.is_overtime is False

    def test_match_with_overtime(self) -> None:
        """Match with score_a=19, score_b=17, is_overtime=True stores overtime correctly."""
        from cs2_analytics.models.canonical import Match

        m = Match(
            match_id="m1",
            source="faceit",
            team_a_id="t1",
            team_b_id="t2",
            winner_id="t1",
            played_at="2024-01-15",
            score_a=19,
            score_b=17,
            is_overtime=True,
        )
        assert m.score_a == 19
        assert m.score_b == 17
        assert m.is_overtime is True

    def test_match_schema_field_count(self) -> None:
        """MATCH_SCHEMA includes score and ranking fields for dbt marts."""
        from cs2_analytics.utils.parquet import MATCH_SCHEMA

        assert len(MATCH_SCHEMA) == 12


class TestFACEITScoreExtraction:
    """Tests for FACEITMatch.to_canonical() score field extraction."""

    def test_faceit_match_to_canonical_with_scores(self) -> None:
        """FACEITMatch with results.score dict populates score_a, score_b, is_overtime=False."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Pro League",
            teams={
                "faction1": {"faction_id": "team-a"},
                "faction2": {"faction_id": "team-b"},
            },
            results={"winner": "faction1", "score": {"faction1": 16, "faction2": 13}},
            finished_at=1705276800,
        )
        canonical = m.to_canonical()
        assert canonical.score_a == 16
        assert canonical.score_b == 13
        assert canonical.is_overtime is False

    def test_faceit_match_to_canonical_no_scores(self) -> None:
        """FACEITMatch with results but no score key has score_a=None, score_b=None."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Pro League",
            teams={"faction1": {"faction_id": "team-a"}, "faction2": {"faction_id": "team-b"}},
            results={"winner": "faction1"},
            finished_at=1705276800,
        )
        canonical = m.to_canonical()
        assert canonical.score_a is None
        assert canonical.score_b is None
        assert canonical.is_overtime is None

    def test_faceit_match_to_canonical_overtime(self) -> None:
        """FACEITMatch with scores summing > 24 sets is_overtime=True."""
        from cs2_analytics.models.faceit import FACEITMatch

        m = FACEITMatch(
            match_id="abc",
            game="cs2",
            region="EU",
            competition_name="Pro League",
            teams={"faction1": {"faction_id": "team-a"}, "faction2": {"faction_id": "team-b"}},
            results={"winner": "faction1", "score": {"faction1": 19, "faction2": 17}},
            finished_at=1705276800,
        )
        canonical = m.to_canonical()
        assert canonical.score_a == 19
        assert canonical.score_b == 17
        assert canonical.is_overtime is True


class TestPandaScoreScoreExtraction:
    """Tests for PandaScoreMatch.to_canonical() score field extraction."""

    def test_pandascore_match_to_canonical_with_scores(self) -> None:
        """PandaScoreMatch with results list populates score_a and score_b."""
        from cs2_analytics.models.pandascore import PandaScoreMatch

        psm = PandaScoreMatch(
            id=12345,
            name="NaVi vs G2",
            status="finished",
            begin_at="2024-01-15T12:00:00Z",
            opponents=[
                {"opponent": {"id": 101, "name": "NaVi"}},
                {"opponent": {"id": 202, "name": "G2"}},
            ],
            winner={"id": 101},
            results=[{"score": 16}, {"score": 13}],
        )
        canonical = psm.to_canonical()
        assert canonical.score_a == 16
        assert canonical.score_b == 13
        assert canonical.is_overtime is False

    def test_pandascore_match_to_canonical_no_results(self) -> None:
        """PandaScoreMatch without results field has score_a=None, score_b=None."""
        from cs2_analytics.models.pandascore import PandaScoreMatch

        psm = PandaScoreMatch(id=1, name="test", status="not_started")
        canonical = psm.to_canonical()
        assert canonical.score_a is None
        assert canonical.score_b is None
        assert canonical.is_overtime is None


class TestKaggleScoreExtraction:
    """Tests for KaggleBootstrapIngester.csv_to_matches() score field extraction."""

    def test_kaggle_csv_with_map_wins_columns(self) -> None:
        """CSV with _map_wins_team_1/_map_wins_team_2 maps to score_a/score_b."""
        import tempfile
        from pathlib import Path

        from cs2_analytics.ingestion.kaggle import KaggleBootstrapIngester

        csv_content = (
            "match_id,date,team_1,team_2,map,map_winner,_map_wins_team_1,"
            "_map_wins_team_2,rank_1,rank_2\n"
            "m1,2024-01-15,TeamA,TeamB,de_dust2,TeamA,16,10,4,9\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        ingester = KaggleBootstrapIngester(bucket="test-bucket")
        matches = ingester.csv_to_matches(tmp_path)
        tmp_path.unlink()

        assert len(matches) == 1
        assert matches[0].score_a == 16
        assert matches[0].score_b == 10
        assert matches[0].is_overtime is False
        assert matches[0].team_a_ranking == 4
        assert matches[0].team_b_ranking == 9
