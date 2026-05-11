-- Players flagged as outliers compared with the tier above them (HG-01..HG-04).
-- Tier boundaries: T1 = world_ranking 1-10, T2 = 11-30, T3 = 31-50, T4 = 51+.
-- A hidden gem is a tier 2/3/4 player whose aggregate stats clear 3+ 85th
-- percentile thresholds from the next stronger tier, plus a 90-day trend direction.
-- Player-level clutch rate is not available in the current stat facts, so HG-02/HG-03
-- use rating, ADR, K/D, and KAST until a trustworthy source is persisted.
-- Expose the recommended 20 recent 90-day stat-row floor so the dashboard can
-- filter interactively without hiding lower-sample candidates at the mart layer.
-- Grain: one row per qualifying hidden-gem player.
with stats as (
    select * from {{ ref('fact_player_stats') }}
),

eligibility_criteria as (
    select 20 as minimum_recent_90_day_maps
),

current_players as (
    select
        player_id,
        team_id as current_team_id
    from {{ ref('dim_players') }}
),

teams as (
    select team_id, team_name, region, world_ranking from {{ ref('dim_teams') }}
),

player_match_stats as (
    select
        s.player_id,
        s.display_name,
        coalesce(cp.current_team_id, s.team_id) as team_id,
        t.team_name,
        t.region as team_region,
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
        team_name,
        team_region,
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
    group by player_id, display_name, team_id, team_name, team_region, world_ranking, player_tier
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
        sum(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then 1
                else 0
            end
        ) as recent_90_day_maps_played,
        sum(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then 1
                else 0
            end
        ) as previous_90_day_maps_played,
        avg(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then adr
                else null
            end
        ) as recent_90_day_adr,
        avg(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then kd_ratio
                else null
            end
        ) as recent_90_day_kd_ratio,
        avg(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then kast
                else null
            end
        ) as recent_90_day_kast,
        avg(
            case
                when recorded_at >= dateadd(day, -89, max_recorded_at) then rating
                else null
            end
        ) as recent_90_day_rating,
        avg(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then adr
                else null
            end
        ) as previous_90_day_adr,
        avg(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then kd_ratio
                else null
            end
        ) as previous_90_day_kd_ratio,
        avg(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then kast
                else null
            end
        ) as previous_90_day_kast,
        avg(
            case
                when recorded_at < dateadd(day, -89, max_recorded_at)
                     and recorded_at >= dateadd(day, -179, max_recorded_at)
                then rating
                else null
            end
        ) as previous_90_day_rating
    from trend_windows
    group by player_id
),

scored_base as (
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
        pt.recent_90_day_maps_played,
        pt.previous_90_day_maps_played,
        ec.minimum_recent_90_day_maps,
        pt.recent_90_day_adr,
        pt.recent_90_day_kd_ratio,
        pt.recent_90_day_kast,
        pt.recent_90_day_rating,
        pt.previous_90_day_adr,
        pt.previous_90_day_kd_ratio,
        pt.previous_90_day_kast,
        pt.previous_90_day_rating
    from player_agg pa
    left join tier_above_thresholds tabove
        on tabove.player_tier = pa.player_tier - 1
    left join player_trends pt
        on pa.player_id = pt.player_id
    cross join eligibility_criteria ec
    where pa.player_tier > 1
),

