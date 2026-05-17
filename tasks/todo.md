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
