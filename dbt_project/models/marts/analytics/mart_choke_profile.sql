-- Team pressure performance from exact round-history rows where available.
-- Source is explicitly marked as `hltv_unofficial` because the upstream data
-- comes from best-effort HLTV mapstats exports, not an official API contract.
-- Grain: one row per team with map-level choke indicators.
with round_history as (
    select * from {{ ref('stg_hltv_round_history') }}
),

rounds_enriched as (
    select
        *,
        max(round_number) over (partition by map_stats_id) as total_rounds,
        max(score_team1_after) over (partition by map_stats_id) as final_team1_score,
        max(score_team2_after) over (partition by map_stats_id) as final_team2_score
    from round_history
),

team_rounds as (
    select
        map_stats_id,
        match_id,
        map_name,
        played_at,
        team1_id as team_id,
        team1_name as team_name,
        team2_id as opponent_id,
        team2_name as opponent_name,
        round_number,
        winner_team_id,
        score_team1_after as own_score_after,
        score_team2_after as opp_score_after,
        final_team1_score as final_own_score,
        final_team2_score as final_opp_score,
        is_overtime,
        total_rounds
    from rounds_enriched

    union all

    select
        map_stats_id,
        match_id,
        map_name,
        played_at,
        team2_id as team_id,
        team2_name as team_name,
        team1_id as opponent_id,
        team1_name as opponent_name,
        round_number,
        winner_team_id,
        score_team2_after as own_score_after,
        score_team1_after as opp_score_after,
        final_team2_score as final_own_score,
        final_team1_score as final_opp_score,
        is_overtime,
        total_rounds
    from rounds_enriched
),

team_round_state as (
    select
        *,
        case when winner_team_id = team_id then 1 else 0 end as won_round,
        own_score_after - case when winner_team_id = team_id then 1 else 0 end as own_score_before,
        opp_score_after - case when winner_team_id != team_id then 1 else 0 end as opp_score_before
    from team_rounds
),

map_team_summary as (
    select
        map_stats_id,
        any_value(match_id) as match_id,
        any_value(map_name) as map_name,
        any_value(played_at) as played_at,
        team_id,
        any_value(team_name) as team_name,
        any_value(opponent_id) as opponent_id,
        any_value(opponent_name) as opponent_name,
        max(final_own_score) as final_own_score,
        max(final_opp_score) as final_opp_score,
        max(total_rounds) as total_rounds,
        max(case when is_overtime then 1 else 0 end) as is_overtime_map,
        max(
            greatest(
                own_score_before - opp_score_before,
                own_score_after - opp_score_after
            )
        ) as largest_lead,
        max(case when round_number = 12 then own_score_after end) as halftime_own_score,
        max(case when round_number = 12 then opp_score_after end) as halftime_opp_score
    from team_round_state
    group by map_stats_id, team_id
),

map_team_flags as (
    select
        *,
        case when final_own_score > final_opp_score then 1 else 0 end as won_map,
        case when final_own_score < final_opp_score then 1 else 0 end as lost_map,
        case when abs(final_own_score - final_opp_score) <= 2 then 1 else 0 end as is_close_map,
        case when largest_lead >= 5 then 1 else 0 end as had_5plus_lead,
        case when largest_lead >= 5 and final_own_score < final_opp_score then 1 else 0 end
            as lead_blown_5plus,
        case when halftime_own_score > halftime_opp_score then 1 else 0 end as had_halftime_lead,
        case
            when halftime_own_score > halftime_opp_score and final_own_score < final_opp_score
                then 1
            else 0
        end as halftime_lead_lost,
        case
            when halftime_own_score < halftime_opp_score and final_own_score > final_opp_score
                then 1
            else 0
        end as halftime_comeback_win
    from map_team_summary
),

