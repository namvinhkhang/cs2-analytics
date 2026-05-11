# Graph Report - .  (2026-05-10)

## Corpus Check
- Corpus is ~29,248 words - fits in a single context window. You may not need a graph.

## Summary
- 852 nodes · 1243 edges · 73 communities (48 shown, 25 thin omitted)
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 362 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Kaggle Bootstrap Flow|Kaggle Bootstrap Flow]]
- [[_COMMUNITY_FACEIT Ingestion Client|FACEIT Ingestion Client]]
- [[_COMMUNITY_Airflow Daily Ingestion|Airflow Daily Ingestion]]
- [[_COMMUNITY_Architecture Decisions|Architecture Decisions]]
- [[_COMMUNITY_PandaScore Ingestion Client|PandaScore Ingestion Client]]
- [[_COMMUNITY_Base API Client Tests|Base API Client Tests]]
- [[_COMMUNITY_Liquipedia Client Contracts|Liquipedia Client Contracts]]
- [[_COMMUNITY_Parquet Schema Tests|Parquet Schema Tests]]
- [[_COMMUNITY_Warehouse Bootstrap Config|Warehouse Bootstrap Config]]
- [[_COMMUNITY_Liquipedia Domain Models|Liquipedia Domain Models]]
- [[_COMMUNITY_PandaScore Domain Models|PandaScore Domain Models]]
- [[_COMMUNITY_Core dbt Marts|Core dbt Marts]]
- [[_COMMUNITY_FACEIT Domain Models|FACEIT Domain Models]]
- [[_COMMUNITY_Canonical Match Model|Canonical Match Model]]
- [[_COMMUNITY_Settings Configuration|Settings Configuration]]
- [[_COMMUNITY_Canonical Player Models|Canonical Player Models]]
- [[_COMMUNITY_Kaggle Fixture Tests|Kaggle Fixture Tests]]
- [[_COMMUNITY_Kaggle CSV Edge Cases|Kaggle CSV Edge Cases]]
- [[_COMMUNITY_dbt Run DAG Tests|dbt Run DAG Tests]]
- [[_COMMUNITY_Ingestion Schema Semantics|Ingestion Schema Semantics]]
- [[_COMMUNITY_Base API Client|Base API Client]]
- [[_COMMUNITY_Liquipedia Basic Tests|Liquipedia Basic Tests]]
- [[_COMMUNITY_Airflow DAG Test Fixtures|Airflow DAG Test Fixtures]]
- [[_COMMUNITY_Liquipedia Ingestion Tests|Liquipedia Ingestion Tests]]
- [[_COMMUNITY_Kaggle Ingester Fixtures|Kaggle Ingester Fixtures]]
- [[_COMMUNITY_Liquipedia Fetch Methods|Liquipedia Fetch Methods]]
- [[_COMMUNITY_Liquipedia Client|Liquipedia Client]]
- [[_COMMUNITY_DAG Structure Tests|DAG Structure Tests]]
- [[_COMMUNITY_Kaggle Ingester|Kaggle Ingester]]
- [[_COMMUNITY_Weekly Rankings DAG|Weekly Rankings DAG]]
- [[_COMMUNITY_Daily Matches DAG|Daily Matches DAG]]
- [[_COMMUNITY_Intermediate dbt Models|Intermediate dbt Models]]
- [[_COMMUNITY_Daily S3 Idempotency|Daily S3 Idempotency]]
- [[_COMMUNITY_Canonical Team Tests|Canonical Team Tests]]
- [[_COMMUNITY_FACEIT Player Model|FACEIT Player Model]]
- [[_COMMUNITY_Tournament Sync DAG|Tournament Sync DAG]]
- [[_COMMUNITY_Slack Alerting|Slack Alerting]]
- [[_COMMUNITY_Kaggle Credential Tests|Kaggle Credential Tests]]
- [[_COMMUNITY_Kaggle S3 Write Tests|Kaggle S3 Write Tests]]
- [[_COMMUNITY_Kaggle Download Tests|Kaggle Download Tests]]
- [[_COMMUNITY_Pytest Environment Fixtures|Pytest Environment Fixtures]]
- [[_COMMUNITY_Kaggle Instantiation Tests|Kaggle Instantiation Tests]]
- [[_COMMUNITY_DAG Bag Fixture|DAG Bag Fixture]]
- [[_COMMUNITY_Slack Smoke DAG|Slack Smoke DAG]]
- [[_COMMUNITY_dbt Airflow DAG|dbt Airflow DAG]]
- [[_COMMUNITY_Kaggle Bootstrap Script|Kaggle Bootstrap Script]]
- [[_COMMUNITY_Package Metadata|Package Metadata]]
- [[_COMMUNITY_Liquipedia S3 Prefix|Liquipedia S3 Prefix]]
- [[_COMMUNITY_Liquipedia Tournament Tests|Liquipedia Tournament Tests]]
- [[_COMMUNITY_Airflow Utils Package|Airflow Utils Package]]
- [[_COMMUNITY_PandaScore Test Contracts|PandaScore Test Contracts]]
- [[_COMMUNITY_PandaScore Match List|PandaScore Match List]]
- [[_COMMUNITY_PandaScore Pagination Params|PandaScore Pagination Params]]
- [[_COMMUNITY_PandaScore Rate Limit|PandaScore Rate Limit]]
- [[_COMMUNITY_PandaScore Empty Matches|PandaScore Empty Matches]]
- [[_COMMUNITY_PandaScore Players List|PandaScore Players List]]
- [[_COMMUNITY_PandaScore Player Rate Limit|PandaScore Player Rate Limit]]
- [[_COMMUNITY_PandaScore Player Team None|PandaScore Player Team None]]
- [[_COMMUNITY_PandaScore Match Write Count|PandaScore Match Write Count]]
- [[_COMMUNITY_PandaScore Match S3 Key|PandaScore Match S3 Key]]
- [[_COMMUNITY_PandaScore Empty Write Skip|PandaScore Empty Write Skip]]
- [[_COMMUNITY_PandaScore Sequential Fetch|PandaScore Sequential Fetch]]
- [[_COMMUNITY_PandaScore Player Write Count|PandaScore Player Write Count]]
- [[_COMMUNITY_PandaScore Free Tier Stats|PandaScore Free Tier Stats]]
- [[_COMMUNITY_PandaScore Player S3 Key|PandaScore Player S3 Key]]
- [[_COMMUNITY_Auth Header Contract|Auth Header Contract]]
- [[_COMMUNITY_Rate Limited GET|Rate Limited GET]]
- [[_COMMUNITY_CS2 Analytics Package|CS2 Analytics Package]]

