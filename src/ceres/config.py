from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


class MissingConfigError(Exception):
    pass


@dataclass(frozen=True)
class CeresConfig:
    database_url: str
    anthropic_api_key: Optional[str] = None
    proxy_api_key: Optional[str] = None
    captcha_api_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    max_concurrency: int = 5
    default_rate_limit_ms: int = 2000
    max_retries: int = 3
    screenshot_on_failure: bool = True

    @classmethod
    def from_env(cls, overrides: Optional[dict] = None) -> CeresConfig:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise MissingConfigError(
                "DATABASE_URL environment variable is required"
            )

        kwargs: dict = {
            "database_url": database_url,
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY") or None,
            "proxy_api_key": os.environ.get("PROXY_API_KEY") or None,
            "captcha_api_key": os.environ.get("CAPTCHA_API_KEY") or None,
            "s3_bucket": os.environ.get("S3_BUCKET") or None,
            "s3_access_key": os.environ.get("S3_ACCESS_KEY") or None,
            "s3_secret_key": os.environ.get("S3_SECRET_KEY") or None,
        }

        if overrides:
            crawl = overrides.get("crawl", {})
            if "max_concurrency" in crawl:
                kwargs["max_concurrency"] = crawl["max_concurrency"]
            if "default_rate_limit_ms" in crawl:
                kwargs["default_rate_limit_ms"] = crawl["default_rate_limit_ms"]
            if "max_retries" in crawl:
                kwargs["max_retries"] = crawl["max_retries"]

        return cls(**kwargs)


def load_config(yaml_path: Optional[str] = None) -> CeresConfig:
    overrides: dict = {}
    if yaml_path and Path(yaml_path).exists():
        with open(yaml_path) as f:
            overrides = yaml.safe_load(f) or {}
    return CeresConfig.from_env(overrides)
