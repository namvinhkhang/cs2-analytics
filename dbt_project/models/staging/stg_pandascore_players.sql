-- Staging model for PandaScore player stats.
-- Renames and casts columns from raw_pandascore_players. Single-source, no aggregations.
-- Filters out records with null player_id to enforce referential integrity.
with source as (
    select * from {{ source('raw', 'raw_pandascore_players') }}
),

renamed as (
    select
        player_id,
        'pandascore' as source,
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
