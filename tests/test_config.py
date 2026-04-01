import os
from unittest.mock import patch

import pytest

from ceres.config import CeresConfig, load_config, MissingConfigError


class TestCeresConfig:
    def test_from_env_with_required_vars(self):
        env = {"DATABASE_URL": "postgresql://test:pass@host:5432/db"}
        with patch.dict(os.environ, env, clear=True):
            config = CeresConfig.from_env()
        assert config.database_url == "postgresql://test:pass@host:5432/db"
        assert config.anthropic_api_key is None

    def test_from_env_missing_database_url_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(MissingConfigError, match="DATABASE_URL"):
                CeresConfig.from_env()

    def test_optional_vars_default_to_none(self):
        env = {"DATABASE_URL": "postgresql://test:pass@host:5432/db"}
        with patch.dict(os.environ, env, clear=True):
            config = CeresConfig.from_env()
        assert config.proxy_api_key is None
        assert config.captcha_api_key is None

    def test_crawl_settings_defaults(self):
        env = {"DATABASE_URL": "postgresql://test:pass@host:5432/db"}
        with patch.dict(os.environ, env, clear=True):
            config = CeresConfig.from_env()
        assert config.max_concurrency == 5
        assert config.default_rate_limit_ms == 2000
        assert config.max_retries == 3


class TestLoadConfig:
    def test_load_config_merges_yaml_and_env(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("crawl:\n  max_concurrency: 10\n  default_rate_limit_ms: 3000\n")
        env = {"DATABASE_URL": "postgresql://test:pass@host:5432/db"}
        with patch.dict(os.environ, env, clear=True):
            config = load_config(str(yaml_file))
        assert config.max_concurrency == 10
        assert config.default_rate_limit_ms == 3000
