-- Win rates and overall record per team.
-- Grain: one row per team with aggregate win/loss/draw counts and overall win rate.
with matches as (
    select * from {{ ref('fact_matches') }}
),

teams as (
    select * from {{ ref('dim_teams') }}
),

-- Unpivot: each match generates two rows (one per participating team)
team_matches as (
    select
        team_a_id                                                         as team_id,
        played_at,
        case when winner_id = team_a_id then 1 else 0 end                 as is_win,
        case when winner_id is not null
              and winner_id != team_a_id then 1 else 0 end                as is_loss,
        case when winner_id is null then 1 else 0 end                     as is_draw
    from matches

    union all

    select
        team_b_id                                                         as team_id,
        played_at,
        case when winner_id = team_b_id then 1 else 0 end                 as is_win,
        case when winner_id is not null
              and winner_id != team_b_id then 1 else 0 end                as is_loss,
        case when winner_id is null then 1 else 0 end                     as is_draw
    from matches
),

-- Aggregate all-time record per team
aggregated as (
    select
        tm.team_id,
        count(*)                                                          as total_matches,
        sum(tm.is_win)                                                    as wins,
        sum(tm.is_loss)                                                   as losses,
        sum(tm.is_draw)                                                   as draws,
        -- Win rate over all matches (excluding draws from denominator is intentional: draws
        -- are fractional outcomes, so simpler to divide wins by total_matches)
        round(
            sum(tm.is_win)::float / nullif(count(*), 0),
            4
        )                                                                 as win_rate
    from team_matches tm
    group by tm.team_id
)

select
    a.team_id,
    t.team_name,
    t.region,
    t.world_ranking,
    a.total_matches,
    a.wins,
    a.losses,
    a.draws,
    a.win_rate
from aggregated a
left join teams t on a.team_id = t.team_id
