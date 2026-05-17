#!/usr/bin/env bash
# Deploy / operate one HLTV-scraper VPS behind its dedicated IPRoyal ISP IP.
#
# Two phases (a human must do the Cloudflare warmup between them):
#   setup   <vps_ssh_ip> <exit_ip>   rsync code, archive stale profile, bring
#                                     up the display stack, launch Chrome
#                                     through the proxy, verify the real exit
#                                     IP via CDP. Then YOU warm Cloudflare in
#                                     VNC (this script prints how).
#   launch  <vps_ssh_ip> <exit_ip>   offline-prune already-cached ids, then
#                                     start the self-pruning scraper.
#
# Credentials are read from the environment (never hardcode / commit):
#   export CS2_PROXY_USERNAME=...   export CS2_PROXY_PASSWORD=...
# SSH key override:  export SSH_KEY=~/.ssh/id_ed25519_hetzner  (default)
#
# VPS -> dedicated US ISP exit IP (assign for ASN/subnet diversity):
#   VPS-1  50.114.173.114   (AS3561 CenturyLink/Lumen, NYC)   <- only non-RCN
#   VPS-2  192.228.122.89   (AS6079 RCN, Milford DE)
#   VPS-3  104.234.88.177   (AS6079 RCN, Leesburg VA)
#   VPS-4  104.234.82.12    (AS6079 RCN, Leesburg VA)
set -euo pipefail

SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_hetzner}"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
PROXY_PORT=12323
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_MODULES_DIR="$REPO_ROOT/data/hltv_cache/node/node_modules"

die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  echo
  echo "Usage: $0 {setup|launch} <vps_ssh_ip> <exit_ip>"
  exit 2
}

require_creds() {
  [ -n "${CS2_PROXY_USERNAME:-}" ] || die "CS2_PROXY_USERNAME not set in env"
  [ -n "${CS2_PROXY_PASSWORD:-}" ] || die "CS2_PROXY_PASSWORD not set in env"
}

CMD="${1:-}"; VPS="${2:-}"; EXIT_IP="${3:-}"
[ -n "$CMD" ] && [ -n "$VPS" ] && [ -n "$EXIT_IP" ] || usage
require_creds

ssh_vps() { ssh "${SSH_OPTS[@]}" "root@$VPS" "$@"; }

