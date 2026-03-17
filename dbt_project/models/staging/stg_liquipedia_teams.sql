-- Staging model for Liquipedia team metadata.
-- Renames and casts columns from raw_liquipedia_teams. Single-source, no aggregations.
-- world_ranking is used in mart models for upset detection logic.
-- Filters out records with null team_id to enforce primary key integrity.
with source as (
    select * from {{ source('raw', 'raw_liquipedia_teams') }}
),

renamed as (
    select
        team_id,
        'liquipedia' as source,
        name,
        region,
        world_ranking,
        ingested_at
    from source
    where team_id is not null
)

select * from renamed
