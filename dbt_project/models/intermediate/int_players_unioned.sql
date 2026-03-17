-- Union player sources and deduplicate by player_id.
-- When a player appears in both FACEIT and PandaScore, keep FACEIT record
-- (richer stats: ELO, KAST). Uses ROW_NUMBER with source priority ordering.
with faceit as (
    select * from {{ ref('stg_faceit_players') }}
),

pandascore as (
    select * from {{ ref('stg_pandascore_players') }}
),

unioned as (
    select * from faceit
    union all
    select * from pandascore
),

-- Deduplicate: for each (player_id, match_id) combo, prefer FACEIT over PandaScore.
-- For profile-level records (match_id IS NULL), deduplicate by player_id alone.
ranked as (
    select
        *,
        row_number() over (
            partition by player_id, coalesce(match_id, '__profile__')
            order by
                case source
                    when 'faceit' then 1
                    when 'pandascore' then 2
                    else 3
                end
        ) as _row_num
    from unioned
)

select
    player_id,
    source,
    display_name,
    team_id,
    nationality,
    kills,
    deaths,
    adr,
    kd_ratio,
    kast,
    elo,
    match_id,
    recorded_at
from ranked
where _row_num = 1
