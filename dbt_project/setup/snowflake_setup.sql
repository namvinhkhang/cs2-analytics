-- Snowflake setup for CS2 Analytics warehouse
-- Run this as ACCOUNTADMIN in a Snowflake worksheet
-- Replace <placeholders> with your actual values
-- All DDL is idempotent (IF NOT EXISTS / CREATE OR REPLACE)

-- =============================================================================
-- 1. Database and schemas
-- =============================================================================
CREATE DATABASE IF NOT EXISTS CS2_ANALYTICS;
USE DATABASE CS2_ANALYTICS;

-- RAW: Parquet data loaded from S3 via COPY INTO — never modified by dbt
CREATE SCHEMA IF NOT EXISTS RAW;
-- STAGING: dbt views that clean and rename raw columns
CREATE SCHEMA IF NOT EXISTS STAGING;
-- MARTS: dbt tables aggregated for BI and ML consumption
CREATE SCHEMA IF NOT EXISTS MARTS;

-- =============================================================================
-- 2. Warehouse (X-SMALL to conserve free trial credit)
-- =============================================================================
-- AUTO_SUSPEND = 60s and AUTO_RESUME = TRUE prevent idle credit burn
-- Cost note: Snowflake $400 free trial credit — always suspend when not in use
CREATE WAREHOUSE IF NOT EXISTS CS2_WH
  WAREHOUSE_SIZE = 'X-SMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- =============================================================================
-- 3. Storage integration (S3 access via IAM role delegation)
-- =============================================================================
-- CRITICAL: After creation, run DESC INTEGRATION cs2_s3_int to get:
--   STORAGE_AWS_IAM_USER_ARN  — add to AWS IAM role trust policy Principal
--   STORAGE_AWS_EXTERNAL_ID   — add to AWS IAM role trust policy Condition
-- Then create the IAM role trust policy in AWS Console with those values.
-- See: https://docs.snowflake.com/en/user-guide/data-load-s3-config-storage-integration
CREATE STORAGE INTEGRATION IF NOT EXISTS cs2_s3_int
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::850610451085:role/cs2-snowflake-s3-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://cs2-analytics-850610451085-us-east-2-an/raw/');

-- Reveals Snowflake IAM user ARN + external ID for AWS trust policy
DESC INTEGRATION cs2_s3_int;

-- =============================================================================
-- 4. External stage pointing at S3 raw/ prefix
-- =============================================================================
USE SCHEMA CS2_ANALYTICS.RAW;

-- Stage reads Hive-partitioned Parquet files written by the ingestion pipeline:
-- raw/{source}/{entity_type}/year={y}/month={mm}/day={dd}/data.parquet
CREATE OR REPLACE STAGE cs2_raw_stage
  STORAGE_INTEGRATION = cs2_s3_int
  URL = 's3://cs2-analytics-850610451085-us-east-2-an/raw/'
  FILE_FORMAT = (TYPE = PARQUET);

-- =============================================================================
-- 5. Raw tables — typed schema for MATCH_BY_COLUMN_NAME COPY INTO
-- =============================================================================
-- Using typed columns instead of VARIANT avoids $1:field::type syntax in
-- staging models and makes column-level lineage visible in dbt docs.
-- COPY INTO uses MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE to align Parquet
-- column names with table column definitions.

CREATE TABLE IF NOT EXISTS RAW.raw_faceit_matches (
  match_id    VARCHAR,
  source      VARCHAR,
  team_a_id   VARCHAR,
  team_b_id   VARCHAR,
  winner_id   VARCHAR,
  played_at   VARCHAR,
  map_name    VARCHAR,
  score_a     INTEGER,
  score_b     INTEGER,
  is_overtime BOOLEAN,
  team_a_ranking INTEGER,
  team_b_ranking INTEGER
);

CREATE TABLE IF NOT EXISTS RAW.raw_pandascore_matches (
  match_id    VARCHAR,
  source      VARCHAR,
  team_a_id   VARCHAR,
  team_b_id   VARCHAR,
  winner_id   VARCHAR,
  played_at   VARCHAR,
  map_name    VARCHAR,
  score_a     INTEGER,
  score_b     INTEGER,
  is_overtime BOOLEAN,
  team_a_ranking INTEGER,
  team_b_ranking INTEGER
);

