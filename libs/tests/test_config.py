"""Tests for FPLSettings configuration."""

import pytest

from fpl_lib.core.config import FPLSettings


@pytest.mark.unit
class TestFPLSettings:
    def test_default_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENV", raising=False)
        settings = FPLSettings()
        assert settings.ENV == "dev"
        assert settings.AWS_REGION == "eu-west-2"
        assert settings.DATA_LAKE_BUCKET == "fpl-data-lake-dev"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENV", "prod")
        monkeypatch.setenv("DATA_LAKE_BUCKET", "fpl-data-lake-prod")
        settings = FPLSettings()
        assert settings.ENV == "prod"
        assert settings.DATA_LAKE_BUCKET == "fpl-data-lake-prod"

    def test_extra_env_vars_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setenv("UNKNOWN_VAR", "should_not_fail")
        settings = FPLSettings()
        assert settings.ENV == "dev"
