#!/usr/bin/env python3
"""Bootstrap modern CS2 data from the public CS API into S3.

Uploads:
- raw/csapi/team_rankings/... from /rankings/
- raw/csapi/player_stats/... from /matches/ and /matches/{matchid}/stats
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import structlog

from cs2_analytics.ingestion.csapi import CSAPIClient
from cs2_analytics.utils.config import settings
from cs2_analytics.utils.s3 import build_s3_key

logger = structlog.get_logger()

ProfileName = Literal["daily", "weekly", "backfill"]
PROFILE_NAMES: tuple[ProfileName, ...] = ("daily", "weekly", "backfill")


class BootstrapConfigError(ValueError):
    """Raised when CLI or environment bootstrap profile settings are invalid."""


@dataclass(frozen=True)
class CSAPIBootstrapProfile:
    """Resolved CS API bootstrap settings for one run profile."""

    profile: ProfileName
    description: str
    match_limit: int
    match_offset: int
    match_pages: int
    max_matches: int | None
    request_delay_seconds: float
    progress_interval: int
    output_filename: str


@dataclass(frozen=True)
class CSAPIBootstrapOutputKeys:
    """S3 object keys that one profile run would write."""

    team_rankings: str
    matches: str
    player_stats: str


def _read_int_env(name: str, default: int, *, minimum: int = 0) -> int:
    """Read an integer environment override with a defensive fallback."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_using_default", name=name, value=raw_value, default=default)
        return default
    return max(value, minimum)


def _read_optional_int_env(name: str) -> int | None:
    """Read an optional integer environment override."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return None
    try:
        return int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_ignored", name=name, value=raw_value)
        return None


def _read_float_env(name: str, default: float, *, minimum: float = 0.0) -> float:
    """Read a float environment override with a defensive fallback."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning(
            "invalid_float_env_using_default",
            name=name,
            value=raw_value,
            default=default,
        )
        return default
    return max(value, minimum)


def _read_bool_env(name: str, default: bool) -> bool:
    """Read a boolean environment override."""
    raw_value = os.environ.get(name)
    if raw_value is None or not raw_value.strip():
        return default
    normalized = raw_value.strip().casefold()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    logger.warning("invalid_bool_env_using_default", name=name, value=raw_value, default=default)
    return default


def _profile_env_names(profile: ProfileName, suffix: str) -> tuple[str, str]:
    """Return profile-specific then legacy global env var names for a setting."""
    return (f"CS2_CSAPI_{profile.upper()}_{suffix}", f"CS2_CSAPI_{suffix}")


def _read_profile_raw_env(profile: ProfileName, suffix: str) -> tuple[str, str] | None:
    """Read profile-specific env first while preserving legacy global env support."""
    for name in _profile_env_names(profile, suffix):
        raw_value = os.environ.get(name)
        if raw_value is not None and raw_value.strip():
            return name, raw_value.strip()
    return None


