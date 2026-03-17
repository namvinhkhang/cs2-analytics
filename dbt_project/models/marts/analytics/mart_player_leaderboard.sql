-- Per-player aggregated stats with tier percentile rankings.
-- Tier assignment: T1 = world_ranking 1–10, T2 = 11–30, T3 = 31+.
-- Grain: one row per player with avg stats and within-tier percent_rank columns.
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
        count(*)                           as matches_played,
        round(avg(s.adr), 2)               as avg_adr,
        round(avg(s.kd_ratio), 3)          as avg_kd_ratio,
        round(avg(s.kast), 2)              as avg_kast,
        round(avg(s.kills), 1)             as avg_kills,
        round(avg(s.deaths), 1)            as avg_deaths,
        max(s.elo)                         as peak_elo
    from stats s
    group by s.player_id, s.display_name, s.team_id
),

-- Enrich with team tier (based on world ranking)
tiered as (
    select
        pa.*,
        t.world_ranking,
        case
            when t.world_ranking between 1 and 10 then 1
            when t.world_ranking between 11 and 30 then 2
            else 3
        end                                as tier
    from player_agg pa
    left join teams t on pa.team_id = t.team_id
),

-- Compute within-tier percentile ranks for each key stat
-- Higher percent_rank = better performance within the tier
ranked as (
    select
        *,
        percent_rank() over (partition by tier order by avg_adr asc)       as adr_pct_rank,
        percent_rank() over (partition by tier order by avg_kd_ratio asc)  as kd_pct_rank,
        percent_rank() over (partition by tier order by avg_kast asc)      as kast_pct_rank,
        percent_rank() over (partition by tier order by avg_kills asc)     as kills_pct_rank
    from tiered
)

select * from ranked
