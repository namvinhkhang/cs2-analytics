from pathlib import Path


SCRIPT_PATH = Path("scripts/deploy_hltv_proxy_vps.sh")


def test_deploy_script_restarts_stale_display_sessions() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "start_tmux_service()" in script
    assert "tmux kill-session -t \"$session\"" in script
    assert "start_tmux_service desktop" in script
    assert "[ -S /tmp/.X11-unix/X99 ]" in script
    assert "start_tmux_service wm" in script


def test_deploy_script_syncs_browser_dependencies_and_fails_verification_errors() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "data/hltv_cache/node/node_modules" in script
    assert "root@$VPS:/root/cs2/node_modules/" in script
    assert "set -euo pipefail" in script
    assert "EXPECTED_EXIT_IP" in script
    assert "process.exitCode = 1" in script


def test_deploy_script_waits_long_enough_for_chrome_cdp() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "seq 1 120" in script


def test_deploy_script_stops_chrome_before_archiving_profile() -> None:
    script = SCRIPT_PATH.read_text(encoding="utf-8")

    stop_chrome = script.index("tmux kill-session -t chrome")
    archive_profile = script.index("user_data.preproxy")
    assert stop_chrome < archive_profile
