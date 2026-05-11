-- Staging model for CS API modern CS2 series-level matches.
-- CS API team IDs and ranking fields align with stg_csapi_team_rankings, which
-- makes this the safest match source for Upset Tracker features.
with source as (
    select * from {{ source('raw', 'raw_csapi_matches') }}
),

renamed as (
    select
        match_id,
        'csapi' as source,
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
      and team_a_id is not null
      and team_b_id is not null
)

select * from renamed
