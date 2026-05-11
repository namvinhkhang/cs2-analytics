"""Snapshot and Snowflake helpers for the public dashboard."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_SNAPSHOT_DIR = Path("dashboard/snapshots")


@dataclass(frozen=True)
class MartSnapshot:
    """A local mart snapshot loaded for dashboard rendering."""

    name: str
    frame: pd.DataFrame
    loaded_at: datetime | None
    path: Path


def snapshot_path(mart_name: str, snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR) -> Path:
    """Return the default Parquet snapshot path for a mart."""
    return snapshot_dir / f"{mart_name}.parquet"


def load_mart_snapshot(
    mart_name: str,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> MartSnapshot:
    """Load one mart snapshot from a local Parquet file."""
    path = snapshot_path(mart_name, snapshot_dir=snapshot_dir)
    frame = pd.read_parquet(path)
    frame.columns = [str(column).lower() for column in frame.columns]
    loaded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) if path.exists() else None
    return MartSnapshot(name=mart_name, frame=frame, loaded_at=loaded_at, path=path)


@lru_cache(maxsize=32)
def _load_mart_snapshot_cached_fallback(mart_name: str, snapshot_dir: str) -> MartSnapshot:
    return load_mart_snapshot(mart_name, snapshot_dir=Path(snapshot_dir))


def _load_mart_snapshot_for_streamlit(mart_name: str, snapshot_dir: str) -> MartSnapshot:
    return load_mart_snapshot(mart_name, snapshot_dir=Path(snapshot_dir))


_STREAMLIT_CACHE_LOADERS: dict[int, Callable[[str, str], MartSnapshot]] = {}


def load_mart_snapshot_cached(
    mart_name: str,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    ttl_seconds: int = 3600,
) -> MartSnapshot:
    """Load a mart snapshot through Streamlit cache when Streamlit is available."""
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return _load_mart_snapshot_cached_fallback(mart_name, str(snapshot_dir))

    if ttl_seconds not in _STREAMLIT_CACHE_LOADERS:
        # Streamlit's cache is optional here so unit tests and scripts can load snapshots directly.
        _STREAMLIT_CACHE_LOADERS[ttl_seconds] = st.cache_data(
            ttl=ttl_seconds,
            show_spinner=False,
        )(_load_mart_snapshot_for_streamlit)
    return _STREAMLIT_CACHE_LOADERS[ttl_seconds](mart_name, str(snapshot_dir))


def data_freshness(snapshots: Sequence[MartSnapshot]) -> pd.DataFrame:
    """Build a compact freshness table for dashboard status displays."""
    return pd.DataFrame(
        [
            {
                "product": snapshot.name,
                "rows": len(snapshot.frame),
                "loaded_at": snapshot.loaded_at,
                "snapshot_path": str(snapshot.path),
            }
            for snapshot in snapshots
        ],
        columns=["product", "rows", "loaded_at", "snapshot_path"],
    )


def _streamlit_secrets() -> Mapping[str, Any]:
    try:
        import streamlit as st
    except ModuleNotFoundError:
        return {}

    try:
        secrets = st.secrets
        snowflake_secrets = secrets.get("snowflake", secrets)
    except Exception:
        # Accessing st.secrets outside a configured app can raise Streamlit-specific errors.
        return {}
    if isinstance(snowflake_secrets, Mapping):
        return snowflake_secrets
    return {}


def _credential(
    secrets: Mapping[str, Any],
    env_name: str,
    *secret_names: str,
    default: str | None = None,
) -> str:
    for secret_name in secret_names:
        value = secrets.get(secret_name) or secrets.get(secret_name.upper())
        if value is not None:
            return str(value)
    if env_name in os.environ:
        return os.environ[env_name]
    if default is not None:
        return default
    raise KeyError(f"missing Snowflake credential: {env_name}")


def _snowflake_connect_kwargs() -> dict[str, str]:
    secrets = _streamlit_secrets()
    return {
        "account": _credential(secrets, "SNOWFLAKE_ACCOUNT", "account"),
        "user": _credential(secrets, "SNOWFLAKE_USER", "user"),
        "authenticator": _credential(
            secrets,
            "SNOWFLAKE_AUTHENTICATOR",
            "authenticator",
            default="SNOWFLAKE_JWT",
        ),
        "private_key_file": _credential(
            secrets,
            "SNOWFLAKE_PRIVATE_KEY_PATH",
            "private_key_file",
            "private_key_path",
        ),
        "warehouse": _credential(secrets, "SNOWFLAKE_WAREHOUSE", "warehouse"),
        "database": _credential(secrets, "SNOWFLAKE_DATABASE", "database"),
    }


def query_snowflake(sql: str) -> pd.DataFrame:
    """Execute SQL against Snowflake and return the result as a DataFrame."""
    import snowflake.connector

    conn = snowflake.connector.connect(**_snowflake_connect_kwargs())
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        return cursor.fetch_pandas_all()
    finally:
        conn.close()


def export_mart_snapshot(
    mart_name: str,
    sql: str | None = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> MartSnapshot:
    """Query a mart from Snowflake and persist it as a local Parquet snapshot."""
    query = sql or f"select * from CS2_ANALYTICS.MARTS.{mart_name}"
    frame = query_snowflake(query)
    path = snapshot_path(mart_name, snapshot_dir=snapshot_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)
    loaded_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return MartSnapshot(name=mart_name, frame=frame, loaded_at=loaded_at, path=path)
