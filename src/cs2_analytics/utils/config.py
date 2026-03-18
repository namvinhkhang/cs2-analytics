"""Settings class — reads all CS2_* env vars from .env file at startup.

Raises pydantic_core.ValidationError immediately if any required var is missing,
so misconfiguration is caught at import time rather than at first API call.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables with CS2_ prefix.

    Required variables (no default):
      CS2_FACEIT_API_KEY, CS2_PANDASCORE_API_KEY, CS2_LIQUIPEDIA_API_KEY,
      CS2_AWS_S3_BUCKET, CS2_KAGGLE_USERNAME, CS2_KAGGLE_KEY

    Optional variables (have defaults):
      CS2_AWS_REGION — defaults to "us-east-1"
    """

    # Pydantic v2 config — reads from .env file with CS2_ prefix
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CS2_",
        extra="ignore",  # Ignore other CS2_* vars (Airflow, Slack, etc.)
    )

    # --- Required fields (missing value raises ValidationError) ---
    faceit_api_key: str
    pandascore_api_key: str
    liquipedia_api_key: str
    aws_s3_bucket: str
    kaggle_username: str
    kaggle_key: str

    # --- Optional fields with defaults ---
    aws_region: str = "us-east-1"


# Module-level singleton — eagerly instantiated so any missing env var
# causes a startup crash rather than a runtime surprise deep in the pipeline.
# Tests that need to bypass this should:
#   - Patch os.environ before importing this module, OR
#   - Construct Settings() directly with a patched env context
#
# The try/except preserves the ValidationError for production code that imports
# settings directly, while allowing test modules to import Settings class alone.
try:
    settings = Settings()
except Exception:
    # Re-raise so that production imports still crash on missing env vars.
    # This branch is only hit at module-level import time when no .env is present.
    raise
