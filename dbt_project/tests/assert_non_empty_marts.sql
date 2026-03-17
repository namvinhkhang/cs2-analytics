-- Singular test: assert that all analytics marts have at least one row.
-- dbt singular tests FAIL when this query returns any rows.
-- A mart that returns a row here is empty (count(*) = 0), which is a failure.
{% set mart_models = [
    'mart_team_performance',
    'mart_player_leaderboard',
    'mart_map_meta',
    'mart_head2head',
    'mart_upset_features',
    'mart_hidden_gems',
    'mart_choke_profile'
] %}

{% for model in mart_models %}
select '{{ model }}' as model_name, count(*) as row_count
from {{ ref(model) }}
having count(*) = 0
{% if not loop.last %}union all{% endif %}
{% endfor %}
