# CS2 Analytics

Warehouse-first analytics for modern Counter-Strike 2. The project ingests CS API
data, models it with dbt in Snowflake, trains an Upset Tracker model, and serves a
Streamlit dashboard for product-facing analysis.

## What It Does

The v1 product has three analytics tracks:

- **Upset Tracker:** ranks matches by model-estimated upset probability using
  CS API match and ranking features.
- **Hidden Gem Scout:** finds tier 2/3/4 players whose recent form clears
  benchmark thresholds from the tier above them.
- **Choke/Clutch Profile:** profiles team-level pressure metrics from cached
  HLTV round history, with explicit sample-quality and unavailable-metric flags.

The dashboard reads local Parquet snapshots of marts plus versioned ML artifacts,
so page refreshes do not query Snowflake directly.

## Architecture

```text
CS API
  -> scripts/bootstrap_csapi.py
  -> raw Parquet in S3
  -> Snowflake RAW tables
  -> dbt staging/intermediate/marts
  -> ML artifacts in ml/
  -> dashboard snapshots in dashboard/snapshots/
  -> Streamlit dashboard
```

Snowflake and dbt are the source of truth. Python scripts handle ingestion,
training, prediction explainability, and dashboard snapshot export.

## Main Directories

- `src/cs2_analytics/`: ingestion clients, typed models, config, and utilities.
- `scripts/bootstrap_csapi.py`: CS API ingestion entrypoint.
- `dbt_project/`: Snowflake models, tests, sources, and setup SQL.
- `ml/`: Upset Tracker training, prediction helpers, model card, and artifacts.
- `dashboard/`: Streamlit app, mart snapshot export command, and dashboard helpers.
- `airflow/`: local Airflow DAGs for scheduled ingestion and dbt refreshes.
- `tests/`: unit, dbt-SQL, DAG, ML, dashboard, and optional browser smoke tests.
- `tasks/`: working notes, reviews, and lessons captured during implementation.

## Requirements

- Python `>=3.12`
- `uv`
- Snowflake account and key-pair auth for warehouse/dbt work
- S3-compatible bucket credentials for raw CS API output
- Docker, if running local Airflow
- GitHub CLI, if publishing branches/PRs from the command line

## Setup

Install dependencies:

```bash
uv sync
```

Create a local `.env` file with the credentials needed by ingestion, dbt,
Snowflake, and S3:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if using temporary AWS credentials
- `CS2_AWS_REGION`
- `CS2_AWS_S3_BUCKET`
- `CS2_FACEIT_API_KEY`
- `CS2_PANDASCORE_API_KEY`
- `CS2_LIQUIPEDIA_API_KEY` if using Liquipedia enrichment
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_PRIVATE_KEY_PATH`

dbt reads exported shell environment variables; it does not load `.env` by
itself, so export the file before running ingestion, dbt, ML, or snapshot
commands:

```bash
set -a; source .env; set +a
```

Do not commit `.env`, private keys, Snowflake credentials, or raw secrets.

Verify the local project after setup:

```bash
uv run ruff check .
uv run pytest
```

To enable automated dashboard refreshes on GitHub:

1. Add the GitHub repository secrets listed in the GitHub Actions Refresh
   section.
2. Run the `Dashboard Refresh` workflow manually with the `daily` profile.
3. Confirm the run succeeds and commits any changed files in
   `dashboard/snapshots/` and weekly ML artifact paths.
4. Deploy or refresh the Streamlit app from `main`.

## Daily Operations

Run this once per day after exporting `.env`:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile daily
uv run dbt run --select mart_upset_features mart_hidden_gems --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --select mart_upset_features mart_hidden_gems --project-dir dbt_project --profiles-dir dbt_project
uv run python -m dashboard.export_snapshots --mart mart_upset_features --mart mart_hidden_gems
```

The daily profile is bounded for frequent use. It refreshes current rankings,
recent matches, and match-anchored player stats with small default page caps.

## Weekly Operations

Run this once per week after exporting `.env`:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile daily
uv run dbt run --select +mart_upset_features +mart_hidden_gems +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --select +mart_upset_features +mart_hidden_gems +mart_choke_profile --project-dir dbt_project --profiles-dir dbt_project
uv run python -m ml.train
uv run python -m dashboard.export_snapshots --mart mart_upset_features --mart mart_hidden_gems --mart mart_choke_profile
```

The hosted weekly dashboard refresh replaces the Monday daily run. It uses the
bounded CS API `daily` profile for current rankings/matches, then adds the
weekly-only HLTV Choke Profile load, model retraining, and three-mart snapshot
export. Do not schedule the deep CS API `weekly` profile in GitHub Actions.

## Backfills

Backfill is manual-only and requires explicit opt-in:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_csapi.py --profile backfill --allow-backfill
```

