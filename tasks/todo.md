# Fix HLTV VPS Setup Recovery

- [x] Capture root cause for `FATAL: Xvfb :99 down`
- [x] Add regression coverage for stale tmux display-session recovery
- [x] Update `scripts/deploy_hltv_proxy_vps.sh` to restart unhealthy service sessions
- [x] Verify locally and rerun setup against `5.78.200.169`

## Review

- Root cause: the VPS had a stale `desktop` tmux session with no running
  `Xvfb` process/socket, so `tmux has-session` was a false health signal.
  Retry also exposed stale browser deps on `/root/cs2/node_modules` and a
  too-short Chrome CDP readiness wait.
- Verification: `uv run pytest tests/test_deploy_hltv_proxy_vps.py`,
  `bash -n scripts/deploy_hltv_proxy_vps.sh`, and setup against
  `5.78.200.169` all completed; setup printed
  `BROWSER_EXIT_IP=104.234.88.177`.

# Fix Fresh uv Ruff Setup

- [x] Reproduce fresh-environment `uv run ruff` failure
- [x] Add regression coverage for documented uv dev commands
- [x] Consolidate dev dependencies so fresh clones install command-line tools
- [x] Verify lint/test commands

## Review

- Root cause: `ruff` and `pytest` were declared only under the optional
  `dev` extra, while `uv run ruff check .` on a fresh clone uses the default
  uv dependency group and therefore did not install the `ruff` executable.
- Fix: consolidated dev-only tooling into `[dependency-groups].dev`, refreshed
  `uv.lock`, and added metadata coverage so documented validation tools stay
  available to fresh clones.
- Verification: reproduced the original failure with a temporary
  `UV_PROJECT_ENVIRONMENT`, verified the fresh environment now spawns
  `ruff 0.15.6`, then ran `uv run ruff check .` and `uv run pytest`.
