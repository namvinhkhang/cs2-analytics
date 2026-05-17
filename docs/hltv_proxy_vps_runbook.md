# HLTV Scraper — 4-VPS IPRoyal Proxy Runbook

Deploy the HLTV match scraper across 4 VPS, each egressing through its own
dedicated IPRoyal **US ISP static-residential** IP, with a self-pruning
`match_ids.txt` queue.

## Why the proxy

HLTV/Cloudflare 403s the bare VPS datacenter IPs. Each VPS now exits through a
dedicated residential IP. `cf_clearance` is IP-bound, so each VPS must hold
**one constant IP** — these are static (non-rotating) ISP IPs, picked for that
reason. Chrome's `--proxy-server` flag carries only `host:port`; the IPRoyal
account credentials are applied in code via `page.authenticate()`
(`tools/lib/hltv_browser.mjs`), gated by `CS2_PROXY_USERNAME` /
`CS2_PROXY_PASSWORD` (no-op when unset).

## VPS → dedicated exit IP

Assigned for ASN/subnet diversity (don't reshuffle without reason):

| VPS | Exit IP | ASN / location |
|-----|-----------------|--------------------------------|
| VPS-1 | `50.114.173.114` | AS3561 CenturyLink/Lumen, NYC — only non-RCN |
| VPS-2 | `192.228.122.89` | AS6079 RCN, Milford DE |
| VPS-3 | `104.234.88.177` | AS6079 RCN, Leesburg VA |
| VPS-4 | `104.234.82.12` | AS6079 RCN, Leesburg VA |

All use `host = <exit IP>`, `port = 12323`, same account user/pass.

## Scraper queue behaviour (`--prune-ids true`)

`match_ids.txt` is a self-draining queue. Per ID outcome:

| Outcome | Action |
|---|---|
| fetched OK | **prune** (remove from `match_ids.txt`) |
| `cached` (json already exists) | **prune** |
| `500` HLTV soft-error (non-existent match) | **prune** — expected, not a failure |
| `not_completed` (match not finished yet) | keep — retried next run |
| `403` / `429` (rate-limit / cf_clearance dead) | keep + **stop run** + Slack alert |
| nav timeout / `ERR_*` / other transient | keep — retried next run |

Rewrites are atomic (`tmp`+`rename`): killing the run mid-write cannot corrupt
the queue; a restart resumes from the last good prune. `403/429` is the only
rate-limit stop — the legacy "5 errors in a row" stop is disabled here via
`--max-consecutive-failures 0` so a run of non-existent IDs doesn't halt it.

> Without `--prune-ids` (Airflow / local runs) the ids file is left untouched
> and the consecutive-failure backstop keeps its default.

## Prerequisites (operator's machine)

```bash
export CS2_PROXY_USERNAME=14a4304991e86
export CS2_PROXY_PASSWORD=<iproyal-password>      # never commit this
export SSH_KEY=~/.ssh/id_ed25519_hetzner          # default if unset
cd <repo root>
```

## Per-VPS procedure

Do **VPS-1 fully end-to-end first**, confirm scrapes, then repeat for 2/3/4.

### 1. Setup (rsync code + display stack + Chrome via proxy + verify)

```bash
scripts/deploy_hltv_proxy_vps.sh setup <vps_ssh_ip> <exit_ip>
# e.g. VPS-1:
scripts/deploy_hltv_proxy_vps.sh setup 5.223.65.252 50.114.173.114
```

Pass criteria in the output:
- `proxy curl:` prints the **same IP** you passed.
- `code: page.authenticate present` and `code: prune-ids present`.
- `Xvfb :99 ready`, `x11vnc on 5900`, `Chrome CDP up`.
- `BROWSER_EXIT_IP=<exit_ip>` matches `EXPECTED BROWSER_EXIT_IP`.

If `BROWSER_EXIT_IP` ≠ expected, **stop** — the browser isn't using the proxy;
do not warm up (clearance would bind to the wrong IP).

### 2. Warm Cloudflare (human, in VNC)

The setup output prints the exact commands. Summary:

```bash
pkill -f '5901:localhost:5900' 2>/dev/null
ssh -i "$SSH_KEY" -L 5901:localhost:5900 -N root@<vps_ssh_ip> &
sleep 1; vncviewer localhost:5901
```

In VNC: solve the Cloudflare challenge until the HLTV **stats table renders**
(enter the proxy user/pass if a proxy auth popup appears). Close the VNC
viewer **only** — leave Chrome running. `cf_clearance` is now bound to the
dedicated IP.

### 3. Launch (offline-prune cached ids + start self-pruning scraper)

```bash
scripts/deploy_hltv_proxy_vps.sh launch <vps_ssh_ip> <exit_ip>
```

Prints `pre-prune: <before> -> <after> ids` and `scrape RUNNING`.

### 4. Watch

```bash
ssh -i "$SSH_KEY" root@<vps_ssh_ip> 'tail -f /root/cs2/run.log'
```

Healthy log: `fetched …` lines appearing, `gone … 500 non-existent` passing
through without stopping, `match_ids.txt` shrinking. Bad: `stopping on
rate-limit/forbidden (403)` → cf_clearance died; redo step 2 (re-warm) and
re-launch — pruned ids are not re-walked.

## Notes / caveats

- **Singapore→US latency**: some boxes are physically far from the US exit IP;
  `--nav-timeout-ms 90000` is set for this. Bump higher if you see
  `net::ERR_TIMED_OUT` (that's latency, not a proxy fault).
- **Security**: the IPRoyal credentials are live secrets. Keep them only in
  shell env / VPS `.env` (gitignored). Rotate the IPRoyal password after
  rollout if it was ever shared in plaintext.
- **No IP whitelisting on IPRoyal** for this account format — auth is by
  credentials; whitelisting is unnecessary and would not pin the IP.
- Re-running `setup` is safe and idempotent (it re-archives the profile and
  rebuilds the tmux stack); you must re-warm Cloudflare after any `setup`.