Useful controls:

- `CS2_CSAPI_BACKFILL_MATCH_OFFSET`
- `CS2_CSAPI_BACKFILL_MAX_MATCHES`
- `CS2_CSAPI_BACKFILL_MATCH_PAGES`
- `CS2_CSAPI_BACKFILL_PLAYER_STAT_MATCH_LIMIT`

Profile defaults can also be overridden globally, for example
`CS2_CSAPI_MATCH_PAGES=5`, or per profile, for example
`CS2_CSAPI_DAILY_MATCH_PAGES=2`.

## HLTV Round History

Choke Profile uses cached JSON exports from an optional browser-based HLTV
mapstats helper. This source is best-effort and unofficial, so keep fetches
small, cached, and slow. Do not use proxy rotation.

Install the optional browser dependencies into a gitignored cache directory when
you need to fetch new map stats:

```bash
npm install --prefix data/hltv_cache/node \
  puppeteer puppeteer-extra puppeteer-extra-plugin-stealth
```

Create a newline-delimited mapstats ID file, then fetch JSON with a delay:

```bash
mkdir -p data/hltv_cache
printf "49968\n" > data/hltv_cache/mapstats_ids.txt
PUPPETEER_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra/dist/index.cjs.js \
STEALTH_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra-plugin-stealth/index.js \
CHROME_PATH=/usr/bin/chromium \
node tools/fetch_hltv_mapstats.mjs \
  --ids-file data/hltv_cache/mapstats_ids.txt \
  --output-dir data/hltv_cache/map_stats \
  --delay-ms 5000 \
  --headless false
```

Convert cached JSON to compact Parquet and upload it to the existing raw S3
layout:

```bash
set -a; source .env; set +a
uv run python scripts/bootstrap_hltv_round_history.py \
  --input-dir data/hltv_cache/map_stats \
  --ingest-date "$(date +%F)" \
  --upload-s3 \
  --batch-id "hltv_maps_001"
```

The repository stores only parsed round-history rows. Raw helper caches live
under `data/hltv_cache/`, which is ignored by git. Use a unique `--batch-id` for
each 100-300 map chunk so raw S3 files are append-only and reruns skip existing
batch objects instead of overwriting them.

### Parallel VPS Scraping

For large backfills (16k+ matches) a single local browser is too slow and one
Cloudflare timeout can stall the whole run. The repository scales this out
across cheap Hetzner CPX VPSs (one per region) that each run an isolated Chrome
with its own warmed `cf_clearance` cookie.

Architecture:

- Shard `data/hltv_cache/match_ids.txt` into N shuffled chunks so each VPS
  gets a mix of events instead of hammering one event from one IP.
- Each VPS runs Xvfb + Google Chrome + `tools/fetch_hltv_matches.mjs`.
- The scraper connects to Chrome via CDP when `CHROME_REMOTE_URL` is set,
  instead of letting puppeteer spawn its own Chrome. This is required because
  Cloudflare binds `cf_clearance` to the real Chrome fingerprint, and a
  freshly puppeteer-launched Chrome triggers a re-challenge that stealth
  cannot auto-solve on `/stats/...` paths.
- Cloudflare's managed challenge is solved once per VPS through a VNC session.
  The persisted `--user-data-dir` keeps the cookie alive for the full run.
- Output filenames are keyed by `{matchId}.json`, so rsync'ing results back
  from all VPSs is conflict-free.

VPS bootstrap (Ubuntu 24.04, run once per VPS):

```bash
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  curl ca-certificates tmux rsync xvfb fluxbox x11vnc sqlite3 \
  fonts-liberation libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2t64
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs

# Google Chrome from Google's apt repo. Ubuntu 24.04's `chromium` package is a
# snap stub that does not install a binary at /usr/bin/chromium.
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
  | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
  > /etc/apt/sources.list.d/google-chrome.list
DEBIAN_FRONTEND=noninteractive apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq google-chrome-stable
```

Shard the match IDs locally and rsync code + vendored `node_modules` to each
VPS:

```bash
shuf data/hltv_cache/match_ids.txt > /tmp/shuffled.txt
split -n l/4 -d /tmp/shuffled.txt data/hltv_cache/match_ids.part_

# Per VPS — repeat with each IP and the matching part_NN
ssh -i KEY root@VPS_IP 'mkdir -p /root/cs2'
rsync -avz -e "ssh -i KEY" tools/ root@VPS_IP:/root/cs2/tools/
rsync -avz -e "ssh -i KEY" data/hltv_cache/node/node_modules/ root@VPS_IP:/root/cs2/node_modules/
rsync -avz -e "ssh -i KEY" data/hltv_cache/match_ids.part_NN root@VPS_IP:/root/cs2/match_ids.txt
```