team_agg as (
    select
        team_id,
        any_value(team_name) as team_name,
        count(*) as total_maps,
        sum(total_rounds) as rounds_analyzed,
        sum(won_map) as wins,
        sum(lost_map) as losses,
        max(largest_lead) as largest_lead,
        sum(had_5plus_lead) as maps_with_5plus_lead,
        sum(lead_blown_5plus) as leads_blown,
        round(sum(lead_blown_5plus)::float / nullif(sum(had_5plus_lead), 0), 4)
            as lead_blown_rate,
        sum(halftime_lead_lost) as halftime_leads_lost,
        sum(halftime_comeback_win) as halftime_comeback_wins,
        round(sum(halftime_comeback_win)::float / nullif(sum(won_map), 0), 4)
            as comeback_rate,
        sum(is_overtime_map) as ot_matches,
        sum(case when is_overtime_map = 1 and won_map = 1 then 1 else 0 end) as ot_wins,
        sum(case when is_overtime_map = 1 and lost_map = 1 then 1 else 0 end) as ot_losses,
        round(
            sum(case when is_overtime_map = 1 and won_map = 1 then 1 else 0 end)::float
            / nullif(sum(is_overtime_map), 0),
            4
        ) as ot_win_rate,
        sum(is_close_map) as close_maps,
        sum(case when is_close_map = 1 and won_map = 1 then 1 else 0 end) as close_map_wins,
        round(
            sum(case when is_close_map = 1 and won_map = 1 then 1 else 0 end)::float
            / nullif(sum(is_close_map), 0),
            4
        ) as close_map_win_rate
    from map_team_flags
    group by team_id
),

league_averages as (
    select
        round(sum(leads_blown)::float / nullif(sum(maps_with_5plus_lead), 0), 4)
            as league_lead_blown_rate,
        round(sum(halftime_comeback_wins)::float / nullif(sum(wins), 0), 4)
            as league_halftime_comeback_rate,
        round(sum(ot_wins)::float / nullif(sum(ot_matches), 0), 4) as league_ot_win_rate,
        round(sum(close_map_wins)::float / nullif(sum(close_maps), 0), 4)
            as league_close_map_win_rate
    from team_agg
)

select
    ta.team_id,
    coalesce(t.team_name, ta.team_name) as team_name,
    t.world_ranking,
    ta.total_maps,
    ta.total_maps as maps_analyzed,
    ta.total_maps as total_scored_matches,
    ta.rounds_analyzed,
    ta.wins,
    ta.losses,
    ta.largest_lead,
    ta.maps_with_5plus_lead,
    ta.leads_blown,
    ta.lead_blown_rate,
    coalesce(ta.lead_blown_rate, 0) as lead_blown_rate_display,
    ta.lead_blown_rate - la.league_lead_blown_rate as lead_blown_rate_delta,
    ta.halftime_leads_lost,
    ta.halftime_comeback_wins as comebacks,
    ta.comeback_rate,
    ta.comeback_rate as halftime_comeback_rate,
    coalesce(ta.comeback_rate, 0) as halftime_comeback_rate_display,
    ta.comeback_rate - la.league_halftime_comeback_rate as halftime_comeback_rate_delta,
    'round_history_exact' as comeback_metric_type,
    true as halftime_data_available,
    ta.ot_matches,
    ta.ot_matches as overtime_maps_analyzed,
    ta.ot_wins,
    ta.ot_losses,
    ta.ot_win_rate,
    coalesce(ta.ot_win_rate, 0) as ot_win_rate_display,
    ta.ot_win_rate - la.league_ot_win_rate as ot_win_rate_delta,
    ta.close_maps,
    ta.close_maps as close_maps_analyzed,
    ta.close_map_wins,
    ta.close_map_win_rate,
    coalesce(ta.close_map_win_rate, 0) as close_map_win_rate_display,
    ta.close_map_win_rate - la.league_close_map_win_rate as close_map_win_rate_delta,
    50 as minimum_stable_maps,
    case
        when ta.total_maps < 20 then 'limited'
        when ta.total_maps < 50 then 'directional'
        else 'stable'
    end as sample_quality,
    ta.total_maps < 20 as sample_size_warning,
    'hltv_unofficial' as metric_source,
    true as round_history_available,
    false as clutch_data_available,
    false as bracket_data_available,
    null::float as elimination_win_pct,
    null::float as winners_bracket_win_pct
from team_agg ta
cross join league_averages la
left join {{ ref('dim_teams') }} t
    on ta.team_id = t.team_id
