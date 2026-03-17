-- Fact: match results with foreign keys to all dimension tables.
-- Grain: one row per match per source (match_id + source is unique).
with matches as (
    select * from {{ ref('int_matches_unioned') }}
),

teams as (
    select team_id from {{ ref('dim_teams') }}
),

maps as (
    select map_name, map_sk from {{ ref('dim_maps') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['m.match_id', 'm.source']) }} as match_sk,
    m.match_id,
    m.source,
    m.team_a_id,
    m.team_b_id,
    m.winner_id,
    mp.map_sk,
    m.map_name,
    m.played_at,
    m.score_a,
    m.score_b,
    m.is_overtime
from matches m
left join maps mp on m.map_name = mp.map_name