CREATE TABLE IF NOT EXISTS RAW.raw_csapi_matches (
  match_id    VARCHAR,
  source      VARCHAR,
  team_a_id   VARCHAR,
  team_b_id   VARCHAR,
  winner_id   VARCHAR,
  played_at   VARCHAR,
  map_name    VARCHAR,
  score_a     INTEGER,
  score_b     INTEGER,
  is_overtime BOOLEAN,
  team_a_ranking INTEGER,
  team_b_ranking INTEGER
);

CREATE TABLE IF NOT EXISTS RAW.raw_csapi_team_rankings (
  team_id       VARCHAR,
  source        VARCHAR,
  name          VARCHAR,
  region        VARCHAR,
  world_ranking INTEGER,
  vrs_points    INTEGER,
  rank_diff     INTEGER,
  points_diff   INTEGER,
  ranking_date  VARCHAR,
  ingested_at   VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_csapi_player_stats (
  player_id      VARCHAR,
  source         VARCHAR,
  display_name   VARCHAR,
  team_id        VARCHAR,
  team_name      VARCHAR,
  nationality    VARCHAR,
  kills          FLOAT,
  deaths         FLOAT,
  adr            FLOAT,
  kd_ratio       FLOAT,
  kast           FLOAT,
  rating         FLOAT,
  swing          FLOAT,
  matches_played INTEGER,
  elo            INTEGER,
  match_id       VARCHAR,
  recorded_at    VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_valve_team_regions (
  snapshot_date        VARCHAR,
  team_name            VARCHAR,
  normalized_team_name VARCHAR,
  region               VARCHAR,
  regional_rank        INTEGER,
  global_rank          INTEGER,
  points               INTEGER,
  roster               VARCHAR,
  detail_path          VARCHAR,
  source               VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_hltv_round_history (
  source            VARCHAR,
  map_stats_id      VARCHAR,
  match_id          VARCHAR,
  event_id          VARCHAR,
  event_name        VARCHAR,
  map_name          VARCHAR,
  played_at         VARCHAR,
  round_number      INTEGER,
  t_team_id         VARCHAR,
  t_team_name       VARCHAR,
  ct_team_id        VARCHAR,
  ct_team_name      VARCHAR,
  winner_side       VARCHAR,
  winner_team_id    VARCHAR,
  winner_team_name  VARCHAR,
  team1_id          VARCHAR,
  team1_name        VARCHAR,
  team2_id          VARCHAR,
  team2_name        VARCHAR,
  score_team1_after INTEGER,
  score_team2_after INTEGER,
  reported_score    VARCHAR,
  round_outcome     VARCHAR,
  is_overtime       BOOLEAN,
  ingested_at       VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_faceit_players (
  player_id    VARCHAR,
  source       VARCHAR,
  display_name VARCHAR,
  team_id      VARCHAR,
  nationality  VARCHAR,
  kills        INTEGER,
  deaths       INTEGER,
  adr          FLOAT,
  kd_ratio     FLOAT,
  kast         FLOAT,
  elo          INTEGER,
  match_id     VARCHAR,
  recorded_at  VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_pandascore_players (
  player_id    VARCHAR,
  source       VARCHAR,
  display_name VARCHAR,
  team_id      VARCHAR,
  nationality  VARCHAR,
  kills        INTEGER,
  deaths       INTEGER,
  adr          FLOAT,
  kd_ratio     FLOAT,
  kast         FLOAT,
  elo          INTEGER,
  match_id     VARCHAR,
  recorded_at  VARCHAR
);

CREATE TABLE IF NOT EXISTS RAW.raw_liquipedia_teams (
  team_id       VARCHAR,
  source        VARCHAR,
  name          VARCHAR,
  region        VARCHAR,
  world_ranking INTEGER,
  ingested_at   VARCHAR
);

-- =============================================================================
-- 6. Service user and TRANSFORMER role for dbt (key-pair auth)
-- =============================================================================
-- Password auth was deprecated for service accounts November 2025 (Snowflake MFA rollout).
-- This project uses RSA key-pair authentication for both dbt and Airflow connections.
--
-- Generate RSA key pair (run locally — never commit private key):
--   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
--   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

CREATE ROLE IF NOT EXISTS TRANSFORMER;

-- Database and schema access
GRANT USAGE ON DATABASE CS2_ANALYTICS TO ROLE TRANSFORMER;
GRANT CREATE SCHEMA ON DATABASE CS2_ANALYTICS TO ROLE TRANSFORMER;
GRANT USAGE ON SCHEMA CS2_ANALYTICS.RAW TO ROLE TRANSFORMER;
GRANT USAGE ON SCHEMA CS2_ANALYTICS.STAGING TO ROLE TRANSFORMER;
GRANT USAGE ON SCHEMA CS2_ANALYTICS.MARTS TO ROLE TRANSFORMER;

-- Read from raw tables (dbt staging models SELECT from these)
GRANT SELECT ON ALL TABLES IN SCHEMA CS2_ANALYTICS.RAW TO ROLE TRANSFORMER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA CS2_ANALYTICS.RAW TO ROLE TRANSFORMER;

-- Load controlled raw snapshots from S3 during scheduled dashboard refreshes
GRANT USAGE ON STAGE CS2_ANALYTICS.RAW.cs2_raw_stage TO ROLE TRANSFORMER;
GRANT INSERT ON TABLE CS2_ANALYTICS.RAW.raw_valve_team_regions TO ROLE TRANSFORMER;
GRANT INSERT ON TABLE CS2_ANALYTICS.RAW.raw_hltv_round_history TO ROLE TRANSFORMER;

-- Write to staging and marts (dbt creates views and tables here)
GRANT CREATE VIEW ON SCHEMA CS2_ANALYTICS.STAGING TO ROLE TRANSFORMER;
GRANT CREATE TABLE ON SCHEMA CS2_ANALYTICS.STAGING TO ROLE TRANSFORMER;
GRANT CREATE VIEW ON SCHEMA CS2_ANALYTICS.MARTS TO ROLE TRANSFORMER;
GRANT CREATE TABLE ON SCHEMA CS2_ANALYTICS.MARTS TO ROLE TRANSFORMER;

-- Warehouse usage
GRANT USAGE ON WAREHOUSE CS2_WH TO ROLE TRANSFORMER;

-- Create service user (uncomment for non-personal-account setup)
-- CREATE USER IF NOT EXISTS cs2_service_user
--   DEFAULT_ROLE = TRANSFORMER
--   DEFAULT_WAREHOUSE = CS2_WH;
--
-- Register RSA public key (paste content without -----BEGIN/END PUBLIC KEY----- headers):
-- ALTER USER cs2_service_user SET RSA_PUBLIC_KEY='<paste_public_key_content_without_headers>';
--
-- GRANT ROLE TRANSFORMER TO USER cs2_service_user;

-- For development on a personal Snowflake account, grant TRANSFORMER to your user instead:
-- GRANT ROLE TRANSFORMER TO USER <your_username>;

-- =============================================================================
-- 7. COPY INTO commands (executed by cs2_dbt_run Airflow DAG, not manually)
-- =============================================================================
-- These are included here for reference and manual re-loading only.
-- The cs2_dbt_run DAG runs these programmatically via snowflake-connector-python.
-- PURGE = FALSE ensures raw S3 data is never deleted after loading.
/*
COPY INTO CS2_ANALYTICS.RAW.raw_faceit_matches
  FROM @cs2_raw_stage/faceit/matches/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_pandascore_matches
  FROM @cs2_raw_stage/pandascore/matches/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_csapi_matches
  FROM @cs2_raw_stage/csapi/matches/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_csapi_team_rankings
  FROM @cs2_raw_stage/csapi/team_rankings/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_csapi_player_stats
  FROM @cs2_raw_stage/csapi/player_stats/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_valve_team_regions
  FROM @cs2_raw_stage/valve/team_regions/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_faceit_players
  FROM @cs2_raw_stage/faceit/players/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_pandascore_players
  FROM @cs2_raw_stage/pandascore/players/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;

COPY INTO CS2_ANALYTICS.RAW.raw_liquipedia_teams
  FROM @cs2_raw_stage/liquipedia/teams/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE
  PURGE = FALSE;
*/
