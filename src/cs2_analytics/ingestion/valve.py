"""Valve regional standings ingestion helpers.

Valve's public standings repo exposes current roster rankings as Markdown.
This module intentionally uses that data only for team geography enrichment;
model ranking features continue to come from CS API match/ranking lineage.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from cs2_analytics.utils.parquet import VALVE_TEAM_REGION_SCHEMA
from cs2_analytics.utils.s3 import build_s3_key, write_parquet_to_s3

logger = structlog.get_logger()

REGIONS: tuple[str, ...] = ("Americas", "Asia", "Europe")
REPO_OWNER = "ValveSoftware"
REPO_NAME = "counter-strike_regional_standings"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main"
SNAPSHOT_FILE_RE = re.compile(
    r"^standings_(?P<kind>americas|asia|europe|global)_(?P<year>\d{4})_"
    r"(?P<month>\d{2})_(?P<day>\d{2})\.md$"
)
DETAIL_LINK_RE = re.compile(r"\[details\]\((?P<path>[^)]+)\)", re.IGNORECASE)


@dataclass(frozen=True)
class ValveSnapshotFileSet:
    """A complete Valve standings snapshot for one date."""

    year: int
    snapshot_date: date
    regional_filenames: dict[str, str]
    global_filename: str


class ValveTeamRegion(BaseModel):
    """One Valve standings row used for region enrichment only."""

    model_config = ConfigDict(extra="forbid")

    snapshot_date: str
    team_name: str
    normalized_team_name: str
    region: str
    regional_rank: int
    global_rank: int | None
    points: int | None
    roster: str | None
    detail_path: str | None
    source: str = "valve"

    def to_raw_record(self) -> dict[str, Any]:
        """Return the raw warehouse record without introducing ranking features."""
        return self.model_dump()


def normalize_team_name(value: str) -> str:
    """Normalize team names enough to join public sources conservatively."""
    without_team_prefix = re.sub(r"^team[\s_-]+", "", value.strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", "", without_team_prefix.casefold())


def _parse_int(value: str) -> int | None:
    cleaned = re.sub(r"[^0-9-]+", "", value)
    if not cleaned:
        return None
    return int(cleaned)


def _table_rows(markdown: str) -> list[list[str]]:
    """Parse Valve's simple Markdown tables into stripped cells."""
    rows: list[list[str]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.replace("<br />", "").strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0].casefold() in {"standing", ":-"}:
            continue
        if set(cells[0]) <= {":", "-"}:
            continue
        rows.append(cells)
    return rows


def _detail_path(cell: str) -> str | None:
    match = DETAIL_LINK_RE.search(cell)
    if match is None:
        return None
    return match.group("path").strip()


def _global_ranks(global_markdown: str) -> dict[str, int]:
    """Build a normalized team name to global standing lookup."""
    ranks: dict[str, int] = {}
    for cells in _table_rows(global_markdown):
        if len(cells) < 3:
            continue
        rank = _parse_int(cells[0])
        team_name = cells[2]
        if rank is None or not team_name:
            continue
        normalized = normalize_team_name(team_name)
        if normalized and normalized not in ranks:
            ranks[normalized] = rank
    return ranks


def parse_valve_standings_snapshot(
    *,
    snapshot_date: date,
    regional_markdown_by_region: dict[str, str],
    global_markdown: str,
) -> list[ValveTeamRegion]:
    """Parse regional standings and attach global rank context by team name."""
    global_ranks = _global_ranks(global_markdown)
    records: list[ValveTeamRegion] = []

    for region, markdown in regional_markdown_by_region.items():
        for cells in _table_rows(markdown):
            if len(cells) < 4:
                logger.warning("valve_standings_row_skipped_short", region=region, row=cells)
                continue

            regional_rank = _parse_int(cells[0])
            points = _parse_int(cells[1])
            team_name = cells[2]
            roster = cells[3] or None
            detail_path = _detail_path(cells[4]) if len(cells) > 4 else None
            normalized = normalize_team_name(team_name)
            if regional_rank is None or not normalized:
                logger.warning("valve_standings_row_skipped_invalid", region=region, row=cells)
                continue

            records.append(
                ValveTeamRegion(
                    snapshot_date=snapshot_date.isoformat(),
                    team_name=team_name,
                    normalized_team_name=normalized,
                    region=region,
                    regional_rank=regional_rank,
                    global_rank=global_ranks.get(normalized),
                    points=points,
                    roster=roster,
                    detail_path=detail_path,
                )
            )

    return records


