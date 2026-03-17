-- Union all match sources into a single stream.
-- Source column preserved for downstream lineage and deduplication.
-- No deduplication here — mart models handle cross-source match dedup by match_id.
with faceit as (
    select * from {{ ref('stg_faceit_matches') }}
),

pandascore as (
    select * from {{ ref('stg_pandascore_matches') }}
),

kaggle as (
    select * from {{ ref('stg_kaggle_matches') }}
),

unioned as (
    select * from faceit
    union all
    select * from pandascore
    union all
    select * from kaggle
)

select * from unioned
