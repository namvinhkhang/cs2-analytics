-- Staging model for Kaggle historical HLTV match data.
-- Renames and casts columns from raw_kaggle_matches. Single-source, no aggregations.
-- Filters out records with null match_id to enforce primary key integrity.
with source as (
    select * from {{ source('raw', 'raw_kaggle_matches') }}
),

renamed as (
    select
        match_id,
        'kaggle' as source,
        team_a_id,
        team_b_id,
        winner_id,
        played_at,
        map_name,
        score_a,
        score_b,
        is_overtime,
        team_a_ranking,
        team_b_ranking
    from source
    where match_id is not null
)

select * from renamed
