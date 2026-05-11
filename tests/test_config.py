"""Tests for Settings class — verifies CS2_ env prefix, validation, and defaults."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestSettings:
    """Test Settings class behavior."""

    def test_settings_import_succeeds(self) -> None:
        """Settings class is importable."""
        from cs2_analytics.utils.config import Settings  # noqa: F401

    def test_settings_raises_validation_error_when_env_missing(self) -> None:
        """Settings() raises ValidationError when CS2_FACEIT_API_KEY is absent."""
        import pydantic_core

        from cs2_analytics.utils.config import Settings

        # Patch out all env vars and disable .env file to ensure none are set
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(pydantic_core.ValidationError):
                Settings(_env_file=None)

    def test_settings_aws_region_default(self) -> None:
        """settings.aws_region defaults to 'us-east-1' when CS2_AWS_REGION is not set."""
        from cs2_analytics.utils.config import Settings

        env_vars = {
            "CS2_FACEIT_API_KEY": "test_faceit",
            "CS2_PANDASCORE_API_KEY": "test_ps",
            "CS2_AWS_S3_BUCKET": "test-bucket",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            s = Settings(_env_file=None)
            assert s.aws_region == "us-east-1"
            assert s.liquipedia_api_key is None

    def test_settings_keeps_real_liquipedia_key_when_present(self) -> None:
        """settings.liquipedia_api_key keeps a real key when CS2_LIQUIPEDIA_API_KEY is set."""
        from cs2_analytics.utils.config import Settings

        env_vars = {
            "CS2_FACEIT_API_KEY": "test_faceit",
            "CS2_PANDASCORE_API_KEY": "test_ps",
            "CS2_LIQUIPEDIA_API_KEY": "lp_key",
            "CS2_AWS_S3_BUCKET": "test-bucket",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            s = Settings(_env_file=None)
            assert s.liquipedia_api_key == "lp_key"

    def test_settings_treats_liquipedia_placeholder_as_missing(self) -> None:
        """Local placeholder Liquipedia keys should behave like an unconfigured optional source."""
        from cs2_analytics.utils.config import Settings

        env_vars = {
            "CS2_FACEIT_API_KEY": "test_faceit",
            "CS2_PANDASCORE_API_KEY": "test_ps",
            "CS2_LIQUIPEDIA_API_KEY": "your_liquipedia_api_key_here",
            "CS2_AWS_S3_BUCKET": "test-bucket",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            s = Settings(_env_file=None)
            assert s.liquipedia_api_key is None

    def test_settings_reads_env_vars(self) -> None:
        """settings.faceit_api_key returns the value of CS2_FACEIT_API_KEY env var."""
        from cs2_analytics.utils.config import Settings

        env_vars = {
            "CS2_FACEIT_API_KEY": "my_faceit_key_123",
            "CS2_PANDASCORE_API_KEY": "ps_key",
            "CS2_LIQUIPEDIA_API_KEY": "lp_key",
            "CS2_AWS_S3_BUCKET": "my-bucket",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            s = Settings(_env_file=None)
            assert s.faceit_api_key == "my_faceit_key_123"

    def test_settings_custom_aws_region(self) -> None:
        """settings.aws_region is overridable via CS2_AWS_REGION."""
        from cs2_analytics.utils.config import Settings

        env_vars = {
            "CS2_FACEIT_API_KEY": "x",
            "CS2_PANDASCORE_API_KEY": "x",
            "CS2_LIQUIPEDIA_API_KEY": "x",
            "CS2_AWS_S3_BUCKET": "x",
            "CS2_AWS_REGION": "eu-west-1",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            s = Settings(_env_file=None)
            assert s.aws_region == "eu-west-1"
