-- Dimension: teams with rankings from current sources.
-- Ranking priority: Liquipedia (manual/current) > CS API VRS.
with liquipedia as (
    select
        team_id,
        name as team_name,
        region,
        world_ranking,
        ingested_at as last_updated,
        'liquipedia' as ranking_source,
        case 'liquipedia'
            when 'liquipedia' then 1
            when 'csapi' then 2
        end as ranking_source_priority
    from {{ ref('stg_liquipedia_teams') }}
),

csapi_rankings as (
    select
        team_id,
        name as team_name,
        region,
        world_ranking,
        ranking_date as last_updated,
        'csapi' as ranking_source,
        case 'csapi'
            when 'liquipedia' then 1
            when 'csapi' then 2
        end as ranking_source_priority
    from {{ ref('stg_csapi_team_rankings') }}
),

unioned as (
    select * from liquipedia
    union all
    select * from csapi_rankings
),

latest as (
    select
        *,
        row_number() over (
            partition by team_id
            order by ranking_source_priority asc, last_updated desc, world_ranking asc
        ) as _row_num
    from unioned
)

select
    team_id,
    team_name,
    region,
    world_ranking,
    ranking_source,
    last_updated
from latest
where _row_num = 1
