-- Singular test: assert that foundational analytics marts have at least one row.
-- dbt singular tests FAIL when this query returns any rows.
-- A mart that returns a row here is empty (count(*) = 0), which is a failure.
--
-- Do not include sparse/optional marts here:
-- - mart_map_meta needs map-level rows, while CS API match ingestion is currently series-level.
-- - mart_head2head can be empty until enough repeated team pairings are loaded.
-- - mart_hidden_gems can legitimately be empty when no player clears the strict scout threshold.
{% set mart_models = [
    'mart_team_performance',
    'mart_player_leaderboard',
    'mart_upset_features',
    'mart_choke_profile'
] %}

{% for model in mart_models %}
select '{{ model }}' as model_name, count(*) as row_count
from {{ ref(model) }}
having count(*) = 0
{% if not loop.last %}union all{% endif %}
{% endfor %}
