-- Union player sources and deduplicate by player_id.
-- When a player appears in both FACEIT and PandaScore, keep FACEIT record
-- (richer stats: ELO, KAST). Uses ROW_NUMBER with source priority ordering.
with faceit as (
    select * from {{ ref('stg_faceit_players') }}
),

pandascore as (
    select * from {{ ref('stg_pandascore_players') }}
),

kaggle as (
    select * from {{ ref('stg_kaggle_players') }}
),

csapi as (
    select * from {{ ref('stg_csapi_player_stats') }}
),

unioned as (
    select * from faceit
    union all
    select * from pandascore
    union all
    select * from kaggle
    union all
    select * from csapi
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
                    when 'csapi' then 3
                    when 'kaggle' then 4
                    else 4
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
    rating,
    elo,
    match_id,
    recorded_at
from ranked
where _row_num = 1
