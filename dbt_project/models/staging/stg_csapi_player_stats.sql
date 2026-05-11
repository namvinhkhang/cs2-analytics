-- Staging model for CS API modern CS2 match-level player stats.
-- Rows come from /matches/{matchid}/stats, so match_id is a real CS API match
-- identifier and recorded_at is the match date.
with source as (
    select * from {{ source('raw', 'raw_csapi_player_stats') }}
),

renamed as (
    select
        player_id,
        'csapi' as source,
        display_name,
        team_id,
        nationality,
        kills,
        deaths,
        adr,
        kd_ratio,
        kast,
        rating,
        elo,
        match_id,
        recorded_at
    from source
    where player_id is not null
      and match_id is not null
)

select * from renamed