## God Nodes (most connected - your core abstractions)
1. `Match` - 40 edges
2. `LiquipediaClient` - 34 edges
3. `PandaScoreClient` - 33 edges
4. `Player` - 33 edges
5. `KaggleBootstrapIngester` - 29 edges
6. `PandaScoreMatch` - 27 edges
7. `FACEITClient` - 25 edges
8. `FACEITMatch` - 24 edges
9. `PandaScorePlayer` - 23 edges
10. `Team` - 22 edges

## Surprising Connections (you probably didn't know these)
- `dbt_test BashOperator` --references--> `Analytics dbt Schema Tests`  [INFERRED]
  airflow/dags/cs2_dbt_run.py → dbt_project/models/marts/analytics/analytics.yml
- `Graphify Extraction Workflow Todo` --references--> `Canonical Schema Contract`  [INFERRED]
  tasks/todo.md → src/cs2_analytics/models/canonical.py
- `Direct Slack Webhook Decision` --rationale_for--> `on_failure_callback`  [EXTRACTED]
  CLAUDE.md → airflow/dags/utils/slack_alerts.py
- `mart_hidden_gems` --implements--> `Hidden Gem Scout`  [EXTRACTED]
  dbt_project/models/marts/analytics/mart_hidden_gems.sql → cs2-analytics-internship-project.md
- `cs2_daily_matches DAG` --implements--> `Phase 2 Airflow Orchestration`  [INFERRED]
  airflow/dags/cs2_daily_matches.py → cs2-analytics-internship-project.md