def _read_profile_int_env(
    profile: ProfileName,
    suffix: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    """Read an integer profile override with profile-specific precedence."""
    resolved = _read_profile_raw_env(profile, suffix)
    if resolved is None:
        return default

    name, raw_value = resolved
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_using_default", name=name, value=raw_value, default=default)
        return default
    return max(value, minimum)


def _read_profile_optional_int_env(
    profile: ProfileName,
    suffix: str,
    default: int | None,
    *,
    minimum: int = 0,
) -> int | None:
    """Read an optional integer profile override.

    Use "none", "null", or "all" to remove a profile's default match cap.
    """
    resolved = _read_profile_raw_env(profile, suffix)
    if resolved is None:
        return default

    name, raw_value = resolved
    if raw_value.casefold() in {"none", "null", "all"}:
        return None
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("invalid_int_env_using_default", name=name, value=raw_value, default=default)
        return default
    return max(value, minimum)


def _read_profile_float_env(
    profile: ProfileName,
    suffix: str,
    default: float,
    *,
    minimum: float = 0.0,
) -> float:
    """Read a float profile override with profile-specific precedence."""
    resolved = _read_profile_raw_env(profile, suffix)
    if resolved is None:
        return default

    name, raw_value = resolved
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning(
            "invalid_float_env_using_default",
            name=name,
            value=raw_value,
            default=default,
        )
        return default
    return max(value, minimum)


def _read_profile_string_env(profile: ProfileName, suffix: str) -> str | None:
    """Read a string profile override with profile-specific precedence."""
    resolved = _read_profile_raw_env(profile, suffix)
    if resolved is None:
        return None
    _, raw_value = resolved
    return raw_value


def _normalize_profile(profile: str) -> ProfileName:
    """Validate a profile value from CLI, Airflow, or tests."""
    normalized = profile.strip().casefold()
    if normalized in PROFILE_NAMES:
        return cast(ProfileName, normalized)
    valid_profiles = ", ".join(PROFILE_NAMES)
    raise BootstrapConfigError(
        f"Unknown CS API bootstrap profile '{profile}'. Expected one of: {valid_profiles}."
    )


def _default_profile(profile: ProfileName) -> CSAPIBootstrapProfile:
    """Return conservative profile defaults before env overrides."""
    if profile == "daily":
        return CSAPIBootstrapProfile(
            profile=profile,
            description="bounded daily refresh for rankings, recent matches, and player form",
            match_limit=50,
            match_offset=0,
            match_pages=3,
            max_matches=150,
            request_delay_seconds=0.5,
            progress_interval=10,
            output_filename="",
        )
    if profile == "weekly":
        return CSAPIBootstrapProfile(
            profile=profile,
            description="deeper weekly refresh for Hidden Gem rolling windows",
            match_limit=100,
            match_offset=0,
            match_pages=30,
            max_matches=3000,
            request_delay_seconds=1.0,
            progress_interval=25,
            output_filename="",
        )
    return CSAPIBootstrapProfile(
        profile=profile,
        description="explicit manual backfill with larger resumable chunks",
        match_limit=100,
        match_offset=0,
        match_pages=100,
        max_matches=10_000,
        request_delay_seconds=1.0,
        progress_interval=50,
        output_filename="",
    )


def _output_filename(profile: ProfileName, offset: int, max_matches: int | None) -> str:
    """Choose an S3 object name that is safe for profile and chunked bootstraps."""
    if offset > 0 or max_matches is not None:
        match_count = "all" if max_matches is None else str(max_matches)
        return f"{profile}_matches_offset_{offset}_count_{match_count}.parquet"
    return f"{profile}.parquet"


def build_profile_config(
    profile: str,
    *,
    allow_backfill: bool = False,
) -> CSAPIBootstrapProfile:
    """Resolve one profile from defaults, env overrides, and backfill safety gates."""
    resolved_profile = _normalize_profile(profile)
    env_allows_backfill = _read_bool_env("CS2_CSAPI_ALLOW_BACKFILL", False)
    if resolved_profile == "backfill" and not (allow_backfill or env_allows_backfill):
        raise BootstrapConfigError(
            "The backfill profile requires explicit opt-in via --allow-backfill "
            "or CS2_CSAPI_ALLOW_BACKFILL=true."
        )

    defaults = _default_profile(resolved_profile)
    match_limit = _read_profile_int_env(
        resolved_profile,
        "MATCH_LIMIT",
        defaults.match_limit,
        minimum=1,
    )
    match_offset = _read_profile_int_env(
        resolved_profile,
        "MATCH_OFFSET",
        defaults.match_offset,
        minimum=0,
    )
    match_pages = _read_profile_int_env(
        resolved_profile,
        "MATCH_PAGES",
        defaults.match_pages,
        minimum=1,
    )
    max_matches = _read_profile_optional_int_env(
        resolved_profile,
        "MAX_MATCHES",
        defaults.max_matches,
        minimum=0,
    )
    request_delay_seconds = _read_profile_float_env(
        resolved_profile,
        "REQUEST_DELAY_SECONDS",
        defaults.request_delay_seconds,
        minimum=0.0,
    )
    progress_interval = _read_profile_int_env(
        resolved_profile,
        "PROGRESS_INTERVAL",
        defaults.progress_interval,
        minimum=0,
    )
    output_filename = _read_profile_string_env(
        resolved_profile,
        "OUTPUT_FILENAME",
    ) or _output_filename(resolved_profile, match_offset, max_matches)

    return CSAPIBootstrapProfile(
        profile=resolved_profile,
        description=defaults.description,
        match_limit=match_limit,
        match_offset=match_offset,
        match_pages=match_pages,
        max_matches=max_matches,
        request_delay_seconds=request_delay_seconds,
        progress_interval=progress_interval,
        output_filename=output_filename,
    )


def _estimated_match_window(config: CSAPIBootstrapProfile) -> int | None:
    """Estimate match rows fetched before ingestion starts for operator visibility."""
    page_window = config.match_limit * config.match_pages
    if config.max_matches is None:
        return page_window
    return min(page_window, config.max_matches)


def _s3_key_exists(bucket: str, key: str, region: str) -> bool:
    """Return True when the profile output object already exists in S3."""
    s3 = boto3.client("s3", region_name=region)
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _profile_output_keys(
    config: CSAPIBootstrapProfile,
    ingest_date: date,
) -> CSAPIBootstrapOutputKeys:
    """Build the raw S3 keys for all objects written by one profile run."""
    y, m, d = ingest_date.year, ingest_date.month, ingest_date.day
    return CSAPIBootstrapOutputKeys(
        team_rankings=build_s3_key("csapi", "team_rankings", y, m, d),
        matches=build_s3_key(
            "csapi",
            "matches",
            y,
            m,
            d,
            filename=config.output_filename,
        ),
        player_stats=build_s3_key(
            "csapi",
            "player_stats",
            y,
            m,
            d,
            filename=config.output_filename,
        ),
    )


def _log_existing_output(
    *,
    profile: ProfileName,
    entity: str,
    key: str,
) -> None:
    """Make idempotent skips visible in Airflow and manual bootstrap logs."""
    logger.info(
        "csapi_bootstrap_output_exists_skipping",
        profile=profile,
        entity=entity,
        key=key,
    )


async def run_profile(
    profile: str = "daily",
    *,
    allow_backfill: bool = False,
) -> tuple[int, int, int]:
    """Fetch rankings, matches, and match-level player stats for one profile."""
    config = build_profile_config(profile, allow_backfill=allow_backfill)
    ingest_date = date.today()
    output_keys = _profile_output_keys(config, ingest_date)
    region = settings.aws_region
    bucket = settings.aws_s3_bucket

    logger.info(
        "csapi_bootstrap_profile_summary",
        profile=config.profile,
        description=config.description,
        ingest_date=ingest_date.isoformat(),
        match_limit=config.match_limit,
        match_offset=config.match_offset,
        match_pages=config.match_pages,
        max_matches=config.max_matches,
        estimated_match_window=_estimated_match_window(config),
        request_delay_seconds=config.request_delay_seconds,
        progress_interval=config.progress_interval,
        output_filename=config.output_filename,
    )
    if config.profile == "backfill":
        # Backfill resumes by bumping MATCH_OFFSET while keeping each chunk key unique.
        logger.info(
            "csapi_bootstrap_backfill_chunk",
            match_offset=config.match_offset,
            max_matches=config.max_matches,
            output_filename=config.output_filename,
        )

    ranking_exists = _s3_key_exists(bucket, output_keys.team_rankings, region)
    match_exists = _s3_key_exists(bucket, output_keys.matches, region)
    player_exists = _s3_key_exists(bucket, output_keys.player_stats, region)

    if ranking_exists:
        _log_existing_output(
            profile=config.profile,
            entity="team_rankings",
            key=output_keys.team_rankings,
        )
    if match_exists:
        _log_existing_output(
            profile=config.profile,
            entity="matches",
            key=output_keys.matches,
        )
    if player_exists:
        _log_existing_output(
            profile=config.profile,
            entity="player_stats",
            key=output_keys.player_stats,
        )
    if ranking_exists and match_exists and player_exists:
        return 0, 0, 0

    async with CSAPIClient() as client:
        ranking_count = (
            0
            if ranking_exists
            else await client.ingest_team_rankings(
                bucket=bucket,
                ingest_date=ingest_date,
                region=region,
            )
        )
        match_count = (
            0
            if match_exists
            else await client.ingest_matches(
                bucket=bucket,
                ingest_date=ingest_date,
                limit=config.match_limit,
                offset=config.match_offset,
                pages=config.match_pages,
                max_matches=config.max_matches,
                request_delay_seconds=config.request_delay_seconds,
                progress_interval=config.progress_interval,
                output_filename=config.output_filename,
                region=region,
            )
        )
        player_count = (
            0
            if player_exists
            else await client.ingest_player_stats(
                bucket=bucket,
                ingest_date=ingest_date,
                limit=config.match_limit,
                offset=config.match_offset,
                pages=config.match_pages,
                max_matches=config.max_matches,
                request_delay_seconds=config.request_delay_seconds,
                progress_interval=config.progress_interval,
                output_filename=config.output_filename,
                region=region,
            )
        )
    return ranking_count, match_count, player_count


async def _run(
    profile: str = "daily",
    *,
    allow_backfill: bool = False,
) -> tuple[int, int, int]:
    """Backward-compatible internal entry point for older script callers."""
    return await run_profile(profile, allow_backfill=allow_backfill)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags without touching Airflow import-time behavior."""
    default_profile = os.environ.get("CS2_CSAPI_PROFILE", "daily")
    parser = argparse.ArgumentParser(description="Bootstrap CS API raw data into S3.")
    parser.add_argument(
        "--profile",
        choices=PROFILE_NAMES,
        default=_normalize_profile(default_profile),
        help="Bootstrap profile to run. Defaults to CS2_CSAPI_PROFILE or daily.",
    )
    parser.add_argument(
        "--allow-backfill",
        action="store_true",
        help="Required safety opt-in when --profile backfill is selected.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run CS API bootstrap."""
    try:
        args = _parse_args(argv)
        profile = _normalize_profile(args.profile)
    except BootstrapConfigError as exc:
        logger.error("csapi_bootstrap_configuration_error", error=str(exc))
        raise SystemExit(str(exc)) from exc

    logger.info("csapi_bootstrap_starting", bucket=settings.aws_s3_bucket, profile=profile)
    try:
        ranking_count, match_count, player_count = asyncio.run(
            _run(profile, allow_backfill=bool(args.allow_backfill))
        )
    except BootstrapConfigError as exc:
        logger.error("csapi_bootstrap_configuration_error", error=str(exc), profile=profile)
        raise SystemExit(str(exc)) from exc
    logger.info(
        "csapi_bootstrap_finished",
        profile=profile,
        team_rankings=ranking_count,
        matches=match_count,
        player_stats=player_count,
    )
    print(
        f"CS API {profile} bootstrap complete: "
        f"{ranking_count} rankings, {match_count} matches, "
        f"and {player_count} player stats written "
        f"to s3://{settings.aws_s3_bucket}/raw/csapi/"
    )


if __name__ == "__main__":
    main()
