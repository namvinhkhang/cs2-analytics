-- All pairwise historical matchup records between teams.
-- Grain: one row per canonical team pair (team_1_id < team_2_id alphabetically),
-- so NaVi-vs-G2 and G2-vs-NaVi are combined into the same row.
with matches as (
    select * from {{ ref('fact_matches') }}
),

-- Normalise pair ordering so (A, B) and (B, A) map to the same row
ordered_pairs as (
    select
        -- Alphabetically smaller id is always team_1
        case when team_a_id < team_b_id then team_a_id else team_b_id end  as team_1_id,
        case when team_a_id < team_b_id then team_b_id else team_a_id end  as team_2_id,
        winner_id,
        played_at,
        map_name
    from matches
)

select
    team_1_id,
    team_2_id,
    count(*)                                                              as total_matches,
    sum(case when winner_id = team_1_id then 1 else 0 end)               as team_1_wins,
    sum(case when winner_id = team_2_id then 1 else 0 end)               as team_2_wins,
    sum(case when winner_id is null then 1 else 0 end)                   as draws,
    min(played_at)                                                        as first_match,
    max(played_at)                                                        as last_match
from ordered_pairs
group by team_1_id, team_2_id
