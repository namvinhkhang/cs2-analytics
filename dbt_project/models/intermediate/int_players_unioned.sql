-- Union modern player sources and deduplicate by player_id.
-- Profile snapshots prefer CS API because it carries current HLTV-style team
-- context; match rows keep FACEIT/PandaScore priority for richer stat fields.
with faceit as (
    select * from {{ ref('stg_faceit_players') }}
),

pandascore as (
    select * from {{ ref('stg_pandascore_players') }}
),

csapi as (
    select * from {{ ref('stg_csapi_player_stats') }}
),

unioned as (
    select * from faceit
    union all
    select * from pandascore
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
                case
                    when match_id is null and source = 'csapi' then 1
                    when source = 'faceit' then 2
                    when source = 'pandascore' then 3
                    when source = 'csapi' then 4
                    else 5
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
