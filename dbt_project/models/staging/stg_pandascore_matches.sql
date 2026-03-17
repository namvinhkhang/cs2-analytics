-- Staging model for PandaScore match data.
-- Renames and casts columns from raw_pandascore_matches. Single-source, no aggregations.
-- Filters out records with null match_id to enforce primary key integrity.
with source as (
    select * from {{ source('raw', 'raw_pandascore_matches') }}
),

renamed as (
    select
        match_id,
        'pandascore' as source,
        team_a_id,
        team_b_id,
        winner_id,
        played_at,
        map_name,
        score_a,
        score_b,
        is_overtime
    from source
    where match_id is not null
)

select * from renamed