Cloudflare warmup (one-time per VPS):

```bash
# On the VPS — start virtual display, window manager, VNC server bound to
# localhost only.
tmux new -ds desktop 'Xvfb :99 -screen 0 1366x768x24'
tmux new -ds wm     'DISPLAY=:99 fluxbox'
tmux new -ds vnc    'x11vnc -display :99 -listen localhost -nopw -forever -shared'

# Launch Chrome on the display pointed at a /stats/ URL that the scraper will
# need. This is the path that re-challenges if not pre-warmed.
tmux new -ds chrome 'DISPLAY=:99 google-chrome \
  --no-sandbox --no-first-run --no-default-browser-check \
  --disable-blink-features=AutomationControlled \
  --disable-dev-shm-usage \
  --user-data-dir=/root/cs2/user_data \
  --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 \
  --window-size=1366,768 \
  https://www.hltv.org/stats/matches/mapstatsid/213684/-'
```

Then from your local machine, tunnel VNC and connect:

```bash
ssh -i KEY -L 5901:localhost:5900 -N root@VPS_IP &
vncviewer localhost:5901
```

In the VNC window, click through the Cloudflare challenge until the HLTV
stats page loads. Close the VNC viewer only — Chrome must keep running. The
`cf_clearance` cookie now lives in `/root/cs2/user_data` and is valid for
that VPS's IP for ~30 days.

Launch the scraper attached to the warmed Chrome:

```bash
tmux new -ds scrape 'stdbuf -oL -eL env \
  CHROME_REMOTE_URL=http://localhost:9222 \
  PUPPETEER_MODULE_PATH=/root/cs2/node_modules/puppeteer-extra/dist/index.cjs.js \
  STEALTH_MODULE_PATH=/root/cs2/node_modules/puppeteer-extra-plugin-stealth/index.js \
  node /root/cs2/tools/fetch_hltv_matches.mjs \
    --ids-file /root/cs2/match_ids.txt \
    --output-dir /root/cs2/matches \
    --user-data-dir /root/cs2/user_data \
    --delay-ms 5000 --headless true 2>&1 | tee /root/cs2/run.log'
```

Collect results when the runs finish:

```bash
mkdir -p data/hltv_cache/matches
for ip in IP1 IP2 IP3 IP4; do
  rsync -avz -e "ssh -i KEY" root@$ip:/root/cs2/matches/ data/hltv_cache/matches/
done
```

Troubleshooting gotchas encountered during initial setup:

- Ubuntu 24.04's `chromium` apt package is a snap stub and does not provide
  `/usr/bin/chromium`. Use `google-chrome-stable` from Google's deb repo.
- Chrome silently exits on minimal Hetzner images without
  `--disable-dev-shm-usage` because `/dev/shm` is too small for Chrome IPC.
- `--disable-gpu` combined with `--disable-software-rasterizer` makes Chrome
  render to an invisible offscreen surface. Drop both flags if you need
  Chrome visible in VNC.
- Fluxbox (or another WM) must be running on display `:99` *before* Chrome
  launches, or Chrome's window will not appear in VNC.
- `puppeteer-extra-plugin-stealth` alone is not enough for HLTV `/stats/`
  paths. Cloudflare detects the puppeteer-launched Chrome and refuses to
  clear the challenge even with a valid `cf_clearance` cookie. The scraper
  works around this by connecting to a manually-launched Chrome via CDP
  when `CHROME_REMOTE_URL` is set.
- `cf_clearance` minted by visiting only the homepage is not sufficient. The
  warmup VNC visit must navigate to a `/stats/matches/mapstatsid/{id}/-` URL
  at least once before the scraper can fetch mapstats pages.
- Node's stdout is block-buffered when piped to `tee`, so log lines do not
  appear until the buffer fills. Prefix the command with `stdbuf -oL -eL` to
  force line buffering.
- VNC server, fluxbox, x11vnc, and Chrome are kept in separate `tmux`
  sessions (`desktop`, `wm`, `vnc`, `chrome`, `scrape`) so each can be
  restarted independently if it crashes.

Expected throughput is about one match every ~20 seconds (homepage + match
page + ~3 mapstats pages × 5s delay), so a 4-VPS run of 16k matches takes
roughly 22 hours wall-clock.

## Dashboard

Export dashboard snapshots after dbt finishes:

```bash
set -a; source .env; set +a
uv run python -m dashboard.export_snapshots
```

Run Streamlit locally:

```bash
uv run streamlit run dashboard/Home.py
```

Open the URL Streamlit prints, usually:

```text
http://localhost:8501
```

The dashboard expects:

