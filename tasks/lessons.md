# Lessons

- When giving dbt/Snowflake setup commands, explicitly explain that dbt's `env_var()` reads exported shell environment variables and does not automatically load `.env`; include a `set -a; source .env; set +a` or `dotenv run -- ...` command.
- In dbt on Snowflake, `+schema: MARTS` appends to the target schema by default, creating names like `STAGING_MARTS`; add a `generate_schema_name` macro when the intended physical schemas are exactly `STAGING` and `MARTS`, and grant `CREATE SCHEMA` on the database to the dbt role.
- For Upset Tracker training without Liquipedia rankings, preserve Kaggle `rank_1` and `rank_2` through canonical match Parquet and `mart_upset_features`; otherwise `favored_team_id` is null and every `is_upset` label becomes 0.
- For Hidden Gem Scout, do not rely on the old Kaggle dataset as the primary source because it only covers 2015-11-03 through 2020-03-18; use CS2-era sources such as VRS rankings and current player stats for 2023-09 onward.
- CS API `/players/stats/raw` does not preserve a trustworthy match date or real match ID for trend marts; use `/matches/` plus `/matches/{matchid}/stats` when Hidden Gem Scout needs CS2-era match-level player form.
- Long public-API bootstraps need visible progress logs and chunk controls; otherwise a slow sequential endpoint like CS API match stats looks frozen and a rate limit can waste the whole run.
- Do not join modern CS API player team IDs against Kaggle-derived `dim_teams` rows: Kaggle team IDs can be team-name strings, while CS API uses numeric HLTV-style IDs. Keep historical Kaggle out of modern CS2 mart lineage unless a model explicitly normalizes provider IDs.
