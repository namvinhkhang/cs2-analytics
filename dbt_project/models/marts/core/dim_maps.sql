-- Dimension: distinct CS2 maps extracted from all match data.
with maps as (
    select distinct
        map_name
    from {{ ref('int_matches_unioned') }}
    where map_name is not null
)

select
    {{ dbt_utils.generate_surrogate_key(['map_name']) }} as map_sk,
    map_name
from maps
