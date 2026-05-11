-- Staging model for CS API VRS-style team rankings.
-- Grain: one team per ranking snapshot date.
with source as (
    select * from {{ source('raw', 'raw_csapi_team_rankings') }}
),

renamed as (
    select
        team_id,
        'csapi' as source,
        name,
        region,
        world_ranking,
        vrs_points,
        rank_diff,
        points_diff,
        ranking_date,
        ingested_at
    from source
    where team_id is not null
      and world_ranking is not null
)

select * from renamed
