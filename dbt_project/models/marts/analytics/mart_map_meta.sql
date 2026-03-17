-- Pick rates and win rates per map.
-- Grain: one row per map_name aggregating all historical matches played on it.
with matches as (
    -- Only matches where a map was recorded
    select * from {{ ref('fact_matches') }}
    where map_name is not null
),

total_matches as (
    -- Total denominator for pick rate
    select count(*) as total from matches
),

map_stats as (
    select
        m.map_name,
        count(*)                                                              as times_played,
        -- Pick rate: fraction of all matches played on this map
        round(count(*)::float / nullif(t.total, 0), 4)                       as pick_rate,
        -- Team A win rate (team_a is the "home" side in the raw data;
        -- used as a proxy for structural CT/T-side advantage)
        round(
            sum(case when m.winner_id = m.team_a_id then 1 else 0 end)::float
            / nullif(count(case when m.winner_id is not null then 1 end), 0),
            4
        )                                                                     as team_a_win_rate,
        round(
            sum(case when m.winner_id = m.team_b_id then 1 else 0 end)::float
            / nullif(count(case when m.winner_id is not null then 1 end), 0),
            4
        )                                                                     as team_b_win_rate,
        -- Average total rounds as a measure of map closeness
        round(avg(coalesce(m.score_a, 0) + coalesce(m.score_b, 0)), 1)       as avg_total_rounds
    from matches m
    cross join total_matches t
    group by m.map_name, t.total
)

select * from map_stats
