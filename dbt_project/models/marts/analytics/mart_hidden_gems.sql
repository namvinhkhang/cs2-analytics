-- Players flagged as outliers relative to their tier cohort (WH-09).
-- Tier boundaries: T1 = world_ranking 1–10, T2 = 11–30, T3 = 31+.
-- A "hidden gem" is a player in tier 2 or 3 whose stats rank in the top 15th
-- percentile (>= 0.85 percent_rank) of their own tier on 3 or more key metrics.
-- Grain: one row per player (only tier 2/3 players with 3+ elite stats).
with stats as (
    select * from {{ ref('fact_player_stats') }}
),

teams as (
    select team_id, world_ranking from {{ ref('dim_teams') }}
),

-- Aggregate per-player stats across all their matches
player_agg as (
    select
        s.player_id,
        s.display_name,
        s.team_id,
        count(*)          as matches_played,
        avg(s.adr)        as avg_adr,
        avg(s.kd_ratio)   as avg_kd_ratio,
        avg(s.kast)       as avg_kast,
        avg(s.kills)      as avg_kills
    from stats s
    group by s.player_id, s.display_name, s.team_id
),

-- Assign tier based on team's current world ranking
tiered as (
    select
        pa.*,
        t.world_ranking,
        case
            when t.world_ranking between 1 and 10 then 1
            when t.world_ranking between 11 and 30 then 2
            else 3
        end                as player_tier
    from player_agg pa
    left join teams t on pa.team_id = t.team_id
),

-- Compute within-tier percentile ranks and flag stats in the top 15th percentile
tier_percentiles as (
    select
        *,
        percent_rank() over (partition by player_tier order by avg_adr asc)       as adr_pct,
        percent_rank() over (partition by player_tier order by avg_kd_ratio asc)  as kd_pct,
        percent_rank() over (partition by player_tier order by avg_kast asc)      as kast_pct,
        percent_rank() over (partition by player_tier order by avg_kills asc)     as kills_pct,
        -- Count how many of the four key stats fall in the top 15th percentile of the tier
        (
            case when percent_rank() over (partition by player_tier order by avg_adr asc)       >= 0.85 then 1 else 0 end
          + case when percent_rank() over (partition by player_tier order by avg_kd_ratio asc)  >= 0.85 then 1 else 0 end
          + case when percent_rank() over (partition by player_tier order by avg_kast asc)      >= 0.85 then 1 else 0 end
          + case when percent_rank() over (partition by player_tier order by avg_kills asc)     >= 0.85 then 1 else 0 end
        )                                                                         as stats_in_top_15_pct
    from tiered
)

select
    player_id,
    display_name,
    team_id,
    world_ranking,
    player_tier,
    matches_played,
    round(avg_adr, 2)       as avg_adr,
    round(avg_kd_ratio, 3)  as avg_kd_ratio,
    round(avg_kast, 2)      as avg_kast,
    round(avg_kills, 1)     as avg_kills,
    round(adr_pct, 4)       as adr_percentile,
    round(kd_pct, 4)        as kd_percentile,
    round(kast_pct, 4)      as kast_percentile,
    round(kills_pct, 4)     as kills_percentile,
    stats_in_top_15_pct,
    -- is_hidden_gem: true when player qualifies as an outlier in their tier
    case when stats_in_top_15_pct >= 3 and player_tier > 1 then true else false end as is_hidden_gem
from tier_percentiles
-- Only return tier 2/3 players with at least 3 elite stats (the "hidden gem" candidates)
where player_tier > 1
  and stats_in_top_15_pct >= 3
