-- Team pressure performance metrics (CC-01..CC-04).
-- Current facts include final scores and overtime flags, but not halftime scores
-- or bracket position. We expose availability flags so downstream products do
-- not mistake proxy metrics for unavailable event-level facts.
-- Grain: one row per team with aggregated pressure-scenario statistics.
with matches as (
    select * from {{ ref('fact_matches') }}
    where score_a is not null and score_b is not null
),

team_matches as (
    -- Team A perspective
    select
        team_a_id as team_id,
        winner_id,
        score_a as own_score,
        score_b as opp_score,
        is_overtime,
        played_at,
        case when score_a >= 10 and winner_id != team_a_id then 1 else 0 end as lead_blown,
        case when winner_id = team_a_id and score_b >= 12 then 1 else 0 end as comeback_win_proxy,
        case when winner_id = team_a_id then 1 else 0 end as is_win,
        case when winner_id is not null and winner_id != team_a_id then 1 else 0 end as is_loss
    from matches

    union all

    -- Team B perspective
    select
        team_b_id as team_id,
        winner_id,
        score_b as own_score,
        score_a as opp_score,
        is_overtime,
        played_at,
        case when score_b >= 10 and winner_id != team_b_id then 1 else 0 end as lead_blown,
        case when winner_id = team_b_id and score_a >= 12 then 1 else 0 end as comeback_win_proxy,
        case when winner_id = team_b_id then 1 else 0 end as is_win,
        case when winner_id is not null and winner_id != team_b_id then 1 else 0 end as is_loss
    from matches
),

team_agg as (
    select
        team_id,
        count(*) as total_scored_matches,
        sum(is_win) as wins,
        sum(is_loss) as losses,
        sum(lead_blown) as leads_blown,
        round(sum(lead_blown)::float / nullif(count(*), 0), 4) as lead_blown_rate,
        sum(comeback_win_proxy) as comebacks,
        round(sum(comeback_win_proxy)::float / nullif(sum(is_win), 0), 4) as comeback_rate,
        sum(case when is_overtime = true then 1 else 0 end) as ot_matches,
        sum(case when is_overtime = true and is_win = 1 then 1 else 0 end) as ot_wins,
        sum(case when is_overtime = true and is_loss = 1 then 1 else 0 end) as ot_losses,
        round(
            sum(case when is_overtime = true and is_win = 1 then 1 else 0 end)::float
            / nullif(sum(case when is_overtime = true then 1 else 0 end), 0),
            4
        ) as ot_win_rate
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
    'final_score_pressure_proxy' as comeback_metric_type,
    false as halftime_data_available,
    ta.ot_matches,
    ta.ot_wins,
    ta.ot_losses,
    ta.ot_win_rate,
    false as bracket_data_available,
    null::float as elimination_win_pct,
    null::float as winners_bracket_win_pct
from team_agg ta
left join {{ ref('dim_teams') }} t on ta.team_id = t.team_id
