"""TDD tests for cs2_analytics.utils.parquet — pyarrow schema utilities.

RED phase: these tests are written before the implementation exists.
They define the exact contract the implementation must satisfy.
"""

from __future__ import annotations

from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq


def test_match_schema_has_twelve_fields() -> None:
    """MATCH_SCHEMA includes scores, overtime, and optional team ranking fields."""
    from cs2_analytics.utils.parquet import MATCH_SCHEMA

    assert len(MATCH_SCHEMA) == 12, f"Expected 12 match fields, got {len(MATCH_SCHEMA)}"


def test_match_schema_required_fields_non_nullable() -> None:
    """Non-optional Match fields must be marked nullable=False in schema."""
    from cs2_analytics.utils.parquet import MATCH_SCHEMA

    required = ["match_id", "source", "team_a_id", "team_b_id", "played_at"]
    for field_name in required:
        field = MATCH_SCHEMA.field(field_name)
        assert field.nullable is False, f"Field '{field_name}' should be non-nullable"


def test_match_schema_optional_fields_nullable() -> None:
    """Optional Match fields must be marked nullable=True in schema."""
    from cs2_analytics.utils.parquet import MATCH_SCHEMA

    optional = ["winner_id", "map_name", "team_a_ranking", "team_b_ranking"]
    for field_name in optional:
        field = MATCH_SCHEMA.field(field_name)
        assert field.nullable is True, f"Field '{field_name}' should be nullable"


def test_player_schema_has_thirteen_fields() -> None:
    """PLAYER_SCHEMA must declare exactly 13 fields to mirror the Player canonical model."""
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA

    assert len(PLAYER_SCHEMA) == 13, f"Expected 13 player fields, got {len(PLAYER_SCHEMA)}"


def test_player_schema_stat_fields_nullable() -> None:
    """All stat fields on PLAYER_SCHEMA must be nullable (per-match records may omit them)."""
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA

    nullable_fields = [
        "team_id",
        "nationality",
        "kills",
        "deaths",
        "adr",
        "kd_ratio",
        "kast",
        "elo",
        "match_id",
    ]
    for field_name in nullable_fields:
        field = PLAYER_SCHEMA.field(field_name)
        assert field.nullable is True, f"Field '{field_name}' should be nullable"


def test_player_schema_required_fields_non_nullable() -> None:
    """Identity fields on PLAYER_SCHEMA must be non-nullable."""
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA

    required = ["player_id", "source", "display_name", "recorded_at"]
    for field_name in required:
        field = PLAYER_SCHEMA.field(field_name)
        assert field.nullable is False, f"Field '{field_name}' should be non-nullable"


def test_player_schema_stat_types() -> None:
    """Stat fields must use correct pyarrow types: int64 for counts, float64 for rates."""
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA

    assert PLAYER_SCHEMA.field("kills").type == pa.int64()
    assert PLAYER_SCHEMA.field("deaths").type == pa.int64()
    assert PLAYER_SCHEMA.field("elo").type == pa.int64()
    assert PLAYER_SCHEMA.field("adr").type == pa.float64()
    assert PLAYER_SCHEMA.field("kd_ratio").type == pa.float64()
    assert PLAYER_SCHEMA.field("kast").type == pa.float64()


def test_team_schema_has_six_fields() -> None:
    """TEAM_SCHEMA must declare exactly 6 fields to mirror the Team canonical model."""
    from cs2_analytics.utils.parquet import TEAM_SCHEMA

    assert len(TEAM_SCHEMA) == 6, f"Expected 6 team fields, got {len(TEAM_SCHEMA)}"


def test_team_schema_nullable_flags() -> None:
    """region and world_ranking are optional; other Team fields are required."""
    from cs2_analytics.utils.parquet import TEAM_SCHEMA

    assert TEAM_SCHEMA.field("region").nullable is True
    assert TEAM_SCHEMA.field("world_ranking").nullable is True
    assert TEAM_SCHEMA.field("team_id").nullable is False
    assert TEAM_SCHEMA.field("source").nullable is False
    assert TEAM_SCHEMA.field("name").nullable is False
    assert TEAM_SCHEMA.field("ingested_at").nullable is False


def test_team_schema_world_ranking_type() -> None:
    """world_ranking must use int64 (not int32) for forward compatibility."""
    from cs2_analytics.utils.parquet import TEAM_SCHEMA

    assert TEAM_SCHEMA.field("world_ranking").type == pa.int64()


def test_models_to_records_converts_pydantic_to_dicts() -> None:
    """models_to_records must return a list of plain dicts via model_dump()."""
    from cs2_analytics.models.canonical import Match
    from cs2_analytics.utils.parquet import models_to_records

    match = Match(
        match_id="m1",
        source="faceit",
        team_a_id="ta",
        team_b_id="tb",
        winner_id=None,
        played_at="2024-01-15",
    )
    records = models_to_records([match])

    assert len(records) == 1
    assert isinstance(records[0], dict)
    assert records[0]["match_id"] == "m1"
    assert records[0]["winner_id"] is None


def test_models_to_records_empty_list() -> None:
    """models_to_records([]) must return an empty list without raising."""
    from cs2_analytics.utils.parquet import models_to_records

    assert models_to_records([]) == []


def test_models_to_records_none_stat_fields_roundtrip() -> None:
    """Player with all-None stats must round-trip to Parquet buffer without ArrowInvalid error.

    This is the Pitfall 4 test — explicit schema prevents schema drift on null batches.
    """
    from cs2_analytics.models.canonical import Player
    from cs2_analytics.utils.parquet import PLAYER_SCHEMA, models_to_records

    player = Player(
        player_id="p1",
        source="faceit",
        display_name="test_player",
        recorded_at="2024-01-15",
        # All optional fields left as None
    )
    records = models_to_records([player])
    table = pa.Table.from_pylist(records, schema=PLAYER_SCHEMA)

    buf = BytesIO()
    pq.write_table(table, buf, compression="snappy")
    assert buf.tell() > 0, "Parquet buffer should not be empty"


def test_match_schema_roundtrip_with_none_fields() -> None:
    """Match with None winner_id and map_name must serialize to Parquet correctly."""
    from cs2_analytics.models.canonical import Match
    from cs2_analytics.utils.parquet import MATCH_SCHEMA, models_to_records

    match = Match(
        match_id="m2",
        source="liquipedia",
        team_a_id="ta",
        team_b_id="tb",
        winner_id=None,
        played_at="2024-03-10",
        map_name=None,
    )
    records = models_to_records([match])
    table = pa.Table.from_pylist(records, schema=MATCH_SCHEMA)

    buf = BytesIO()
    pq.write_table(table, buf, compression="snappy")
    assert buf.tell() > 0
