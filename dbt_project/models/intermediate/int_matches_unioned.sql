-- Union modern match sources into a single stream.
-- Source column preserved for downstream lineage and deduplication.
-- No deduplication here — mart models handle cross-source match dedup by match_id.
with faceit as (
    select * from {{ ref('stg_faceit_matches') }}
),

pandascore as (
    select * from {{ ref('stg_pandascore_matches') }}
),

csapi as (
    select * from {{ ref('stg_csapi_matches') }}
),

unioned as (
    select * from faceit
    union all
    select * from pandascore
    union all
    select * from csapi
)

select * from unioned