## Hyperedges (group relationships)
- **Full ELT Pipeline Flow** — internship_data_sources, docker_compose_airflow_celeryexecutor_stack, s3_external_stage, snowflake_raw_tables, dbt_project_models, internship_streamlit_dashboard [INFERRED 0.85]
- **Airflow Failure Alerting Pattern** — cs2_daily_matches_dag, cs2_tournament_sync_dag, cs2_weekly_rankings_dag, cs2_dbt_run_dag, fail_intentionally_dag, slack_alerts_on_failure_callback [EXTRACTED 1.00]
- **dbt Analytics Mart Layer** — int_matches_unioned, int_players_unioned, mart_hidden_gems, mart_choke_profile, mart_head2head, mart_map_meta, analytics_schema_tests [EXTRACTED 1.00]
- **dbt Layered Warehouse Flow** — snowflake_raw_schema, snowflake_staging_schema, snowflake_marts_schema, staging_yml_model_contracts, core_yml_model_contracts, fact_matches_model, fact_player_stats_model, mart_team_performance_model, mart_player_leaderboard_model, mart_upset_features_model [EXTRACTED 0.95]
- **Upset Tracker Feature Engineering Flow** — stg_liquipedia_teams_model, dim_teams_model, fact_matches_model, mart_upset_features_model, upset_tracker_feature_set_concept [EXTRACTED 0.93]
- **Kaggle Bootstrap to Raw Match Pipeline** — bootstrap_kaggle_main, kaggle_bootstrap_ingester, kaggle_raw_s3_prefix, snowflake_copy_into_raw_loads, raw_kaggle_matches_table, stg_kaggle_matches_model [INFERRED 0.80]
- **Raw Source To Canonical Parquet S3 Flow** — faceit_faceit_client, kaggle_bootstrap_ingester, liquipedia_liquipedia_client, pandascore_pandascore_client, canonical_schema_contract, parquet_explicit_schema_contract, s3_hive_partitioned_layout [INFERRED 0.86]
- **Rate-Limited Client Family** — base_rate_limited_async_client_pattern, faceit_faceit_client, liquipedia_liquipedia_client, pandascore_pandascore_client [EXTRACTED 1.00]
- **Ingestion Clients to Canonical S3 Flow** — test_liquipedia_client_liquipediaclient_ingest_all, test_pandascore_client_ingest_matches, test_pandascore_client_ingest_players, test_models_canonical_models_contract, test_s3_write_parquet_to_s3, test_s3_hive_partitioned_s3_path [INFERRED 0.86]
- **Canonical Schema Parquet Contract** — test_models_canonical_models_contract, test_models_match_score_fields, test_parquet_match_schema, test_parquet_player_schema, test_parquet_team_schema, test_parquet_models_to_records, test_parquet_null_batch_schema_drift_prevention [INFERRED 0.88]
- **Airflow Operational Test Contract** — test_dags_airflow_dagbag_fixture, test_dags_airflow_import_environment, test_dags_cs2_daily_matches_dag, test_daily_matches_s3_idempotency_helper, test_dbt_run_dag_structure, test_slack_alerts_on_failure_callback [INFERRED 0.82]

## Communities (73 total, 25 thin omitted)

### Community 0 - "Kaggle Bootstrap Flow"
Cohesion: 0.05
Nodes (43): Parse one CSV, write Parquet to S3, return count of matches written.          Us, Full bootstrap pipeline: credentials → download → parse CSVs → S3.          Retu, Write Kaggle credentials to ~/.kaggle/kaggle.json.          Required before any, Download and unzip Kaggle dataset to download_path.          Returns the path co, TDD tests for cs2_analytics.utils.s3 — S3 upload and Hive path utilities.  RED p, write_parquet_to_s3 with empty records must still upload a valid Parquet file., Uploaded body must be snappy-compressed Parquet (not uncompressed or gzip)., boto3.client must be called with the correct region_name. (+35 more)

