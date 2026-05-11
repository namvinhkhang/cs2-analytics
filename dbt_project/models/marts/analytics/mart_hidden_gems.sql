-- Players flagged as outliers compared with the tier above them (HG-01..HG-04).
-- Tier boundaries: T1 = world_ranking 1-10, T2 = 11-30, T3 = 31-50, T4 = 51+.
-- A hidden gem is a tier 2/3/4 player whose aggregate stats clear 3+ 85th
-- percentile thresholds from the next stronger tier, plus a 90-day trend direction.
-- Grain: one row per qualifying hidden-gem player.
with stats as (
    select * from {{ ref('fact_player_stats') }}
),

current_players as (
    select
        player_id,
        team_id as current_team_id
    from {{ ref('dim_players') }}
),

teams as (
    select team_id, world_ranking from {{ ref('dim_teams') }}
),

player_match_stats as (
    select
        s.player_id,
        s.display_name,
        coalesce(cp.current_team_id, s.team_id) as team_id,
        cast(s.recorded_at as date) as recorded_at,
        s.adr,
        s.kd_ratio,
        s.kast,
        s.rating,
        s.kills,
        case
            when t.world_ranking between 1 and 10 then 1
            when t.world_ranking between 11 and 30 then 2
            when t.world_ranking between 31 and 50 then 3
            else 4
        end as player_tier,
        t.world_ranking
    from stats s
    left join current_players cp
        on s.player_id = cp.player_id
    left join teams t
        on coalesce(cp.current_team_id, s.team_id) = t.team_id
),

player_agg as (
    select
        player_id,
        display_name,
        team_id,
        world_ranking,
        player_tier,
        count(*) as matches_played,
        avg(adr) as avg_adr,
        avg(kd_ratio) as avg_kd_ratio,
        avg(kast) as avg_kast,
        avg(rating) as avg_rating,
        avg(kills) as avg_kills,
        max(recorded_at) as latest_recorded_at
    from player_match_stats
    group by player_id, display_name, team_id, world_ranking, player_tier
),

tier_above_thresholds as (
    select
        player_tier,
        percentile_cont(0.85) within group (order by avg_adr) as adr_threshold,
        percentile_cont(0.85) within group (order by avg_kd_ratio) as kd_threshold,
        percentile_cont(0.85) within group (order by avg_kast) as kast_threshold,
        percentile_cont(0.85) within group (order by avg_rating) as rating_threshold
    from player_agg
    group by player_tier
),

trend_windows as (
    select
        pms.*,
        max(recorded_at) over (partition by player_id) as max_recorded_at
    from player_match_stats pms
),

player_trends as (
    select
        player_id,
        avg(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then adr
                else null
            end
        ) as recent_90_day_adr,
        avg(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then adr
                else null
            end
        ) as previous_90_day_adr
    from trend_windows
    group by player_id
),

scored as (
    select
        pa.*,
        tabove.adr_threshold,
        tabove.kd_threshold,
        tabove.kast_threshold,
        tabove.rating_threshold,
        (
            case when pa.avg_adr >= tabove.adr_threshold then 1 else 0 end
          + case when pa.avg_kd_ratio >= tabove.kd_threshold then 1 else 0 end
          + case when pa.avg_kast >= tabove.kast_threshold then 1 else 0 end
          + case when pa.avg_rating >= tabove.rating_threshold then 1 else 0 end
        ) as stats_above_tier_threshold,
        round(
            (
                case when pa.avg_adr >= tabove.adr_threshold then 25 else 0 end
              + case when pa.avg_kd_ratio >= tabove.kd_threshold then 25 else 0 end
              + case when pa.avg_kast >= tabove.kast_threshold then 25 else 0 end
              + case when pa.avg_rating >= tabove.rating_threshold then 25 else 0 end
              + least(pa.matches_played, 50) / 10.0
            ),
            2
        ) as prospect_score,
        pt.recent_90_day_adr,
        pt.previous_90_day_adr
    from player_agg pa
    left join tier_above_thresholds tabove
        on tabove.player_tier = pa.player_tier - 1
    left join player_trends pt
        on pa.player_id = pt.player_id
    where pa.player_tier > 1
)

select
    player_id,
    display_name,
    team_id,
    world_ranking,
    player_tier,
    player_tier - 1 as comparison_tier,
    matches_played,
    round(avg_adr, 2) as avg_adr,
    round(avg_kd_ratio, 3) as avg_kd_ratio,
    round(avg_kast, 2) as avg_kast,
    round(avg_rating, 3) as avg_rating,
    round(avg_kills, 1) as avg_kills,
    round(adr_threshold, 2) as tier_above_adr_threshold,
    round(kd_threshold, 3) as tier_above_kd_threshold,
    round(kast_threshold, 2) as tier_above_kast_threshold,
    round(rating_threshold, 3) as tier_above_rating_threshold,
    stats_above_tier_threshold,
    prospect_score,
    round(recent_90_day_adr, 2) as recent_90_day_adr,
    round(previous_90_day_adr, 2) as previous_90_day_adr,
    case
        when previous_90_day_adr is null then 'insufficient_history'
        when recent_90_day_adr > previous_90_day_adr then 'improving'
        when recent_90_day_adr < previous_90_day_adr then 'declining'
        else 'flat'
    end as trend_direction,
    true as is_hidden_gem
from scored
where stats_above_tier_threshold >= 3
