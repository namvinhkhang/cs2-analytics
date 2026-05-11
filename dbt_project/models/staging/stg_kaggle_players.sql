-- Staging model for Kaggle historical HLTV player stats.
-- Maps raw_kaggle_players into the canonical player-stat shape.
with source as (
    select * from {{ source('raw', 'raw_kaggle_players') }}
),

renamed as (
    select
        player_id,
        'kaggle' as source,
        display_name,
        team_id,
        country as nationality,
        kills,
        deaths,
        adr,
        case when deaths > 0 then cast(kills as float) / deaths else null end as kd_ratio,
        kast,
        rating,
        null as elo,
        match_id,
        recorded_at
    from source
    where player_id is not null
)

select * from renamed
