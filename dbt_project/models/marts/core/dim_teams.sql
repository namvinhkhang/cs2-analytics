-- Dimension: teams with rankings from modern and legacy sources.
-- Ranking priority: Liquipedia (manual/current) > CS API VRS > Kaggle legacy.
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
            when 'kaggle' then 3
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
            when 'kaggle' then 3
        end as ranking_source_priority
    from {{ ref('stg_csapi_team_rankings') }}
),

kaggle_rankings as (
    select
        team_a_id as team_id,
        team_a_id as team_name,
        null as region,
        team_a_ranking as world_ranking,
        played_at as last_updated,
        'kaggle' as ranking_source,
        case 'kaggle'
            when 'liquipedia' then 1
            when 'csapi' then 2
            when 'kaggle' then 3
        end as ranking_source_priority
    from {{ ref('stg_kaggle_matches') }}
    where team_a_id is not null
      and team_a_ranking is not null

    union all

    select
        team_b_id as team_id,
        team_b_id as team_name,
        null as region,
        team_b_ranking as world_ranking,
        played_at as last_updated,
        'kaggle' as ranking_source,
        case 'kaggle'
            when 'liquipedia' then 1
            when 'csapi' then 2
            when 'kaggle' then 3
        end as ranking_source_priority
    from {{ ref('stg_kaggle_matches') }}
    where team_b_id is not null
      and team_b_ranking is not null
),

unioned as (
    select * from liquipedia
    union all
    select * from csapi_rankings
    union all
    select * from kaggle_rankings
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