def select_latest_snapshot(
    *,
    years: list[str],
    filenames: list[str],
) -> ValveSnapshotFileSet:
    """Select the newest complete Valve snapshot from a year directory listing."""
    numeric_years = sorted(int(year) for year in years if year.isdigit())
    if not numeric_years:
        raise ValueError("No numeric Valve live year folders found.")
    latest_year = numeric_years[-1]

    files_by_date: dict[date, dict[str, str]] = {}
    for filename in filenames:
        match = SNAPSHOT_FILE_RE.match(filename)
        if match is None or int(match.group("year")) != latest_year:
            continue
        snapshot_date = date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
        files_by_date.setdefault(snapshot_date, {})[match.group("kind")] = filename

    required = {"americas", "asia", "europe", "global"}
    complete_dates = [
        snapshot_date
        for snapshot_date, files in files_by_date.items()
        if required.issubset(files)
    ]
    if not complete_dates:
        raise ValueError(f"No complete Valve standings snapshot found for {latest_year}.")

    selected_date = max(complete_dates)
    selected_files = files_by_date[selected_date]
    return ValveSnapshotFileSet(
        year=latest_year,
        snapshot_date=selected_date,
        regional_filenames={
            "Americas": selected_files["americas"],
            "Asia": selected_files["asia"],
            "Europe": selected_files["europe"],
        },
        global_filename=selected_files["global"],
    )


def build_valve_team_regions_s3_key(ingest_date: date) -> str:
    """Build the raw S3 key for one Valve region snapshot upload."""
    return build_s3_key(
        "valve",
        "team_regions",
        ingest_date.year,
        ingest_date.month,
        ingest_date.day,
    )


class ValveStandingsClient:
    """Small GitHub-backed client for Valve regional standings markdown."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def __aenter__(self) -> ValveStandingsClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    async def _github_names(self, path: str) -> list[str]:
        response = await self._client.get(f"{GITHUB_API_BASE}/{path}", params={"ref": "main"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Expected GitHub directory listing for {path}.")
        return [
            str(item["name"])
            for item in payload
            if isinstance(item, dict) and item.get("name") is not None
        ]

    async def _raw_markdown(self, path: str) -> str:
        response = await self._client.get(f"{RAW_BASE}/{path}")
        response.raise_for_status()
        return response.text

    async def fetch_latest_snapshot_records(self) -> list[ValveTeamRegion]:
        """Fetch and parse the latest complete Valve standings snapshot."""
        years = await self._github_names("live")
        latest_year = max(int(year) for year in years if year.isdigit())
        filenames = await self._github_names(f"live/{latest_year}")
        snapshot = select_latest_snapshot(years=years, filenames=filenames)

        regional_markdown = {
            region: await self._raw_markdown(f"live/{snapshot.year}/{filename}")
            for region, filename in snapshot.regional_filenames.items()
        }
        global_markdown = await self._raw_markdown(
            f"live/{snapshot.year}/{snapshot.global_filename}"
        )
        records = parse_valve_standings_snapshot(
            snapshot_date=snapshot.snapshot_date,
            regional_markdown_by_region=regional_markdown,
            global_markdown=global_markdown,
        )
        logger.info(
            "valve_standings_snapshot_parsed",
            year=snapshot.year,
            snapshot_date=snapshot.snapshot_date.isoformat(),
            records=len(records),
        )
        return records

    async def ingest_team_regions(
        self,
        bucket: str,
        ingest_date: date,
        *,
        region: str = "us-east-1",
    ) -> int:
        """Fetch the latest Valve team regions and write them to S3."""
        records = [record.to_raw_record() for record in await self.fetch_latest_snapshot_records()]
        if records:
            write_parquet_to_s3(
                records=records,
                schema=VALVE_TEAM_REGION_SCHEMA,
                bucket=bucket,
                key=build_valve_team_regions_s3_key(ingest_date),
                region=region,
            )
        logger.info("valve_team_regions_ingested", count=len(records))
        return len(records)


async def ingest_latest_team_regions(
    bucket: str,
    ingest_date: date,
    *,
    region: str = "us-east-1",
) -> int:
    """Convenience entry point for scripts and Airflow tasks."""
    async with ValveStandingsClient() as client:
        return await client.ingest_team_regions(bucket, ingest_date, region=region)


def ingest_latest_team_regions_sync(
    bucket: str,
    ingest_date: date,
    *,
    region: str = "us-east-1",
) -> int:
    """Synchronous wrapper for task functions that cannot await directly."""
    return asyncio.run(ingest_latest_team_regions(bucket, ingest_date, region=region))