- `dashboard/snapshots/mart_upset_features.parquet`
- `dashboard/snapshots/mart_hidden_gems.parquet`
- `dashboard/snapshots/mart_choke_profile.parquet`
- `ml/models/upset_tracker_v1.0.joblib`
- `ml/evaluation/decision_threshold.txt`
- `ml/evaluation/metrics.json`
- `ml/MODEL_CARD.md`

## Hosting For Free

Use Streamlit Community Cloud for the simplest free deployment:

- Deployed app: https://cs2-analytics.streamlit.app/

1. Push this repository to GitHub.
2. Deploy a new Streamlit app from the repo.
3. Set the entrypoint to `dashboard/Home.py`.
4. Commit dashboard snapshot Parquet files if the public app should avoid live
   Snowflake access.
5. If the app needs live Snowflake access, add credentials through Streamlit
   secrets instead of committing them.

GitHub Student Developer Pack credits can help with alternatives like
DigitalOcean or Azure, but Streamlit Community Cloud is the lowest-maintenance
fit for this app.

## GitHub Actions Refresh

The repository includes `.github/workflows/dashboard-refresh.yml` to keep hosted
dashboard snapshots fresh without running a 24/7 server.

GitHub only runs scheduled workflows from the default branch, so merge this
workflow to `main` before relying on the daily and weekly timers.

After the pull request is merged:

1. Go to GitHub repo Settings, then Secrets and variables, then Actions.
2. Add each required value as a repository secret.
3. Go to the Actions tab and select `Dashboard Refresh`.
4. Click Run workflow, choose `daily`, and run it from `main`.
5. Open the workflow logs if it fails. Missing or misspelled secrets usually
   show up during the ingest, Snowflake key, dbt, or S3 steps.
6. After the first successful daily run, let the scheduled daily and weekly
   runs take over.

You can also start the first run from the GitHub CLI:

```bash
gh workflow run dashboard-refresh.yml --ref main -f profile=daily
```

Schedules are in UTC:

- Daily refresh: `17 10 * * 0,2-6` for Sunday and Tuesday-Saturday
- Weekly refresh: `43 11 * * 1` for Monday

You can also run it manually from GitHub Actions with the `daily` or `weekly`
profile. The daily run ingests recent CS API data, rebuilds/test the dashboard
marts, exports snapshots, and commits changed snapshots. The weekly run replaces
the Monday daily run, still uses the bounded CS API `daily` ingest window, and
adds HLTV raw loading, `mart_choke_profile`, Upset Tracker retraining, and the
Choke snapshot export.

Each hosted refresh copies only the current S3 date partition into Snowflake,
for example `year=2026/month=05/day=12/`, instead of scanning every historical
raw file under the source prefix.

Add these repository secrets in GitHub before enabling the workflow:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN` if using temporary AWS credentials
- `CS2_AWS_REGION`
- `CS2_AWS_S3_BUCKET`
- `CS2_FACEIT_API_KEY`
- `CS2_PANDASCORE_API_KEY`
- `CS2_LIQUIPEDIA_API_KEY` if using Liquipedia enrichment
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_PRIVATE_KEY`

`SNOWFLAKE_PRIVATE_KEY` should contain the full private key text. Escaped
newlines (`\n`) and normal multi-line secret values are both handled by the
workflow.

## Airflow

Start local Airflow:

```bash
docker compose --env-file .env -f airflow/docker-compose.yml up airflow-init
docker compose --env-file .env -f airflow/docker-compose.yml up -d
```

The daily DAG runs the `daily` CS API profile. The weekly rankings DAG runs the
`weekly` profile for deeper warehouse history. GitHub Actions intentionally does
not use that deep weekly CS API profile for hosted dashboard refreshes. The
`backfill` profile has no scheduled trigger by default.

## Validation

Run fast checks:

```bash
uv run ruff check .
uv run pytest
```

Run the optional browser smoke test against a local dashboard server:

```bash
uv run streamlit run dashboard/Home.py
CS2_DASHBOARD_BASE_URL=http://localhost:8501 uv run pytest tests/test_dashboard_browser.py -q
```

Run dbt validation against Snowflake:

```bash
set -a; source .env; set +a
uv run dbt run --project-dir dbt_project --profiles-dir dbt_project
uv run dbt test --project-dir dbt_project --profiles-dir dbt_project
```

## Current Limitations

- Choke/Clutch exact lead-blown, halftime comeback, overtime, and close-map
  metrics are team/map pressure signals from `hltv_unofficial` round history.
  Player clutch, bracket, and elimination-match metrics remain unavailable until
  a trustworthy event/bracket source is persisted with aligned team identities.
- Hosted dashboard pages read committed Parquet snapshots. The GitHub Actions
  refresh exports those snapshots on schedule, but Streamlit still serves the
  latest committed files rather than querying Snowflake live on page load.
- Upset Tracker predictions are watchlist signals, not certainties.
