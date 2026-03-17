-- Fact: per-match player performance stats.
-- Grain: one row per player per match (player_id + match_id is unique after dedup).
with players as (
    select * from {{ ref('int_players_unioned') }}
)

select
    {{ dbt_utils.generate_surrogate_key(['player_id', 'match_id', 'source']) }} as player_stat_sk,
    player_id,
    source,
    display_name,
    team_id,
    match_id,
    kills,
    deaths,
    adr,
    kd_ratio,
    kast,
    elo,
    recorded_at,
    -- Derived stats for downstream analytics
    case when deaths > 0 then cast(kills as float) / deaths else null end as computed_kd,
    case when (kills + deaths) > 0 then cast(kills as float) / (kills + deaths) else null end as kill_share
from players
where match_id is not null  -- only per-match stat records, not profiles
