-- Cleaned unofficial HLTV round-history rows from cached HLTV mapstats.
-- Grain: one row per played round on one map.
select
    source,
    map_stats_id,
    match_id,
    event_id,
    event_name,
    map_name,
    try_to_timestamp_ntz(played_at) as played_at,
    round_number::int as round_number,
    t_team_id,
    t_team_name,
    ct_team_id,
    ct_team_name,
    winner_side,
    winner_team_id,
    winner_team_name,
    team1_id,
    team1_name,
    team2_id,
    team2_name,
    score_team1_after::int as score_team1_after,
    score_team2_after::int as score_team2_after,
    reported_score,
    round_outcome,
    is_overtime::boolean as is_overtime,
    try_to_timestamp_ntz(ingested_at) as ingested_at
from {{ source('raw', 'raw_hltv_round_history') }}
where map_stats_id is not null
  and round_number is not null
  and winner_team_id is not null
  and team1_id is not null
  and team2_id is not null
