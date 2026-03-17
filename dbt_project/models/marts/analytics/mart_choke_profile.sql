-- Team pressure performance metrics (WH-10).
-- Computes lead-blown rate (CC-01), comeback rate (CC-02), overtime record (CC-03).
-- CC-04 (elimination vs winners' bracket win %) requires bracket position data not yet
-- available in canonical schema — the column is left as NULL for future population.
-- Grain: one row per team with aggregated pressure-scenario statistics.
with matches as (
    -- Only matches with score data available
    select * from {{ ref('fact_matches') }}
    where score_a is not null and score_b is not null
),

-- Unpivot: each match produces two rows (one perspective per team)
team_matches as (
    -- Team A perspective
    select
        team_a_id                                                               as team_id,
        winner_id,
        score_a                                                                 as own_score,
        score_b                                                                 as opp_score,
        is_overtime,
        played_at,
        -- CC-01: lead-blown — team reached 10+ rounds but still lost
        case when score_a >= 10 and winner_id != team_a_id then 1 else 0 end   as lead_blown,
        -- CC-02: comeback win — won a match where opponent also reached 12+ rounds
        --        (i.e. the opponent was close to winning in a tight match)
        case when winner_id = team_a_id and score_b >= 12 then 1 else 0 end    as comeback_win,
        case when winner_id = team_a_id then 1 else 0 end                      as is_win,
        case when winner_id is not null
              and winner_id != team_a_id then 1 else 0 end                     as is_loss
    from matches

    union all

    -- Team B perspective
    select
        team_b_id                                                               as team_id,
        winner_id,
        score_b                                                                 as own_score,
        score_a                                                                 as opp_score,
        is_overtime,
        played_at,
        case when score_b >= 10 and winner_id != team_b_id then 1 else 0 end   as lead_blown,
        case when winner_id = team_b_id and score_a >= 12 then 1 else 0 end    as comeback_win,
        case when winner_id = team_b_id then 1 else 0 end                      as is_win,
        case when winner_id is not null
              and winner_id != team_b_id then 1 else 0 end                     as is_loss
    from matches
),

team_agg as (
    select
        team_id,
        count(*)                                                                as total_scored_matches,
        sum(is_win)                                                             as wins,
        sum(is_loss)                                                            as losses,
        -- CC-01: lead-blown count and rate
        sum(lead_blown)                                                         as leads_blown,
        round(
            sum(lead_blown)::float / nullif(count(*), 0),
            4
        )                                                                       as lead_blown_rate,
        -- CC-02: comeback count and rate (as fraction of all wins)
        sum(comeback_win)                                                       as comebacks,
        round(
            sum(comeback_win)::float / nullif(sum(is_win), 0),
            4
        )                                                                       as comeback_rate,
        -- CC-03: overtime record
        sum(case when is_overtime = true then 1 else 0 end)                    as ot_matches,
        sum(case when is_overtime = true and is_win = 1 then 1 else 0 end)     as ot_wins,
        sum(case when is_overtime = true and is_loss = 1 then 1 else 0 end)    as ot_losses,
        round(
            sum(case when is_overtime = true and is_win = 1 then 1 else 0 end)::float
            / nullif(sum(case when is_overtime = true then 1 else 0 end), 0),
            4
        )                                                                       as ot_win_rate
    from team_matches
    group by team_id
)

select
    ta.team_id,
    t.team_name,
    t.world_ranking,
    ta.total_scored_matches,
    ta.wins,
    ta.losses,
    ta.leads_blown,
    ta.lead_blown_rate,
    ta.comebacks,
    ta.comeback_rate,
    ta.ot_matches,
    ta.ot_wins,
    ta.ot_losses,
    ta.ot_win_rate,
    -- CC-04 placeholder: bracket elimination win% requires Liquipedia tournament schema (Phase 4)
    null::float                                                                 as elimination_win_pct
from team_agg ta
left join {{ ref('dim_teams') }} t on ta.team_id = t.team_id
