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

liquipedia_region_names as (
    select
        regexp_replace(
            lower(
                regexp_replace(name, '^team[ _-]+', '', 1, 1, 'i')
            ),
            '[^a-z0-9]+',
            ''
        ) as normalized_team_name,
        region
    from {{ ref('stg_liquipedia_teams') }}
    where name is not null
      and region is not null
    qualify count(*) over (partition by normalized_team_name) = 1
),

latest_valve_snapshot as (
    select max(snapshot_date) as snapshot_date
    from {{ ref('stg_valve_team_regions') }}
),

latest_valve_regions as (
    select
        normalized_team_name,
        region
    from {{ ref('stg_valve_team_regions') }}
    where normalized_team_name is not null
      and region is not null
      and snapshot_date = (select snapshot_date from latest_valve_snapshot)
),

valve_region_names as (
    select
        normalized_team_name,
        max(region) as region
    from latest_valve_regions
    group by normalized_team_name
    having count(distinct region) = 1
),

csapi_rankings as (
    select
        c.team_id,
        c.name as team_name,
        coalesce(
            case when lower(c.region) = 'global' then null else c.region end,
            lr.region,
            vr.region
        ) as region,
        c.world_ranking,
        c.ranking_date as last_updated,
        'csapi' as ranking_source,
        case 'csapi'
            when 'liquipedia' then 1
            when 'csapi' then 2
        end as ranking_source_priority
    from {{ ref('stg_csapi_team_rankings') }} c
    left join liquipedia_region_names lr
        on regexp_replace(
            lower(
                regexp_replace(c.name, '^team[ _-]+', '', 1, 1, 'i')
            ),
            '[^a-z0-9]+',
            ''
        ) = lr.normalized_team_name
    left join valve_region_names vr
        on regexp_replace(
            lower(
                regexp_replace(c.name, '^team[ _-]+', '', 1, 1, 'i')
            ),
            '[^a-z0-9]+',
            ''
        ) = vr.normalized_team_name
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