### Community 1 - "FACEIT Ingestion Client"
Cohesion: 0.06
Nodes (38): FACEITClient, FACEIT Data API v4 ingestion client for CS2 per-match statistics.  Fetches match, FACEIT Data API v4 client for CS2 per-match statistics.      Rate limit: ~1 req/, Return FACEIT Bearer token auth header., Fetch match metadata by ID.          Endpoint: GET /matches/{match_id}         R, Fetch per-player stats for a completed match.          Endpoint: GET /matches/{m, Fetch match metadata and player stats, then write both to S3.          Processes, Tests for FACEITClient ingestion client — covers ING-02.  Tests cover: - Class a (+30 more)

### Community 2 - "Airflow Daily Ingestion"
Cohesion: 0.05
Nodes (46): AWS S3 head_object, Airflow DAG Import Pattern, Direct Slack Webhook Decision, cs2_daily_matches._ingest_faceit, cs2_daily_matches._ingest_pandascore, cs2_daily_matches._s3_key_exists, cs2_daily_matches DAG, ingest_faceit_matches Task (+38 more)

### Community 3 - "Architecture Decisions"
Cohesion: 0.05
Nodes (46): Analytics dbt Schema Tests, AWS S3 over GCS Decision, Full-Stack ELT Pipeline, Canonical vs Source Model Pattern, No HLTV Scraping Decision, Repository Guidance, Snowflake over BigQuery Decision, copy_into_raw Task (+38 more)

### Community 4 - "PandaScore Ingestion Client"
Cohesion: 0.06
Nodes (34): PandaScoreClient, PandaScore REST API ingestion client for CS2 (counterstrike) match results and p, Fetch match pages and write canonical Match records to S3.          Fetches page, Fetch player pages and write canonical Player records to S3.          Advanced s, PandaScore REST API client for CS2 (counterstrike) match results and player stat, Return PandaScore Bearer token auth header., Fetch recent CS2 past match results.          Endpoint: GET /csgo/matches/past, Fetch CS2 player profiles.          Endpoint: GET /csgo/players         Sleeps 3 (+26 more)

### Community 5 - "Base API Client Tests"
Cohesion: 0.07
Nodes (36): BaseAPIClient, ConcreteClient, Tests for BaseAPIClient ABC — covers ING-06.  Uses a concrete ConcreteClient sub, get() should return the parsed JSON as a dict on a 200 response., get() should forward **params as query parameters., get() should raise httpx.HTTPStatusError on 404 (client error, not retried)., get() should raise HTTPStatusError on 429 (rate limited).      tenacity's retry_, paginate() should yield first page and stop when fewer items than limit returned (+28 more)

### Community 6 - "Liquipedia Client Contracts"
Cohesion: 0.07
Nodes (36): Client Rate Limit Sleep Policy, Liquipedia API v3 Endpoint Contract, Liquipedia Apikey Auth Header, Liquipedia Canonical Entity Write, LiquipediaClient Contract Tests, LiquipediaClient Get Methods, LiquipediaClient.ingest_all, Liquipedia Result Envelope Deserialization (+28 more)

### Community 7 - "Parquet Schema Tests"
Cohesion: 0.06
Nodes (32): TDD tests for cs2_analytics.utils.parquet — pyarrow schema utilities.  RED phase, world_ranking must use int64 (not int32) for forward compatibility., models_to_records must return a list of plain dicts via model_dump()., models_to_records([]) must return an empty list without raising., Player with all-None stats must round-trip to Parquet buffer without ArrowInvali, MATCH_SCHEMA must declare exactly 10 fields (7 original + score_a, score_b, is_o, Match with None winner_id and map_name must serialize to Parquet correctly., Non-optional Match fields must be marked nullable=False in schema. (+24 more)

### Community 8 - "Warehouse Bootstrap Config"
Cohesion: 0.1
Nodes (30): bootstrap_kaggle.main, CS2_ANALYTICS Database, cs2_raw_stage, cs2_s3_int Storage Integration, cs2_analytics.utils.config.settings, CS2_WH Warehouse, FACEIT Primary Stats Source, Hive-Partitioned S3 Raw Layout (+22 more)

### Community 9 - "Liquipedia Domain Models"
Cohesion: 0.11
Nodes (21): BaseModel, Canonical team model written to Parquet by Liquipedia and PandaScore clients., Team, LiquipediaMatch, LiquipediaPlacement, LiquipediaTeam, LiquipediaTournament, Liquipedia API v3 raw Pydantic v2 models.  Source models use extra="ignore" to s (+13 more)

### Community 10 - "PandaScore Domain Models"
Cohesion: 0.1
Nodes (17): PandaScoreMatch, PandaScorePlayer, PandaScore API raw Pydantic v2 models.  Source models use extra="ignore" to sile, Raw PandaScore match record. Maps to canonical Match via to_canonical()., Map PandaScore match fields to the shared canonical Match schema., Raw PandaScore player record. Maps to canonical Player via to_canonical()., Map PandaScore player fields to the shared canonical Player schema.          Per, PandaScore source model tests. (+9 more)

### Community 11 - "Core dbt Marts"
Cohesion: 0.15
Nodes (24): assert_non_empty_marts, Core dbt Model Contracts, dbt_utils.generate_surrogate_key, dim_maps, dim_players, dim_teams, dim_tournaments, fact_matches (+16 more)

### Community 12 - "FACEIT Domain Models"
Cohesion: 0.12
Nodes (14): FACEITMatch, Raw FACEIT match model. Maps to canonical Match via to_canonical()., Map FACEIT match fields to the shared canonical Match schema., FACEITMatch and FACEITPlayer model tests., FACEITMatch silently drops unknown extra fields., FACEITMatch.to_canonical() returns a Match instance., FACEITMatch.to_canonical() maps winner when results present., FACEITMatch.to_canonical() falls back to 'unknown' for missing team keys. (+6 more)

### Community 13 - "Canonical Match Model"
Cohesion: 0.12
Nodes (14): Match, Canonical match model written to Parquet by every ingestion client.      The pla, Canonical Match model tests., Match with all required fields succeeds., Match rejects unknown fields (extra='forbid')., Tests for canonical Match score_a, score_b, is_overtime fields (Phase 3 addition, Match without score fields has score_a=None, score_b=None, is_overtime=None., Match with score_a=16, score_b=13, is_overtime=False stores values correctly. (+6 more)

### Community 14 - "Settings Configuration"
Cohesion: 0.13
Nodes (12): BaseSettings, Tests for Settings class — verifies CS2_ env prefix, validation, and defaults., Test Settings class behavior., Settings class is importable., Settings() raises ValidationError when CS2_FACEIT_API_KEY is absent., settings.aws_region defaults to 'us-east-1' when CS2_AWS_REGION is not set., settings.faceit_api_key returns the value of CS2_FACEIT_API_KEY env var., settings.aws_region is overridable via CS2_AWS_REGION. (+4 more)

### Community 15 - "Canonical Player Models"
Cohesion: 0.14
Nodes (12): Player, Canonical Pydantic v2 models shared across all ingestion sources.  These models, Canonical player model written to Parquet by FACEIT and PandaScore clients., LiquipediaPlayer, Raw Liquipedia player record. Maps to canonical Player via to_canonical()., Map Liquipedia player fields to the shared canonical Player schema., Player with all stat fields populated succeeds., LiquipediaPlayer.to_canonical() returns a Player instance. (+4 more)

### Community 16 - "Kaggle Fixture Tests"
Cohesion: 0.12
Nodes (15): ingester(), Tests for KaggleBootstrapIngester using the tests/fixtures/kaggle/sample_matches, setup_kaggle_credentials must write correct JSON to ~/.kaggle/kaggle.json., Path to the realistic sample CSV fixture with 3 data rows., KaggleBootstrapIngester configured with a test bucket., csv_to_matches should return one Match per valid row in the fixture (3 rows)., First fixture row must map to canonical Match fields correctly., Third fixture row has empty map_winner — winner_id must be None. (+7 more)

### Community 17 - "Kaggle CSV Edge Cases"
Cohesion: 0.12
Nodes (5): Empty string winner should be stored as None., team_a / team_b / winner column variants must be recognised., Rows where team_a or team_b is blank must be skipped., When no match_id column exists, generate index-based ID., TestCsvToMatches

### Community 18 - "dbt Run DAG Tests"
Cohesion: 0.12
Nodes (9): Structural tests for cs2_dbt_run Airflow DAG.  Validates DAG structure, task cou, cs2_dbt_run DAG structural validation., cs2_dbt_run DAG loads without import errors., cs2_dbt_run has exactly 3 tasks., cs2_dbt_run task IDs match expected pipeline., cs2_dbt_run runs daily at 08:00 UTC., cs2_dbt_run has cs2 and warehouse tags., Pipeline order: copy_into_raw >> dbt_run >> dbt_test. (+1 more)

### Community 19 - "Ingestion Schema Semantics"
Cohesion: 0.19
Nodes (15): BaseAPIClient, Rate-Limited Async API Client Pattern, Canonical Match Model, Canonical Player Model, Canonical Schema Contract, Settings, FACEITClient, KaggleBootstrapIngester (+7 more)

### Community 20 - "Base API Client"
Cohesion: 0.18
Nodes (9): ABC, _auth_headers(), BaseAPIClient, get(), Abstract base class for all CS2 data API ingestion clients.  Provides shared ret, Paginate through results, yielding each page as a list.          Stops when the, Return self to support `async with client:` usage., Close the underlying httpx.AsyncClient to release connections. (+1 more)

### Community 21 - "Liquipedia Basic Tests"
Cohesion: 0.14
Nodes (7): Tests for LiquipediaClient ingestion client.  Tests cover: - Class attributes: B, get_matches() deserializes the {result: [...]} envelope into LiquipediaMatch lis, LiquipediaClient.BASE_URL must point to API v3., _semaphore must be a class-level asyncio.Semaphore., test_base_url(), test_get_matches_returns_liquipedia_match_list(), test_semaphore_is_asyncio_semaphore()

### Community 22 - "Airflow DAG Test Fixtures"
Cohesion: 0.16
Nodes (14): Airflow DagBag Fixture, Airflow DAG Import Environment, cs2_daily_matches DAG, cs2_tournament_sync DAG, cs2_weekly_rankings DAG, DAG Structure Tests, boto3 S3 head_object, Daily Matches S3 Idempotency Helper (+6 more)

### Community 23 - "Liquipedia Ingestion Tests"
Cohesion: 0.15
Nodes (13): load_fixture(), get_teams() deserializes the {result: [...]} envelope into LiquipediaTeam list., get_players() deserializes the {result: [...]} envelope into LiquipediaPlayer li, get_placements() deserializes the {result: [...]} envelope into LiquipediaPlacem, asyncio.sleep(2.0) must be called after each get_teams() request (rate limit pol, ingest_all() returns a dict with keys for all 5 entity types., ingest_all() calls write_parquet_to_s3 for teams, players, and matches., test_get_placements_returns_liquipedia_placement_list() (+5 more)

### Community 24 - "Kaggle Ingester Fixtures"
Cohesion: 0.17
Nodes (11): alternate_columns_csv(), ingester(), missing_teams_csv(), no_match_id_csv(), Tests for KaggleBootstrapIngester — TDD RED phase.  Tests cover: - Class instant, A CSV with no match_id column — should fall back to index-based IDs., A KaggleBootstrapIngester with a test bucket., A CSV using standard HLTV Kaggle column names. (+3 more)

### Community 25 - "Liquipedia Fetch Methods"
Cohesion: 0.17
Nodes (6): Fetch CS2 tournaments from Liquipedia.          Endpoint: GET /tournament?wiki=c, Fetch CS2 tournament placements from Liquipedia.          Endpoint: GET /placeme, Ingest all 5 CS2 entity types and write canonical records to S3.          Teams,, Fetch CS2 teams from Liquipedia.          Endpoint: GET /team?wiki=counterstrike, Fetch CS2 players from Liquipedia.          Endpoint: GET /player?wiki=counterst, Fetch CS2 match results from Liquipedia.          Endpoint: GET /match2 (NOT /ma

### Community 26 - "Liquipedia Client"
Cohesion: 0.17
Nodes (10): LiquipediaClient, Liquipedia REST API v3 ingestion client for CS2 competitive data.  Fetches five, Liquipedia REST API v3 client for CS2 competitive data.      IMPORTANT: Liquiped, Return Liquipedia API key auth header.          Note: Liquipedia uses 'Apikey' (, get_matches() must call /match2 (not /match) per Liquipedia API v3 spec., ingest_all() skips write_parquet_to_s3 when entity list is empty., _auth_headers() must use 'Apikey' prefix (not 'Bearer')., test_auth_headers_apikey_format() (+2 more)

### Community 28 - "Kaggle Ingester"
Cohesion: 0.2
Nodes (7): KaggleBootstrapIngester, Kaggle historical CSV bootstrap ingester for CS2 analytics pipeline.  Downloads, Parse a CSV file and map rows to canonical Match objects.          Column name m, One-time historical data bootstrap from Kaggle CSV datasets.      Writes through, Tests for KaggleBootstrapIngester.csv_to_matches() score field extraction., CSV with _map_wins_team_1/_map_wins_team_2 maps to score_a/score_b., TestKaggleScoreExtraction

### Community 29 - "Weekly Rankings DAG"
Cohesion: 0.2
Nodes (9): cs2_weekly_rankings_dag(), _ingest_player_rankings(), _ingest_rankings(), Airflow DAG: cs2_weekly_rankings — sync CS2 team and player rankings weekly.  In, Return True if key exists in S3 bucket, False otherwise.      Uses head_object t, Run Liquipedia team rankings ingestion asynchronously., Run Liquipedia player rankings ingestion asynchronously., Sync CS2 team and player rankings from Liquipedia into S3. (+1 more)

### Community 30 - "Daily Matches DAG"
Cohesion: 0.2
Nodes (9): cs2_daily_matches_dag(), _ingest_faceit(), _ingest_pandascore(), Airflow DAG: cs2_daily_matches — ingest CS2 match results every 6 hours.  Ingest, Ingest CS2 match results from FACEIT and PandaScore into S3., Return True if key exists in S3 bucket, False otherwise.      Uses head_object t, Run FACEIT match ingestion asynchronously for today's date.      Calls FACEITCli, Run PandaScore match ingestion asynchronously for today's date.      Fetches rec (+1 more)

### Community 31 - "Intermediate dbt Models"
Cohesion: 0.25
Nodes (9): int_matches_unioned, FACEIT Priority Player Deduplication, int_players_unioned, Intermediate dbt Schema Tests, stg_faceit_matches, stg_faceit_players, stg_kaggle_matches, stg_pandascore_matches (+1 more)

### Community 32 - "Daily S3 Idempotency"
Cohesion: 0.25
Nodes (7): Unit tests for cs2_daily_matches DAG task logic.  Tests the S3 idempotency helpe, _s3_key_exists() returns True when head_object succeeds (key present)., _s3_key_exists() returns False when head_object raises ClientError 404., _s3_key_exists() re-raises ClientError for non-404 error codes (e.g., 403 Forbid, test_s3_key_exists_reraises_non_404_errors(), test_s3_key_exists_returns_false_on_404(), test_s3_key_exists_returns_true_on_200()

### Community 33 - "Canonical Team Tests"
Cohesion: 0.25
Nodes (5): Tests for canonical (Match, Player, Team) and per-source Pydantic v2 models.  Co, Canonical Team model tests., Team with world_ranking=None is valid., Team rejects unknown fields (extra='forbid')., TestCanonicalTeam

### Community 34 - "FACEIT Player Model"
Cohesion: 0.25
Nodes (5): FACEITPlayer, FACEIT API v4 raw Pydantic v2 models.  Source models use extra="ignore" to silen, Map FACEIT player profile to the shared canonical Player schema.          Per-ma, Raw FACEIT player profile model. Maps to canonical Player via to_canonical()., FACEITPlayer.to_canonical() returns a Player instance.

### Community 35 - "Tournament Sync DAG"
Cohesion: 0.25
Nodes (7): cs2_tournament_sync_dag(), _ingest_tournament_matches(), Airflow DAG: cs2_tournament_sync — sync active CS2 tournament match data daily., Return True if key exists in S3 bucket, False otherwise.      Uses head_object t, Run Liquipedia tournament match ingestion asynchronously.      Calls LiquipediaC, Sync active CS2 tournament match data from Liquipedia into S3., _s3_key_exists()

### Community 36 - "Slack Alerting"
Cohesion: 0.25
Nodes (6): Unit tests for Slack failure alert callback.  Tests that on_failure_callback for, on_failure_callback POSTs a Slack message containing dag_id, task_id, run_id., test_on_failure_callback_sends_slack_message(), on_failure_callback(), Shared Airflow DAG failure alert callback using Slack webhooks.  Usage in DAG de, Send a Slack alert when any task in the DAG fails.      Called automatically by

### Community 37 - "Kaggle Credential Tests"
Cohesion: 0.29
Nodes (4): Credential file must contain username and key as JSON., Credential file must be owner read/write only (chmod 600)., ~/.kaggle directory must be created if it does not exist., TestSetupKaggleCredentials

### Community 38 - "Kaggle S3 Write Tests"
Cohesion: 0.29
Nodes (3): ingest_csv_file must call write_parquet_to_s3 with MATCH_SCHEMA., S3 key must start with raw/kaggle/matches/, TestIngestCsvFile

### Community 39 - "Kaggle Download Tests"
Cohesion: 0.29
Nodes (3): download_and_ingest must call setup_kaggle_credentials with username/key., Total returned must be sum of per-file counts., TestDownloadAndIngest

### Community 40 - "Pytest Environment Fixtures"
Cohesion: 0.5
Nodes (3): dummy_env(), pytest conftest — shared fixtures and env setup for all tests.  The cs2_analytic, Fixture that patches all CS2_* env vars with dummy values for isolated tests.

### Community 42 - "DAG Bag Fixture"
Cohesion: 0.5
Nodes (3): dagbag(), pytest conftest for DAG tests — extends root conftest with Airflow-specific fixt, Load all DAGs from airflow/dags/ — use for structural tests.

### Community 43 - "Slack Smoke DAG"
Cohesion: 0.5
Nodes (3): fail_intentionally_dag(), Dev DAG — intentionally fails to smoke-test the Slack webhook alert.  Use to ver, DAG that always fails — used to verify Slack webhook alerting is live.

### Community 44 - "dbt Airflow DAG"
Cohesion: 0.5
Nodes (3): cs2_dbt_run_dag(), Airflow DAG: cs2_dbt_run — refresh Snowflake warehouse daily.  Pipeline: COPY IN, Refresh Snowflake warehouse: COPY INTO raw tables then dbt run + test.

## Ambiguous Edges - Review These
- `mart_map_meta` → `Team A Win Rate as Side Advantage Proxy`  [AMBIGUOUS]
  dbt_project/models/marts/analytics/mart_map_meta.sql · relation: rationale_for

## Knowledge Gaps
- **371 isolated node(s):** `pytest conftest — shared fixtures and env setup for all tests.  The cs2_analytic`, `Fixture that patches all CS2_* env vars with dummy values for isolated tests.`, `TDD tests for cs2_analytics.utils.s3 — S3 upload and Hive path utilities.  RED p`, `Standard faceit/matches path with single-digit month and day.`, `Double-digit month and day should not add extra padding.` (+366 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `mart_map_meta` and `Team A Win Rate as Side Advantage Proxy`?**
  _Edge tagged AMBIGUOUS (relation: rationale_for) - confidence is low._
- **Why does `Match` connect `Canonical Match Model` to `Kaggle Bootstrap Flow`, `Canonical Team Tests`, `FACEIT Ingestion Client`, `FACEIT Player Model`, `PandaScore Ingestion Client`, `Parquet Schema Tests`, `Liquipedia Domain Models`, `PandaScore Domain Models`, `FACEIT Domain Models`, `Canonical Player Models`, `Liquipedia Client`, `Kaggle Ingester`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Why does `KaggleBootstrapIngester` connect `Kaggle Ingester` to `Kaggle Bootstrap Flow`, `Canonical Team Tests`, `Kaggle Credential Tests`, `Kaggle S3 Write Tests`, `Kaggle Download Tests`, `Kaggle Instantiation Tests`, `Liquipedia Domain Models`, `PandaScore Domain Models`, `FACEIT Domain Models`, `Canonical Match Model`, `Kaggle Bootstrap Script`, `Canonical Player Models`, `Kaggle Fixture Tests`, `Kaggle CSV Edge Cases`, `Kaggle Ingester Fixtures`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `LiquipediaClient` connect `Liquipedia Client` to `Tournament Sync DAG`, `Base API Client Tests`, `Liquipedia Domain Models`, `Canonical Match Model`, `Canonical Player Models`, `Liquipedia Tournament Tests`, `Liquipedia S3 Prefix`, `Base API Client`, `Liquipedia Basic Tests`, `Liquipedia Ingestion Tests`, `Liquipedia Fetch Methods`, `Weekly Rankings DAG`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 37 inferred relationships involving `Match` (e.g. with `TestCanonicalMatch` and `TestCanonicalPlayer`) actually correct?**
  _`Match` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `LiquipediaClient` (e.g. with `BaseAPIClient` and `Match`) actually correct?**
  _`LiquipediaClient` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `PandaScoreClient` (e.g. with `TestPandaScoreClientAttributes` and `TestGetRecentMatches`) actually correct?**
  _`PandaScoreClient` has 25 INFERRED edges - model-reasoned connections that need verification._