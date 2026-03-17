-- Dimension: unique players with latest profile info.
-- Sourced from deduplicated int_players_unioned (FACEIT priority).
with players as (
    select * from {{ ref('int_players_unioned') }}
),

-- Keep most recent profile record per player (latest recorded_at)
latest as (
    select
        *,
        row_number() over (
            partition by player_id
            order by recorded_at desc
        ) as _row_num
    from players
)

select
    player_id,
    display_name,
    team_id,
    nationality,
    source              as primary_source,
    recorded_at         as last_updated
from latest
where _row_num = 1
