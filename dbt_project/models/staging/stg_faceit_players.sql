-- Staging model for FACEIT player stats.
-- Renames and casts columns from raw_faceit_players. Single-source, no aggregations.
-- FACEIT is the primary stats source: only API providing per-match ADR, KAST, and ELO.
-- Filters out records with null player_id to enforce referential integrity.
with source as (
    select * from {{ source('raw', 'raw_faceit_players') }}
),

renamed as (
    select
        player_id,
        'faceit' as source,
        display_name,
        team_id,
        nationality,
        kills,
        deaths,
        adr,
        kd_ratio,
        kast,
        elo,
        match_id,
        recorded_at
    from source
    where player_id is not null
)

select * from renamed
