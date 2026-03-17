-- Dimension: teams with world rankings from Liquipedia.
-- Uses latest ingested_at record per team_id for current ranking.
with teams as (
    select * from {{ ref('stg_liquipedia_teams') }}
),

-- Keep most recent record per team (latest ingestion wins)
latest as (
    select
        *,
        row_number() over (
            partition by team_id
            order by ingested_at desc
        ) as _row_num
    from teams
)

select
    team_id,
    name                as team_name,
    region,
    world_ranking,
    ingested_at         as last_updated
from latest
where _row_num = 1