gap_components as (
    select
        *,
        case
            when recent_90_day_adr is not null and nullif(adr_threshold, 0) is not null
            then (recent_90_day_adr / adr_threshold) - 1
            else null
        end as recent_adr_gap,
        case
            when recent_90_day_kd_ratio is not null and nullif(kd_threshold, 0) is not null
            then (recent_90_day_kd_ratio / kd_threshold) - 1
            else null
        end as recent_kd_gap,
        case
            when recent_90_day_kast is not null and nullif(kast_threshold, 0) is not null
            then (recent_90_day_kast / kast_threshold) - 1
            else null
        end as recent_kast_gap,
        case
            when recent_90_day_rating is not null and nullif(rating_threshold, 0) is not null
            then (recent_90_day_rating / rating_threshold) - 1
            else null
        end as recent_rating_gap,
        case
            when previous_90_day_adr is not null and nullif(adr_threshold, 0) is not null
            then (previous_90_day_adr / adr_threshold) - 1
            else null
        end as previous_adr_gap,
        case
            when previous_90_day_kd_ratio is not null and nullif(kd_threshold, 0) is not null
            then (previous_90_day_kd_ratio / kd_threshold) - 1
            else null
        end as previous_kd_gap,
        case
            when previous_90_day_kast is not null and nullif(kast_threshold, 0) is not null
            then (previous_90_day_kast / kast_threshold) - 1
            else null
        end as previous_kast_gap,
        case
            when previous_90_day_rating is not null and nullif(rating_threshold, 0) is not null
            then (previous_90_day_rating / rating_threshold) - 1
            else null
        end as previous_rating_gap
    from scored_base
),

scored as (
    select
        *,
        (
            coalesce(recent_adr_gap, 0)
          + coalesce(recent_kd_gap, 0)
          + coalesce(recent_kast_gap, 0)
          + coalesce(recent_rating_gap, 0)
        ) / nullif(
            case when recent_adr_gap is not null then 1 else 0 end
          + case when recent_kd_gap is not null then 1 else 0 end
          + case when recent_kast_gap is not null then 1 else 0 end
          + case when recent_rating_gap is not null then 1 else 0 end,
            0
        ) as recent_90_day_gap_to_tier_above,
        (
            coalesce(previous_adr_gap, 0)
          + coalesce(previous_kd_gap, 0)
          + coalesce(previous_kast_gap, 0)
          + coalesce(previous_rating_gap, 0)
        ) / nullif(
            case when previous_adr_gap is not null then 1 else 0 end
          + case when previous_kd_gap is not null then 1 else 0 end
          + case when previous_kast_gap is not null then 1 else 0 end
          + case when previous_rating_gap is not null then 1 else 0 end,
            0
        ) as previous_90_day_gap_to_tier_above
    from gap_components
)

select
    player_id,
    display_name,
    team_id,
    team_name,
    team_region,
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
    recent_90_day_maps_played,
    previous_90_day_maps_played,
    minimum_recent_90_day_maps,
    recent_90_day_maps_played >= minimum_recent_90_day_maps as meets_recent_sample_size,
    round(recent_90_day_adr, 2) as recent_90_day_adr,
    round(recent_90_day_kd_ratio, 3) as recent_90_day_kd_ratio,
    round(recent_90_day_kast, 2) as recent_90_day_kast,
    round(recent_90_day_rating, 3) as recent_90_day_rating,
    round(previous_90_day_adr, 2) as previous_90_day_adr,
    round(previous_90_day_kd_ratio, 3) as previous_90_day_kd_ratio,
    round(previous_90_day_kast, 2) as previous_90_day_kast,
    round(previous_90_day_rating, 3) as previous_90_day_rating,
    round(recent_90_day_gap_to_tier_above, 4) as recent_90_day_gap_to_tier_above,
    round(previous_90_day_gap_to_tier_above, 4) as previous_90_day_gap_to_tier_above,
    round(
        recent_90_day_gap_to_tier_above - previous_90_day_gap_to_tier_above,
        4
    ) as gap_delta_to_tier_above,
    case
        when previous_90_day_gap_to_tier_above is null
             or recent_90_day_gap_to_tier_above is null
        then 'insufficient_history'
        when recent_90_day_gap_to_tier_above > previous_90_day_gap_to_tier_above
        then 'gap_growing'
        when recent_90_day_gap_to_tier_above < previous_90_day_gap_to_tier_above
        then 'gap_shrinking'
        else 'gap_flat'
    end as trend_direction,
    true as is_hidden_gem
from scored
where stats_above_tier_threshold >= 3