# ---------------------------------------------------------------------------
do_setup() {
  [ -d "$NODE_MODULES_DIR" ] \
    || die "missing $NODE_MODULES_DIR; run: npm install --prefix data/hltv_cache/node puppeteer puppeteer-extra puppeteer-extra-plugin-stealth"

  echo ">> [1/3] rsync tools/ + browser deps to $VPS"
  ssh_vps "mkdir -p /root/cs2/tools /root/cs2/node_modules"
  rsync -avz -e "ssh ${SSH_OPTS[*]}" "$REPO_ROOT/tools/" "root@$VPS:/root/cs2/tools/" \
    | tail -3
  rsync -avz -e "ssh ${SSH_OPTS[*]}" "$NODE_MODULES_DIR/" "root@$VPS:/root/cs2/node_modules/" \
    | tail -3

  echo ">> [2/3] remote setup (profile, display stack, Chrome via $EXIT_IP)"
  ssh_vps "EXIT_IP='$EXIT_IP' PUSER='$CS2_PROXY_USERNAME' PPASS='$CS2_PROXY_PASSWORD' PORT='$PROXY_PORT' bash -s" <<'REMOTE'
set -euo pipefail
cd /root/cs2 || { echo "FATAL: /root/cs2 missing"; exit 1; }

# Stop Chrome before moving the profile; reruns can otherwise archive a live
# user_data directory and leave Chrome holding stale profile locks.
tmux kill-session -t chrome 2>/dev/null || true
pkill -f 'google-chrome.*--user-data-dir=/root/cs2/user_data' 2>/dev/null || true
sleep 1

# stale (pre-proxy) cf_clearance is bound to the old IP — archive it.
if [ -d /root/cs2/user_data ]; then
  mv /root/cs2/user_data "/root/cs2/user_data.preproxy.$(date +%s)" && echo "archived old user_data"
fi

echo -n "proxy curl: "; curl -s --max-time 25 -x "http://$PUSER:$PPASS@$EXIT_IP:$PORT" https://api.ipify.org; echo " (want $EXIT_IP)"
grep -q 'page.authenticate' /root/cs2/tools/lib/hltv_browser.mjs \
  && echo "code: page.authenticate present" || echo "code: WARN missing page.authenticate"
grep -q 'prune-ids' /root/cs2/tools/fetch_hltv_matches.mjs \
  && echo "code: prune-ids present" || echo "code: WARN missing prune-ids"

start_tmux_service() {
  session="$1"
  health_check="$2"
  command="$3"
  fatal_message="$4"

  if eval "$health_check"; then
    return 0
  fi

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "restarting stale tmux session: $session"
    tmux capture-pane -pt "$session" -S -20 2>/dev/null || true
    tmux kill-session -t "$session" 2>/dev/null || true
  fi

  tmux new -ds "$session" "$command"
  for i in $(seq 1 40); do
    eval "$health_check" && return 0
    sleep 0.5
  done

  echo "FATAL: $fatal_message"
  tmux capture-pane -pt "$session" -S -25 2>/dev/null || true
  exit 2
}

rm -f /tmp/.X99-lock
start_tmux_service desktop '[ -S /tmp/.X11-unix/X99 ]' 'Xvfb :99 -screen 0 1366x768x24' 'Xvfb :99 down'
echo "Xvfb :99 ready"

start_tmux_service wm "pgrep -f 'fluxbox' >/dev/null" 'DISPLAY=:99 fluxbox' 'fluxbox down'
tmux kill-session -t vnc 2>/dev/null || true
tmux new -ds vnc 'x11vnc -display :99 -rfbport 5900 -listen localhost -nopw -forever -shared -noxdamage'
sleep 2
ss -ltnp 2>/dev/null | grep -q ':5900' && echo "x11vnc on 5900" || { echo "WARN x11vnc"; tmux capture-pane -pt vnc -S -25; }

tmux new -ds chrome "DISPLAY=:99 google-chrome --no-sandbox --no-first-run --no-default-browser-check --disable-blink-features=AutomationControlled --disable-dev-shm-usage --proxy-server=http://$EXIT_IP:$PORT --proxy-bypass-list='<-loopback>' --user-data-dir=/root/cs2/user_data --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --window-size=1366,768 https://www.hltv.org/stats/matches/mapstatsid/213684/-"
for i in $(seq 1 120); do curl -sf http://localhost:9222/json/version >/dev/null 2>&1 && break; sleep 0.5; done
curl -sf http://localhost:9222/json/version >/dev/null 2>&1 && echo "Chrome CDP up" || { echo "FATAL: CDP down"; tmux capture-pane -pt chrome -S -25; exit 3; }

cat > /root/cs2/tools/_proxy_check.mjs <<'EOF'
const mod = await import("/root/cs2/node_modules/puppeteer-extra/dist/index.cjs.js");
const puppeteer = mod.default ?? mod;
const b = await puppeteer.connect({ browserURL: "http://localhost:9222", defaultViewport: null });
const p = await b.newPage();
await p.authenticate({ username: process.env.CS2_PROXY_USERNAME, password: process.env.CS2_PROXY_PASSWORD });
const expected = process.env.EXPECTED_EXIT_IP;
try { await p.goto("https://api.ipify.org", { waitUntil: "domcontentloaded", timeout: 30000 });
  const actual = await p.evaluate(() => document.body.innerText.trim());
  console.log("BROWSER_EXIT_IP=" + actual);
  if (expected && actual !== expected) {
    console.error(`BROWSER_EXIT_IP_MISMATCH expected=${expected} actual=${actual}`);
    process.exitCode = 1;
  }
} catch (e) {
  console.error("BROWSER_EXIT_IP_ERROR=" + (e?.message ?? e));
  process.exitCode = 1;
}
finally { await p.close().catch(() => {}); b.disconnect(); }
EOF
CS2_PROXY_USERNAME=$PUSER CS2_PROXY_PASSWORD=$PPASS EXPECTED_EXIT_IP=$EXIT_IP timeout 60 node /root/cs2/tools/_proxy_check.mjs
rm -f /root/cs2/tools/_proxy_check.mjs
echo "EXPECTED BROWSER_EXIT_IP=$EXIT_IP"
REMOTE

  cat <<EOF

>> [3/3] HUMAN STEP — warm Cloudflare in VNC (run locally):

  pkill -f '5901:localhost:5900' 2>/dev/null
  ssh -i $SSH_KEY -L 5901:localhost:5900 -N root@$VPS &
  sleep 1; vncviewer localhost:5901

In VNC: clear the Cloudflare challenge until the HLTV stats page renders
(enter $CS2_PROXY_USERNAME / <password> if a proxy auth popup appears),
then close the VNC viewer ONLY. When done:

  $0 launch $VPS $EXIT_IP
EOF
}

