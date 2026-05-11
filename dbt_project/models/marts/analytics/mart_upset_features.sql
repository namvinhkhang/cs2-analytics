-- Pre-computed feature set for the Upset Tracker ML model (Phase 4, WH-08).
-- An upset occurs when the lower-ranked team (higher ranking number) wins
-- and the ranking delta between the two teams is greater than 5.
-- Grain: one row per completed match with team ranking features and upset label.
with matches as (
    -- Only completed matches with a determined winner
    select * from {{ ref('fact_matches') }}
    where winner_id is not null
),

teams as (
    select team_id, world_ranking, region from {{ ref('dim_teams') }}
),

-- Enrich each match with rankings for both sides
enriched as (
    select
        m.match_sk,
        m.match_id,
        m.source,
        m.team_a_id,
        m.team_b_id,
        m.winner_id,
        m.map_name,
        m.played_at,
        m.score_a,
        m.score_b,
        m.is_overtime,
        coalesce(m.team_a_ranking, ta.world_ranking)    as team_a_ranking,
        coalesce(m.team_b_ranking, tb.world_ranking)    as team_b_ranking,
        ta.region                                       as team_a_region,
        tb.region                                       as team_b_region,
        -- Ranking delta (absolute difference between the two teams' rankings).
        -- Unranked teams are coalesced to 999 so they are always treated as heavy underdogs.
        abs(
            coalesce(m.team_a_ranking, ta.world_ranking, 999)
            - coalesce(m.team_b_ranking, tb.world_ranking, 999)
        )                                               as ranking_delta,
        -- Favored team = lower ranking number (better world standing).
        -- NULL when teams have equal rankings.
        case
            when coalesce(m.team_a_ranking, ta.world_ranking, 999)
                 < coalesce(m.team_b_ranking, tb.world_ranking, 999)
            then m.team_a_id
            when coalesce(m.team_b_ranking, tb.world_ranking, 999)
                 < coalesce(m.team_a_ranking, ta.world_ranking, 999)
            then m.team_b_id
            else null
        end                                             as favored_team_id,
        -- Round differential (positive = team_a won more rounds)
        coalesce(m.score_a, 0) - coalesce(m.score_b, 0) as score_diff,
        -- Total rounds played (map length proxy)
        coalesce(m.score_a, 0) + coalesce(m.score_b, 0) as total_rounds
    from matches m
    left join teams ta on m.team_a_id = ta.team_id
    left join teams tb on m.team_b_id = tb.team_id
)

select
    match_sk,
    match_id,
    source,
    team_a_id,
    team_b_id,
    winner_id,
    map_name,
    played_at,
    score_a,
    score_b,
    is_overtime,
    team_a_ranking,
    team_b_ranking,
    team_a_region,
    team_b_region,
    ranking_delta,
    favored_team_id,
    score_diff,
    total_rounds,
    -- Upset label: 1 if the underdog (non-favored team) won with ranking_delta > 5
    case
        when favored_team_id is not null
             and winner_id != favored_team_id
             and ranking_delta > 5
        then 1
        else 0
    end                                                  as is_upset,
    -- Cross-region flag: potential jet-lag and meta-difference signal for ML
    case when team_a_region != team_b_region then 1 else 0 end as is_cross_region
from enriched
