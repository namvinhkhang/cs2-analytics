-- Staging model for Valve public regional standings.
-- Grain: one Valve team row per standings snapshot.
with source as (
    select * from {{ source('raw', 'raw_valve_team_regions') }}
),

renamed as (
    select
        snapshot_date,
        'valve' as source,
        team_name,
        normalized_team_name,
        region,
        regional_rank,
        global_rank,
        points,
        roster,
        detail_path
    from source
    where snapshot_date is not null
      and normalized_team_name is not null
      and region is not null
)

select * from renamed