# ---------------------------------------------------------------------------
do_launch() {
  echo ">> offline-prune already-cached ids + start self-pruning scraper on $VPS"
  ssh_vps "EXIT_IP='$EXIT_IP' PUSER='$CS2_PROXY_USERNAME' PPASS='$CS2_PROXY_PASSWORD' PORT='$PROXY_PORT' bash -s" <<'REMOTE'
set -u
cd /root/cs2 || exit 1
curl -sf http://localhost:9222/json/version >/dev/null 2>&1 || { echo "FATAL: Chrome/CDP not up — run setup first"; exit 1; }

# Drop ids we already have a JSON for (fast, offline). Order is irrelevant
# for a queue; the scraper also prunes the rest as it runs.
if [ -f match_ids.txt ]; then
  before=$(grep -c . match_ids.txt || true)
  ls matches 2>/dev/null | sed 's/\.json$//' | sort -u > /tmp/have.ids || true
  grep -E '^[0-9]+$' match_ids.txt | sort -u | comm -23 - /tmp/have.ids > match_ids.txt.tmp
  mv match_ids.txt.tmp match_ids.txt
  after=$(grep -c . match_ids.txt || true)
  echo "pre-prune: $before -> $after ids ( $((before-after)) already cached )"
fi

tmux kill-session -t scrape 2>/dev/null || true
tmux new -ds scrape "stdbuf -oL -eL env \
  CHROME_REMOTE_URL=http://localhost:9222 \
  CS2_PROXY_USERNAME=$PUSER CS2_PROXY_PASSWORD=$PPASS \
  PUPPETEER_MODULE_PATH=/root/cs2/node_modules/puppeteer-extra/dist/index.cjs.js \
  STEALTH_MODULE_PATH=/root/cs2/node_modules/puppeteer-extra-plugin-stealth/index.js \
  node /root/cs2/tools/fetch_hltv_matches.mjs \
    --ids-file /root/cs2/match_ids.txt \
    --output-dir /root/cs2/matches \
    --user-data-dir /root/cs2/user_data \
    --delay-ms 5000 --headless true --nav-timeout-ms 90000 \
    --prune-ids true --max-consecutive-failures 0 \
    2>&1 | tee -a /root/cs2/run.log"
sleep 3
tmux has-session -t scrape 2>/dev/null && echo "scrape RUNNING" || echo "scrape FAILED to start"
REMOTE
  echo ">> tail with:  ssh -i $SSH_KEY root@$VPS 'tail -f /root/cs2/run.log'"
}

case "$CMD" in
  setup)  do_setup ;;
  launch) do_launch ;;
  *) usage ;;
esac
