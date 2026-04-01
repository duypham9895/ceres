# CERES Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-healing web crawler system that extracts loan products from 62+ Indonesian banks into a normalized PostgreSQL schema, with daily automated runs and Ringkas business intelligence.

**Architecture:** Six async agents (Scout, Strategist, Crawler, Parser, Learning, Lab) orchestrated by a CLI. Playwright + Undetected ChromeDriver for browser automation. asyncpg for direct Supabase PostgreSQL access. CSS/XPath selectors with Claude API LLM fallback for data extraction.

**Tech Stack:** Python 3.11+, Poetry, asyncpg, Playwright, undetected-chromedriver, anthropic SDK, click, pytest, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-01-ceres-crawler-design.md`

---

## Phase 1: Project Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/ceres/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize Poetry project**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
poetry init --name ceres --description "Indonesian bank loan programs crawler" \
  --author "Edward" --python "^3.11" --no-interaction
```

- [ ] **Step 2: Add dependencies**

```bash
poetry add asyncpg playwright anthropic click pyyaml python-dotenv aiohttp lxml cssselect
poetry add --group dev pytest pytest-asyncio pytest-cov aiosqlite
```

- [ ] **Step 3: Configure pyproject.toml**

Add to `pyproject.toml`:

```toml
[tool.poetry.scripts]
ceres = "ceres.main:cli"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.poetry.packages]
include = "ceres"
from = "src"
```

- [ ] **Step 4: Create .gitignore**

```
__pycache__/
*.pyc
.env
.venv/
dist/
*.egg-info/
.pytest_cache/
htmlcov/
screenshots/
```

- [ ] **Step 5: Create .env.example**

```
DATABASE_URL=postgresql://user:pass@host:port/dbname
ANTHROPIC_API_KEY=sk-ant-...
# Optional:
PROXY_API_KEY=
CAPTCHA_API_KEY=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
```

- [ ] **Step 6: Create src/ceres/__init__.py and tests files**

`src/ceres/__init__.py`:
```python
__version__ = "0.1.0"
```

`tests/__init__.py`: empty file

`tests/conftest.py`:
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_db_pool():
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool, conn
```

- [ ] **Step 7: Create .env with real credentials**

Create `.env` (NOT committed) — copy from `.env.example` and fill in your Supabase connection string and API keys. Never put real credentials in plan or code files.

- [ ] **Step 8: Install and verify**

```bash
poetry install
poetry run python -c "import ceres; print(ceres.__version__)"
```
Expected: `0.1.0`

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/
git commit -m "chore: scaffold CERES project with Poetry"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/ceres/config.py`
- Create: `config/config.yaml`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config loading**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ceres.config'`

- [ ] **Step 3: Implement config module**

`src/ceres/config.py`:
```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
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

        kwargs = {
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
    overrides = {}
    if yaml_path and Path(yaml_path).exists():
        with open(yaml_path) as f:
            overrides = yaml.safe_load(f) or {}
    return CeresConfig.from_env(overrides)
```

`config/config.yaml`:
```yaml
crawl:
  max_concurrency: 5
  default_rate_limit_ms: 2000
  max_retries: 3
```

- [ ] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/test_config.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/config.py config/ tests/test_config.py
git commit -m "feat: add configuration module with env + yaml loading"
```

---

### Task 3: Database Schema & Connection

**Files:**
- Create: `database/schema.sql`
- Create: `src/ceres/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write database schema SQL**

`database/schema.sql`:
```sql
-- CERES Database Schema
-- Run against Supabase PostgreSQL

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Banks table
CREATE TABLE IF NOT EXISTS banks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_code VARCHAR(20) NOT NULL UNIQUE,
    bank_name VARCHAR(200) NOT NULL,
    bank_name_indonesia VARCHAR(200),
    logo_url VARCHAR(500),
    website_url VARCHAR(500),
    is_partner_ringkas BOOLEAN DEFAULT false,
    bank_category VARCHAR(30) NOT NULL CHECK (bank_category IN ('BUMN', 'SWASTA_NASIONAL', 'BPD', 'ASING', 'SYARIAH')),
    bank_type VARCHAR(20) NOT NULL CHECK (bank_type IN ('KONVENSIONAL', 'SYARIAH')),
    website_status VARCHAR(20) DEFAULT 'unknown' CHECK (website_status IN ('active', 'unreachable', 'blocked', 'unknown')),
    api_available BOOLEAN DEFAULT false,
    last_crawled_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    crawl_streak INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER banks_updated_at BEFORE UPDATE ON banks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Bank strategies table
CREATE TABLE IF NOT EXISTS bank_strategies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    version INTEGER DEFAULT 1,
    anti_bot_detected BOOLEAN DEFAULT false,
    anti_bot_type VARCHAR(50),
    bypass_method VARCHAR(50) DEFAULT 'headless_browser',
    selectors JSONB DEFAULT '{}',
    loan_page_urls JSONB DEFAULT '[]',
    rate_limit_ms INTEGER DEFAULT 2000,
    required_headers JSONB DEFAULT '{}',
    user_agent_pattern JSONB,
    proxy_required BOOLEAN DEFAULT false,
    proxy_type VARCHAR(30),
    success_rate DECIMAL(5,4) DEFAULT 0,
    total_attempts INTEGER DEFAULT 0,
    total_successes INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    is_primary BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Only one active primary strategy per bank
CREATE UNIQUE INDEX idx_bank_strategies_primary
    ON bank_strategies (bank_id)
    WHERE is_primary = true AND is_active = true;

CREATE TRIGGER bank_strategies_updated_at BEFORE UPDATE ON bank_strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Loan programs table
CREATE TABLE IF NOT EXISTS loan_programs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    program_name VARCHAR(300) NOT NULL,
    loan_type VARCHAR(30) NOT NULL CHECK (loan_type IN (
        'KPR', 'KPA', 'KPT', 'MULTIGUNA', 'KENDARAAN',
        'MODAL_KERJA', 'INVESTASI', 'PENDIDIKAN', 'PMI',
        'TAKE_OVER', 'REFINANCING', 'OTHER'
    )),
    min_loan_amount DECIMAL(18,2),
    max_loan_amount DECIMAL(18,2),
    min_tenure_months INTEGER,
    max_tenure_months INTEGER,
    min_interest_rate DECIMAL(6,3),
    max_interest_rate DECIMAL(6,3),
    rate_type VARCHAR(10) CHECK (rate_type IN ('FIXED', 'FLOATING', 'MIXED')),
    min_dp_percentage DECIMAL(5,2),
    min_age INTEGER,
    max_age INTEGER,
    min_income DECIMAL(18,2),
    employment_types JSONB DEFAULT '[]',
    collateral_required BOOLEAN,
    collateral_type VARCHAR(100),
    features JSONB DEFAULT '[]',
    special_offers JSONB DEFAULT '[]',
    admin_fee VARCHAR(200),
    provisi_fee VARCHAR(200),
    appraisal_fee VARCHAR(200),
    early_repayment_penalty VARCHAR(200),
    required_documents JSONB DEFAULT '[]',
    available_regions JSONB DEFAULT '"ALL"',
    is_latest BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    data_confidence DECIMAL(3,2) DEFAULT 0,
    completeness_score DECIMAL(3,2) DEFAULT 0,
    raw_data JSONB,
    source_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_loan_programs_bank ON loan_programs(bank_id);
CREATE INDEX idx_loan_programs_type ON loan_programs(loan_type);
CREATE INDEX idx_loan_programs_latest ON loan_programs(bank_id) WHERE is_latest = true;

CREATE TRIGGER loan_programs_updated_at BEFORE UPDATE ON loan_programs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Crawl logs table
CREATE TABLE IF NOT EXISTS crawl_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    strategy_id UUID REFERENCES bank_strategies(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status VARCHAR(20) DEFAULT 'queued' CHECK (status IN (
        'queued', 'running', 'success', 'partial', 'failed', 'blocked', 'timeout'
    )),
    programs_found INTEGER DEFAULT 0,
    programs_new INTEGER DEFAULT 0,
    programs_updated INTEGER DEFAULT 0,
    error_type VARCHAR(100),
    error_message TEXT,
    anti_bot_detected BOOLEAN DEFAULT false,
    screenshot_url TEXT,
    html_sample TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_crawl_logs_bank ON crawl_logs(bank_id);
CREATE INDEX idx_crawl_logs_status ON crawl_logs(status);
CREATE INDEX idx_crawl_logs_started ON crawl_logs(started_at DESC);

-- Crawl raw data (handoff between Crawler and Parser)
CREATE TABLE IF NOT EXISTS crawl_raw_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    crawl_log_id UUID NOT NULL REFERENCES crawl_logs(id) ON DELETE CASCADE,
    bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE CASCADE,
    page_url VARCHAR(500) NOT NULL,
    raw_html TEXT NOT NULL,
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    parsed BOOLEAN DEFAULT false
);

CREATE INDEX idx_crawl_raw_data_unparsed ON crawl_raw_data(bank_id) WHERE parsed = false;

-- Strategy feedback table
CREATE TABLE IF NOT EXISTS strategy_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id UUID NOT NULL REFERENCES bank_strategies(id) ON DELETE CASCADE,
    test_approach VARCHAR(50) NOT NULL,
    result VARCHAR(20) NOT NULL CHECK (result IN ('success', 'partial', 'failure')),
    improvement_score DECIMAL(3,2),
    recommended_changes JSONB DEFAULT '{}',
    applied BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategy_feedback_strategy ON strategy_feedback(strategy_id);

-- Ringkas recommendations table
CREATE TABLE IF NOT EXISTS ringkas_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rec_type VARCHAR(30) NOT NULL CHECK (rec_type IN (
        'partnership_opportunity', 'product_gap',
        'competitive_analysis', 'pricing', 'market_trend'
    )),
    priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    impact_score DECIMAL(3,2),
    title VARCHAR(300) NOT NULL,
    summary TEXT,
    detailed_analysis TEXT,
    suggested_actions JSONB DEFAULT '[]',
    related_bank_ids JSONB DEFAULT '[]',
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'reviewed', 'approved', 'implemented', 'dismissed'
    )),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER recommendations_updated_at BEFORE UPDATE ON ringkas_recommendations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Proxies table
CREATE TABLE IF NOT EXISTS proxies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    proxy_url VARCHAR(500) NOT NULL,
    proxy_type VARCHAR(20) DEFAULT 'datacenter' CHECK (proxy_type IN ('residential', 'datacenter', 'mobile')),
    country VARCHAR(5) DEFAULT 'ID',
    avg_response_ms INTEGER,
    success_rate DECIMAL(5,4) DEFAULT 1.0,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'rate_limited', 'banned', 'expired')),
    rotation_enabled BOOLEAN DEFAULT true,
    rotation_weight DECIMAL(3,2) DEFAULT 1.0,
    last_used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER proxies_updated_at BEFORE UPDATE ON proxies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

- [ ] **Step 2: Write failing test for database module**

`tests/test_database.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ceres.database import Database


class TestDatabase:
    @pytest.mark.asyncio
    async def test_connect_creates_pool(self):
        with patch("ceres.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            mock_pool.return_value = AsyncMock()
            db = Database("postgresql://test:pass@host:5432/db")
            await db.connect()
            mock_pool.assert_called_once()
            assert db.pool is not None

    @pytest.mark.asyncio
    async def test_disconnect_closes_pool(self):
        with patch("ceres.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            pool_instance = AsyncMock()
            mock_pool.return_value = pool_instance
            db = Database("postgresql://test:pass@host:5432/db")
            await db.connect()
            await db.disconnect()
            pool_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_banks_returns_list(self):
        with patch("ceres.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            pool_instance = AsyncMock()
            pool_instance.fetch = AsyncMock(return_value=[
                {"id": "uuid1", "bank_code": "BCA", "bank_name": "Bank Central Asia"}
            ])
            mock_pool.return_value = pool_instance
            db = Database("postgresql://test:pass@host:5432/db")
            await db.connect()
            banks = await db.fetch_banks()
            assert len(banks) == 1
            assert banks[0]["bank_code"] == "BCA"

    @pytest.mark.asyncio
    async def test_fetch_active_strategies_filters_active(self):
        with patch("ceres.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            pool_instance = AsyncMock()
            pool_instance.fetch = AsyncMock(return_value=[])
            mock_pool.return_value = pool_instance
            db = Database("postgresql://test:pass@host:5432/db")
            await db.connect()
            strategies = await db.fetch_active_strategies()
            call_args = pool_instance.fetch.call_args[0][0]
            assert "is_active = true" in call_args
            assert "is_primary = true" in call_args

    @pytest.mark.asyncio
    async def test_upsert_bank_creates_or_updates(self):
        with patch("ceres.database.asyncpg.create_pool", new_callable=AsyncMock) as mock_pool:
            pool_instance = AsyncMock()
            pool_instance.fetchrow = AsyncMock(return_value={"id": "uuid1"})
            mock_pool.return_value = pool_instance
            db = Database("postgresql://test:pass@host:5432/db")
            await db.connect()
            result = await db.upsert_bank(
                bank_code="BCA",
                bank_name="Bank Central Asia",
                website_url="https://bca.co.id",
                bank_category="SWASTA_NASIONAL",
                bank_type="KONVENSIONAL",
            )
            assert result["id"] == "uuid1"
            call_sql = pool_instance.fetchrow.call_args[0][0]
            assert "ON CONFLICT" in call_sql
```

- [ ] **Step 3: Run test to verify it fails**

```bash
poetry run pytest tests/test_database.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ceres.database'`

- [ ] **Step 4: Implement database module**

`src/ceres/database.py`:
```python
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import asyncpg


class Database:
    def __init__(self, database_url: str, min_pool: int = 2, max_pool: int = 10):
        self._database_url = database_url
        self._min_pool = min_pool
        self._max_pool = max_pool
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self._database_url,
            min_size=self._min_pool,
            max_size=self._max_pool,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()

    # ── Bank queries ──

    async def fetch_banks(self, status: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM banks"
        args = []
        if status:
            query += " WHERE website_status = $1"
            args.append(status)
        query += " ORDER BY bank_code"
        rows = await self.pool.fetch(query, *args)
        return [dict(r) for r in rows]

    async def upsert_bank(self, *, bank_code: str, bank_name: str,
                          website_url: str, bank_category: str,
                          bank_type: str, **kwargs) -> dict:
        sql = """
            INSERT INTO banks (bank_code, bank_name, website_url, bank_category, bank_type)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (bank_code) DO UPDATE SET
                bank_name = EXCLUDED.bank_name,
                website_url = EXCLUDED.website_url,
                updated_at = NOW()
            RETURNING id, bank_code
        """
        row = await self.pool.fetchrow(
            sql, bank_code, bank_name, website_url, bank_category, bank_type
        )
        return dict(row)

    async def update_bank_status(self, bank_id: str, status: str,
                                 last_crawled: bool = False) -> None:
        parts = ["website_status = $2"]
        args: list[Any] = [bank_id, status]
        if last_crawled:
            parts.append("last_crawled_at = NOW()")
        sql = f"UPDATE banks SET {', '.join(parts)} WHERE id = $1"
        await self.pool.execute(sql, *args)

    # ── Strategy queries ──

    async def fetch_active_strategies(self, bank_id: Optional[str] = None) -> list[dict]:
        query = """
            SELECT bs.*, b.bank_code, b.bank_name, b.website_url
            FROM bank_strategies bs
            JOIN banks b ON bs.bank_id = b.id
            WHERE bs.is_active = true AND bs.is_primary = true
        """
        args = []
        if bank_id:
            query += " AND bs.bank_id = $1"
            args.append(bank_id)
        query += " ORDER BY b.bank_code"
        rows = await self.pool.fetch(query, *args)
        return [dict(r) for r in rows]

    async def upsert_strategy(self, *, bank_id: str, selectors: dict,
                              loan_page_urls: list[str],
                              bypass_method: str = "headless_browser",
                              anti_bot_detected: bool = False,
                              anti_bot_type: Optional[str] = None,
                              rate_limit_ms: int = 2000) -> dict:
        sql = """
            INSERT INTO bank_strategies
                (bank_id, selectors, loan_page_urls, bypass_method,
                 anti_bot_detected, anti_bot_type, rate_limit_ms)
            VALUES ($1, $2::jsonb, $3::jsonb, $4, $5, $6, $7)
            ON CONFLICT (bank_id) WHERE (is_primary = true AND is_active = true)
            DO UPDATE SET
                selectors = EXCLUDED.selectors,
                loan_page_urls = EXCLUDED.loan_page_urls,
                bypass_method = EXCLUDED.bypass_method,
                anti_bot_detected = EXCLUDED.anti_bot_detected,
                anti_bot_type = EXCLUDED.anti_bot_type,
                rate_limit_ms = EXCLUDED.rate_limit_ms,
                version = bank_strategies.version + 1,
                updated_at = NOW()
            RETURNING id, bank_id, version
        """
        row = await self.pool.fetchrow(
            sql, bank_id, json.dumps(selectors), json.dumps(loan_page_urls),
            bypass_method, anti_bot_detected, anti_bot_type, rate_limit_ms
        )
        return dict(row)

    # ── Crawl log queries ──

    async def create_crawl_log(self, *, bank_id: str, strategy_id: str) -> str:
        sql = """
            INSERT INTO crawl_logs (bank_id, strategy_id, status, started_at)
            VALUES ($1, $2, 'running', NOW())
            RETURNING id
        """
        row = await self.pool.fetchrow(sql, bank_id, strategy_id)
        return str(row["id"])

    async def update_crawl_log(self, log_id: str, *, status: str,
                               programs_found: int = 0, programs_new: int = 0,
                               programs_updated: int = 0,
                               error_type: Optional[str] = None,
                               error_message: Optional[str] = None,
                               anti_bot_detected: bool = False) -> None:
        sql = """
            UPDATE crawl_logs SET
                status = $2, completed_at = NOW(),
                duration_ms = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER * 1000,
                programs_found = $3, programs_new = $4, programs_updated = $5,
                error_type = $6, error_message = $7, anti_bot_detected = $8
            WHERE id = $1
        """
        await self.pool.execute(
            sql, log_id, status, programs_found, programs_new,
            programs_updated, error_type, error_message, anti_bot_detected
        )

    # ── Raw data queries ──

    async def store_raw_html(self, *, crawl_log_id: str, bank_id: str,
                             page_url: str, raw_html: str) -> str:
        sql = """
            INSERT INTO crawl_raw_data (crawl_log_id, bank_id, page_url, raw_html)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        row = await self.pool.fetchrow(sql, crawl_log_id, bank_id, page_url, raw_html)
        return str(row["id"])

    async def fetch_unparsed_html(self, bank_id: Optional[str] = None) -> list[dict]:
        query = """
            SELECT crd.*, b.bank_code, b.bank_name, bs.selectors
            FROM crawl_raw_data crd
            JOIN banks b ON crd.bank_id = b.id
            LEFT JOIN crawl_logs cl ON crd.crawl_log_id = cl.id
            LEFT JOIN bank_strategies bs ON cl.strategy_id = bs.id
            WHERE crd.parsed = false
        """
        args = []
        if bank_id:
            query += " AND crd.bank_id = $1"
            args.append(bank_id)
        query += " ORDER BY crd.extracted_at"
        rows = await self.pool.fetch(query, *args)
        return [dict(r) for r in rows]

    async def mark_parsed(self, raw_data_id: str) -> None:
        await self.pool.execute(
            "UPDATE crawl_raw_data SET parsed = true WHERE id = $1", raw_data_id
        )

    # ── Loan program queries ──

    async def upsert_loan_program(self, *, bank_id: str, program_name: str,
                                  loan_type: str, source_url: str,
                                  data_confidence: float,
                                  completeness_score: float,
                                  raw_data: dict, **fields) -> dict:
        # Mark previous versions as not latest
        await self.pool.execute(
            """UPDATE loan_programs SET is_latest = false
               WHERE bank_id = $1 AND program_name = $2 AND is_latest = true""",
            bank_id, program_name
        )

        columns = [
            "bank_id", "program_name", "loan_type", "source_url",
            "data_confidence", "completeness_score", "raw_data"
        ]
        values = [bank_id, program_name, loan_type, source_url,
                  data_confidence, completeness_score, json.dumps(raw_data)]

        valid_fields = {
            "min_loan_amount", "max_loan_amount", "min_tenure_months",
            "max_tenure_months", "min_interest_rate", "max_interest_rate",
            "rate_type", "min_dp_percentage", "min_age", "max_age",
            "min_income", "collateral_required", "collateral_type",
            "admin_fee", "provisi_fee", "appraisal_fee",
            "early_repayment_penalty",
        }
        json_fields = {
            "employment_types", "features", "special_offers",
            "required_documents", "available_regions",
        }

        for k, v in fields.items():
            if k in valid_fields and v is not None:
                columns.append(k)
                values.append(v)
            elif k in json_fields and v is not None:
                columns.append(k)
                values.append(json.dumps(v))

        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        col_names = ", ".join(columns)

        sql = f"""
            INSERT INTO loan_programs ({col_names})
            VALUES ({placeholders})
            RETURNING id, program_name, loan_type
        """
        row = await self.pool.fetchrow(sql, *values)
        return dict(row)

    async def fetch_loan_programs(self, bank_id: Optional[str] = None,
                                  loan_type: Optional[str] = None,
                                  latest_only: bool = True) -> list[dict]:
        query = "SELECT lp.*, b.bank_code, b.bank_name FROM loan_programs lp JOIN banks b ON lp.bank_id = b.id WHERE 1=1"
        args = []
        idx = 1
        if latest_only:
            query += " AND lp.is_latest = true"
        if bank_id:
            query += f" AND lp.bank_id = ${idx}"
            args.append(bank_id)
            idx += 1
        if loan_type:
            query += f" AND lp.loan_type = ${idx}"
            args.append(loan_type)
            idx += 1
        query += " ORDER BY b.bank_code, lp.program_name"
        rows = await self.pool.fetch(query, *args)
        return [dict(r) for r in rows]

    # ── Strategy feedback queries ──

    async def add_strategy_feedback(self, *, strategy_id: str,
                                    test_approach: str, result: str,
                                    improvement_score: float = 0,
                                    recommended_changes: Optional[dict] = None) -> str:
        sql = """
            INSERT INTO strategy_feedback
                (strategy_id, test_approach, result, improvement_score, recommended_changes)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            RETURNING id
        """
        row = await self.pool.fetchrow(
            sql, strategy_id, test_approach, result,
            improvement_score, json.dumps(recommended_changes or {})
        )
        return str(row["id"])

    # ── Recommendation queries ──

    async def add_recommendation(self, *, rec_type: str, priority: int,
                                 impact_score: float, title: str,
                                 summary: str, detailed_analysis: str = "",
                                 suggested_actions: Optional[list] = None,
                                 related_bank_ids: Optional[list] = None) -> str:
        sql = """
            INSERT INTO ringkas_recommendations
                (rec_type, priority, impact_score, title, summary,
                 detailed_analysis, suggested_actions, related_bank_ids)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
            RETURNING id
        """
        row = await self.pool.fetchrow(
            sql, rec_type, priority, impact_score, title, summary,
            detailed_analysis, json.dumps(suggested_actions or []),
            json.dumps(related_bank_ids or [])
        )
        return str(row["id"])

    # ── Stats queries ──

    async def get_crawl_stats(self, days: int = 7) -> dict:
        sql = """
            SELECT
                COUNT(*) as total_crawls,
                COUNT(*) FILTER (WHERE status = 'success') as successes,
                COUNT(*) FILTER (WHERE status = 'failed') as failures,
                COUNT(*) FILTER (WHERE status = 'blocked') as blocked,
                COUNT(DISTINCT bank_id) as banks_crawled,
                SUM(programs_found) as total_programs_found
            FROM crawl_logs
            WHERE started_at > NOW() - ($1 || ' days')::INTERVAL
        """
        row = await self.pool.fetchrow(sql, str(days))
        return dict(row)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
poetry run pytest tests/test_database.py -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add database/schema.sql src/ceres/database.py tests/test_database.py
git commit -m "feat: add database schema and async database module"
```

---

### Task 4: Domain Models

**Files:**
- Create: `src/ceres/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for models**

`tests/test_models.py`:
```python
from ceres.models import (
    Bank, BankCategory, BankType, LoanType, CrawlStatus,
    LoanProgram, CrawlLog, Strategy,
    calculate_completeness_score,
)


class TestBank:
    def test_bank_creation(self):
        bank = Bank(
            bank_code="BCA",
            bank_name="Bank Central Asia",
            website_url="https://bca.co.id",
            bank_category=BankCategory.SWASTA_NASIONAL,
            bank_type=BankType.KONVENSIONAL,
        )
        assert bank.bank_code == "BCA"
        assert bank.is_partner_ringkas is False

    def test_bank_is_frozen(self):
        bank = Bank(
            bank_code="BCA",
            bank_name="Bank Central Asia",
            website_url="https://bca.co.id",
            bank_category=BankCategory.SWASTA_NASIONAL,
            bank_type=BankType.KONVENSIONAL,
        )
        try:
            bank.bank_code = "NEW"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestCompletenessScore:
    def test_full_data_scores_high(self):
        data = {
            "program_name": "KPR BCA",
            "loan_type": "KPR",
            "min_interest_rate": 3.5,
            "max_interest_rate": 7.0,
            "min_loan_amount": 100_000_000,
            "max_loan_amount": 5_000_000_000,
            "min_tenure_months": 12,
            "max_tenure_months": 300,
            "rate_type": "MIXED",
            "min_dp_percentage": 10,
        }
        score = calculate_completeness_score(data)
        assert score >= 0.8

    def test_minimal_data_scores_low(self):
        data = {"program_name": "KPR BCA", "loan_type": "KPR"}
        score = calculate_completeness_score(data)
        assert score < 0.5

    def test_empty_data_scores_zero(self):
        score = calculate_completeness_score({})
        assert score == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_models.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement models**

`src/ceres/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID


class BankCategory(str, Enum):
    BUMN = "BUMN"
    SWASTA_NASIONAL = "SWASTA_NASIONAL"
    BPD = "BPD"
    ASING = "ASING"
    SYARIAH = "SYARIAH"


class BankType(str, Enum):
    KONVENSIONAL = "KONVENSIONAL"
    SYARIAH = "SYARIAH"


class LoanType(str, Enum):
    KPR = "KPR"
    KPA = "KPA"
    KPT = "KPT"
    MULTIGUNA = "MULTIGUNA"
    KENDARAAN = "KENDARAAN"
    MODAL_KERJA = "MODAL_KERJA"
    INVESTASI = "INVESTASI"
    PENDIDIKAN = "PENDIDIKAN"
    PMI = "PMI"
    TAKE_OVER = "TAKE_OVER"
    REFINANCING = "REFINANCING"
    OTHER = "OTHER"


class CrawlStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


class WebsiteStatus(str, Enum):
    ACTIVE = "active"
    UNREACHABLE = "unreachable"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class BypassMethod(str, Enum):
    HEADLESS_BROWSER = "headless_browser"
    API = "api"
    PROXY_POOL = "proxy_pool"
    UNDETECTED_CHROME = "undetected_chrome"
    MANUAL = "manual"


@dataclass(frozen=True)
class Bank:
    bank_code: str
    bank_name: str
    website_url: str
    bank_category: BankCategory
    bank_type: BankType
    id: Optional[str] = None
    bank_name_indonesia: Optional[str] = None
    logo_url: Optional[str] = None
    is_partner_ringkas: bool = False
    website_status: WebsiteStatus = WebsiteStatus.UNKNOWN
    api_available: bool = False
    last_crawled_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    crawl_streak: int = 0


@dataclass(frozen=True)
class Strategy:
    bank_id: str
    selectors: dict = field(default_factory=dict)
    loan_page_urls: list[str] = field(default_factory=list)
    id: Optional[str] = None
    version: int = 1
    anti_bot_detected: bool = False
    anti_bot_type: Optional[str] = None
    bypass_method: BypassMethod = BypassMethod.HEADLESS_BROWSER
    rate_limit_ms: int = 2000
    required_headers: dict = field(default_factory=dict)
    proxy_required: bool = False
    success_rate: float = 0.0
    is_active: bool = True
    is_primary: bool = True


@dataclass(frozen=True)
class LoanProgram:
    bank_id: str
    program_name: str
    loan_type: LoanType
    source_url: str
    id: Optional[str] = None
    min_loan_amount: Optional[float] = None
    max_loan_amount: Optional[float] = None
    min_tenure_months: Optional[int] = None
    max_tenure_months: Optional[int] = None
    min_interest_rate: Optional[float] = None
    max_interest_rate: Optional[float] = None
    rate_type: Optional[str] = None
    min_dp_percentage: Optional[float] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    min_income: Optional[float] = None
    data_confidence: float = 0.0
    completeness_score: float = 0.0
    raw_data: Optional[dict] = None


@dataclass(frozen=True)
class CrawlLog:
    bank_id: str
    strategy_id: str
    id: Optional[str] = None
    status: CrawlStatus = CrawlStatus.QUEUED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    programs_found: int = 0
    programs_new: int = 0
    programs_updated: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    anti_bot_detected: bool = False


# Expected fields for completeness scoring
_EXPECTED_FIELDS = [
    "program_name", "loan_type", "min_interest_rate", "max_interest_rate",
    "min_loan_amount", "max_loan_amount", "min_tenure_months",
    "max_tenure_months", "rate_type", "min_dp_percentage",
]


def calculate_completeness_score(data: dict) -> float:
    if not data:
        return 0.0
    filled = sum(1 for f in _EXPECTED_FIELDS if data.get(f) is not None)
    return round(filled / len(_EXPECTED_FIELDS), 2)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/test_models.py -v
```
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ceres/models.py tests/test_models.py
git commit -m "feat: add domain models with enums and completeness scoring"
```

---

## Phase 2: Browser & Extraction Layer

### Task 5: Browser Manager (Playwright + UC ChromeDriver)

**Files:**
- Create: `src/ceres/browser/__init__.py`
- Create: `src/ceres/browser/manager.py`
- Create: `src/ceres/browser/stealth.py`
- Create: `tests/test_browser.py`

- [ ] **Step 1: Write failing test**

`tests/test_browser.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot, AntiBotResult


class TestBrowserManager:
    @pytest.mark.asyncio
    async def test_create_playwright_context(self):
        manager = BrowserManager()
        with patch.object(manager, "_launch_playwright", new_callable=AsyncMock) as mock:
            mock.return_value = (AsyncMock(), AsyncMock())
            browser, page = await manager.create_context(BrowserType.PLAYWRIGHT)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_undetected_context(self):
        manager = BrowserManager()
        with patch.object(manager, "_launch_undetected", new_callable=AsyncMock) as mock:
            mock.return_value = (MagicMock(), MagicMock())
            browser, page = await manager.create_context(BrowserType.UNDETECTED)
            mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_playwright_context(self):
        manager = BrowserManager()
        browser = AsyncMock()
        await manager.close_context(browser, BrowserType.PLAYWRIGHT)
        browser.close.assert_called_once()


class TestAntiBotDetection:
    def test_detect_cloudflare(self):
        html = '<div class="cf-browser-verification">Checking your browser</div>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "cloudflare"

    def test_detect_recaptcha(self):
        html = '<div class="g-recaptcha" data-sitekey="xxx"></div>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "recaptcha"

    def test_no_anti_bot(self):
        html = "<html><body><h1>Welcome to Bank XYZ</h1></body></html>"
        result = detect_anti_bot(html)
        assert result.detected is False

    def test_detect_datadome(self):
        html = '<script src="https://js.datadome.co/tags.js"></script>'
        result = detect_anti_bot(html)
        assert result.detected is True
        assert result.anti_bot_type == "datadome"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_browser.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement stealth module**

`src/ceres/browser/__init__.py`: empty

`src/ceres/browser/stealth.py`:
```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AntiBotResult:
    detected: bool
    anti_bot_type: str | None = None
    details: str | None = None


_PATTERNS = [
    (r"cf-browser-verification|cf-challenge|cloudflare", "cloudflare"),
    (r"g-recaptcha|recaptcha/api", "recaptcha"),
    (r"datadome\.co|dd\.js", "datadome"),
    (r"fingerprint2|fingerprintjs|fp\.min\.js", "fingerprint"),
    (r"challenge-platform|hcaptcha", "custom_js"),
]


def detect_anti_bot(html: str) -> AntiBotResult:
    html_lower = html.lower()
    for pattern, bot_type in _PATTERNS:
        if re.search(pattern, html_lower):
            return AntiBotResult(
                detected=True,
                anti_bot_type=bot_type,
                details=f"Detected {bot_type} pattern",
            )
    return AntiBotResult(detected=False)


STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--disable-gpu",
]

STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
```

- [ ] **Step 4: Implement browser manager**

`src/ceres/browser/manager.py`:
```python
from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Optional

from ceres.browser.stealth import STEALTH_ARGS, STEALTH_UA


class BrowserType(str, Enum):
    PLAYWRIGHT = "playwright"
    UNDETECTED = "undetected"


class BrowserManager:
    def __init__(self, proxy: Optional[str] = None):
        self._proxy = proxy

    async def create_context(
        self, browser_type: BrowserType = BrowserType.PLAYWRIGHT, **kwargs
    ) -> tuple[Any, Any]:
        if browser_type == BrowserType.PLAYWRIGHT:
            return await self._launch_playwright(**kwargs)
        return await self._launch_undetected(**kwargs)

    async def _launch_playwright(self, **kwargs) -> tuple[Any, Any]:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        launch_args = {
            "headless": True,
            "args": STEALTH_ARGS,
        }
        if self._proxy:
            launch_args["proxy"] = {"server": self._proxy}

        browser = await pw.chromium.launch(**launch_args)
        context = await browser.new_context(
            user_agent=STEALTH_UA,
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )
        # Stealth: remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        """)
        page = await context.new_page()
        return browser, page

    async def _launch_undetected(self, **kwargs) -> tuple[Any, Any]:
        import undetected_chromedriver as uc

        loop = asyncio.get_event_loop()
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        for arg in STEALTH_ARGS:
            options.add_argument(arg)

        if self._proxy:
            options.add_argument(f"--proxy-server={self._proxy}")

        driver = await loop.run_in_executor(
            None, lambda: uc.Chrome(options=options)
        )
        return driver, driver

    async def close_context(self, browser: Any, browser_type: BrowserType) -> None:
        if browser_type == BrowserType.PLAYWRIGHT:
            await browser.close()
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, browser.quit)
```

- [ ] **Step 5: Run tests**

```bash
poetry run pytest tests/test_browser.py -v
```
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/ceres/browser/ tests/test_browser.py
git commit -m "feat: add browser manager with Playwright + UC ChromeDriver and anti-bot detection"
```

---

### Task 6: Proxy & CAPTCHA Stubs

**Files:**
- Create: `src/ceres/browser/proxy.py`
- Create: `src/ceres/utils/__init__.py`
- Create: `src/ceres/utils/captcha.py`
- Create: `tests/test_proxy_captcha.py`

- [ ] **Step 1: Write failing test**

`tests/test_proxy_captcha.py`:
```python
import pytest
from ceres.browser.proxy import NoOpProxyProvider, ProxyProvider
from ceres.utils.captcha import NoOpCaptchaSolver, CaptchaSolver


class TestNoOpProxy:
    @pytest.mark.asyncio
    async def test_get_proxy_returns_none(self):
        provider = NoOpProxyProvider()
        proxy = await provider.get_proxy()
        assert proxy is None

    @pytest.mark.asyncio
    async def test_report_result_is_noop(self):
        provider = NoOpProxyProvider()
        await provider.report_result("http://proxy:8080", True)  # Should not raise

    def test_implements_interface(self):
        assert isinstance(NoOpProxyProvider(), ProxyProvider)


class TestNoOpCaptcha:
    @pytest.mark.asyncio
    async def test_solve_returns_none(self):
        solver = NoOpCaptchaSolver()
        result = await solver.solve("recaptcha", "https://example.com")
        assert result is None

    def test_implements_interface(self):
        assert isinstance(NoOpCaptchaSolver(), CaptchaSolver)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_proxy_captcha.py -v
```

- [ ] **Step 3: Implement stubs**

`src/ceres/browser/proxy.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ProxyProvider(ABC):
    @abstractmethod
    async def get_proxy(self) -> Optional[str]:
        ...

    @abstractmethod
    async def report_result(self, proxy: str, success: bool) -> None:
        ...


class NoOpProxyProvider(ProxyProvider):
    async def get_proxy(self) -> Optional[str]:
        return None

    async def report_result(self, proxy: str, success: bool) -> None:
        pass
```

`src/ceres/utils/__init__.py`: empty

`src/ceres/utils/captcha.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CaptchaSolver(ABC):
    @abstractmethod
    async def solve(self, challenge_type: str, page_url: str) -> Optional[str]:
        ...


class NoOpCaptchaSolver(CaptchaSolver):
    async def solve(self, challenge_type: str, page_url: str) -> Optional[str]:
        return None
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_proxy_captcha.py -v
git add src/ceres/browser/proxy.py src/ceres/utils/ tests/test_proxy_captcha.py
git commit -m "feat: add proxy and CAPTCHA solver interfaces with no-op stubs"
```

---

### Task 7: Selector Extractor & Normalizer

**Files:**
- Create: `src/ceres/extractors/__init__.py`
- Create: `src/ceres/extractors/selector.py`
- Create: `src/ceres/extractors/normalizer.py`
- Create: `tests/test_extractors.py`
- Create: `tests/test_normalizer.py`

- [ ] **Step 1: Write failing test for selector extractor**

`tests/test_extractors.py`:
```python
import pytest
from ceres.extractors.selector import SelectorExtractor, ExtractionResult


class TestSelectorExtractor:
    def test_extract_with_css_selector(self):
        html = """
        <div class="product-card">
            <h3 class="title">KPR BCA</h3>
            <span class="rate">3.5% - 7.0%</span>
        </div>
        """
        selectors = {
            "container": "div.product-card",
            "fields": {
                "name": "h3.title",
                "rate": "span.rate",
            }
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert len(results) == 1
        assert results[0].fields["name"] == "KPR BCA"
        assert results[0].fields["rate"] == "3.5% - 7.0%"

    def test_extract_multiple_products(self):
        html = """
        <div class="product"><h3>Product A</h3></div>
        <div class="product"><h3>Product B</h3></div>
        """
        selectors = {
            "container": "div.product",
            "fields": {"name": "h3"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert len(results) == 2
        assert results[0].fields["name"] == "Product A"
        assert results[1].fields["name"] == "Product B"

    def test_extract_with_missing_field_returns_none(self):
        html = '<div class="product"><h3>Product A</h3></div>'
        selectors = {
            "container": "div.product",
            "fields": {"name": "h3", "rate": "span.rate"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert results[0].fields["name"] == "Product A"
        assert results[0].fields["rate"] is None

    def test_confidence_score_based_on_fields_found(self):
        html = '<div class="p"><h3>Name</h3></div>'
        selectors = {
            "container": "div.p",
            "fields": {"name": "h3", "rate": "span.r", "amount": "span.a"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        # 1 of 3 fields found → ~0.33
        assert results[0].confidence < 0.5

    def test_empty_html_returns_empty(self):
        extractor = SelectorExtractor()
        results = extractor.extract("", {"container": "div", "fields": {}})
        assert results == []
```

- [ ] **Step 2: Write failing test for normalizer**

`tests/test_normalizer.py`:
```python
from ceres.extractors.normalizer import normalize_rate, normalize_amount, normalize_loan_type, normalize_tenure


class TestNormalizeRate:
    def test_range_format(self):
        assert normalize_rate("3.5% - 7.0%") == (3.5, 7.0)

    def test_single_rate(self):
        assert normalize_rate("5.25%") == (5.25, 5.25)

    def test_indonesian_format(self):
        assert normalize_rate("Bunga 3,5% s.d. 7,0%") == (3.5, 7.0)

    def test_per_annum(self):
        assert normalize_rate("6.5% p.a.") == (6.5, 6.5)

    def test_invalid_returns_none(self):
        assert normalize_rate("Contact us") == (None, None)


class TestNormalizeAmount:
    def test_rupiah_billions(self):
        assert normalize_amount("Rp 500 Juta - 5 Miliar") == (500_000_000, 5_000_000_000)

    def test_numeric_format(self):
        assert normalize_amount("100.000.000 - 5.000.000.000") == (100_000_000, 5_000_000_000)

    def test_single_amount(self):
        result = normalize_amount("Rp 1 Miliar")
        assert result[0] == 1_000_000_000 or result[1] == 1_000_000_000


class TestNormalizeLoanType:
    def test_kpr_keywords(self):
        assert normalize_loan_type("Kredit Pemilikan Rumah") == "KPR"
        assert normalize_loan_type("KPR BCA") == "KPR"

    def test_kpa_keywords(self):
        assert normalize_loan_type("Kredit Pemilikan Apartemen") == "KPA"

    def test_multiguna(self):
        assert normalize_loan_type("Kredit Multiguna") == "MULTIGUNA"

    def test_kendaraan(self):
        assert normalize_loan_type("Kredit Kendaraan Bermotor") == "KENDARAAN"

    def test_unknown_returns_other(self):
        assert normalize_loan_type("Special Product XYZ") == "OTHER"


class TestNormalizeTenure:
    def test_years_format(self):
        assert normalize_tenure("1 - 25 tahun") == (12, 300)

    def test_months_format(self):
        assert normalize_tenure("12 - 360 bulan") == (12, 360)

    def test_single_max(self):
        assert normalize_tenure("Maks. 20 tahun") == (None, 240)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
poetry run pytest tests/test_extractors.py tests/test_normalizer.py -v
```

- [ ] **Step 4: Implement selector extractor**

`src/ceres/extractors/__init__.py`: empty

`src/ceres/extractors/selector.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lxml import html as lxml_html


@dataclass(frozen=True)
class ExtractionResult:
    fields: dict[str, Optional[str]]
    confidence: float


class SelectorExtractor:
    def extract(self, raw_html: str, selectors: dict) -> list[ExtractionResult]:
        if not raw_html or not selectors.get("fields"):
            return []

        try:
            tree = lxml_html.fromstring(raw_html)
        except Exception:
            return []

        container_sel = selectors.get("container", "body")
        containers = tree.cssselect(container_sel)

        if not containers:
            return []

        field_defs = selectors["fields"]
        results = []

        for container in containers:
            fields: dict[str, Optional[str]] = {}
            found_count = 0

            for field_name, css_sel in field_defs.items():
                elements = container.cssselect(css_sel)
                if elements:
                    text = elements[0].text_content().strip()
                    fields[field_name] = text if text else None
                    if text:
                        found_count += 1
                else:
                    fields[field_name] = None

            total_fields = len(field_defs)
            confidence = found_count / total_fields if total_fields > 0 else 0.0

            results.append(ExtractionResult(
                fields=fields,
                confidence=round(confidence, 2),
            ))

        return results
```

- [ ] **Step 5: Implement normalizer**

`src/ceres/extractors/normalizer.py`:
```python
from __future__ import annotations

import re
from typing import Optional


def normalize_rate(text: str) -> tuple[Optional[float], Optional[float]]:
    if not text:
        return (None, None)

    # Replace Indonesian decimal comma with dot
    cleaned = text.replace(",", ".")

    # Find all decimal numbers
    numbers = re.findall(r"(\d+\.?\d*)\s*%?", cleaned)

    if not numbers:
        return (None, None)

    floats = [float(n) for n in numbers if 0 < float(n) < 100]

    if not floats:
        return (None, None)
    if len(floats) == 1:
        return (floats[0], floats[0])
    return (min(floats), max(floats))


def normalize_amount(text: str) -> tuple[Optional[float], Optional[float]]:
    if not text:
        return (None, None)

    cleaned = text.lower().replace("rp", "").strip()

    # Handle "Juta" (million) and "Miliar" (billion) — support decimals like "1.5 Miliar"
    juta_pattern = r"(\d+[.,]?\d*)\s*juta"
    miliar_pattern = r"(\d+[.,]?\d*)\s*miliar"

    amounts = []

    for match in re.finditer(miliar_pattern, cleaned):
        val = float(match.group(1).replace(",", "."))
        amounts.append(int(val * 1_000_000_000))
    for match in re.finditer(juta_pattern, cleaned):
        val = float(match.group(1).replace(",", "."))
        amounts.append(int(val * 1_000_000))

    # Try plain numbers if no juta/miliar found (strip dots as thousand separators)
    if not amounts:
        plain = cleaned.replace(".", "").replace(",", "")
        numbers = re.findall(r"(\d{6,})", plain)
        amounts = [int(n) for n in numbers]

    if not amounts:
        return (None, None)
    if len(amounts) == 1:
        return (amounts[0], amounts[0])
    return (min(amounts), max(amounts))


_LOAN_TYPE_PATTERNS = [
    (r"kpr|kredit pemilikan rumah|home loan|housing", "KPR"),
    (r"kpa|kredit pemilikan apartemen|apartment", "KPA"),
    (r"kpt|kredit pemilikan tanah|land", "KPT"),
    (r"multiguna|multi guna|multipurpose", "MULTIGUNA"),
    (r"kendaraan|kendaraan bermotor|auto|vehicle|mobil|motor", "KENDARAAN"),
    (r"modal kerja|working capital", "MODAL_KERJA"),
    (r"investasi|investment", "INVESTASI"),
    (r"pendidikan|education|student", "PENDIDIKAN"),
    (r"pmi|pekerja migran|migrant", "PMI"),
    (r"take.?over|takeover", "TAKE_OVER"),
    (r"refinanc", "REFINANCING"),
]


def normalize_loan_type(text: str) -> str:
    if not text:
        return "OTHER"

    text_lower = text.lower()
    for pattern, loan_type in _LOAN_TYPE_PATTERNS:
        if re.search(pattern, text_lower):
            return loan_type
    return "OTHER"


def normalize_tenure(text: str) -> tuple[Optional[int], Optional[int]]:
    if not text:
        return (None, None)

    text_lower = text.lower()
    numbers = re.findall(r"(\d+)", text_lower)

    if not numbers:
        return (None, None)

    is_years = "tahun" in text_lower or "year" in text_lower

    values = [int(n) for n in numbers]
    if is_years:
        values = [v * 12 for v in values]

    # Handle "Maks." / "Max" patterns
    if re.search(r"maks|max", text_lower):
        return (None, max(values))

    if len(values) == 1:
        return (values[0], values[0])
    return (min(values), max(values))
```

- [ ] **Step 6: Run tests, commit**

```bash
poetry run pytest tests/test_extractors.py tests/test_normalizer.py -v
git add src/ceres/extractors/ tests/test_extractors.py tests/test_normalizer.py
git commit -m "feat: add CSS selector extractor and Indonesian banking normalizer"
```

---

### Task 8: LLM Extractor (Claude API Fallback)

**Files:**
- Create: `src/ceres/extractors/llm.py`
- Create: `tests/test_llm_extractor.py`

- [ ] **Step 1: Write failing test**

`tests/test_llm_extractor.py`:
```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.extractors.llm import ClaudeLLMExtractor, LLMExtractor


class TestClaudeLLMExtractor:
    @pytest.mark.asyncio
    async def test_extract_loan_data_calls_claude(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "programs": [{
                "program_name": "KPR BCA",
                "loan_type": "KPR",
                "min_interest_rate": 3.5,
                "max_interest_rate": 7.0,
            }]
        }))]

        mock_client.messages.create = AsyncMock(return_value=mock_response)

        extractor = ClaudeLLMExtractor(client=mock_client)
        result = await extractor.extract_loan_data(
            html="<div>KPR BCA bunga 3.5%-7.0%</div>",
            bank_name="BCA"
        )
        assert len(result["programs"]) == 1
        assert result["programs"][0]["program_name"] == "KPR BCA"

    @pytest.mark.asyncio
    async def test_extract_handles_malformed_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        extractor = ClaudeLLMExtractor(client=mock_client)
        result = await extractor.extract_loan_data(
            html="<div>some html</div>",
            bank_name="BCA"
        )
        assert result == {"programs": [], "error": "Failed to parse LLM response"}

    def test_implements_interface(self):
        mock_client = MagicMock()
        assert isinstance(ClaudeLLMExtractor(client=mock_client), LLMExtractor)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_llm_extractor.py -v
```

- [ ] **Step 3: Implement LLM extractor**

`src/ceres/extractors/llm.py`:
```python
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a data extraction specialist for Indonesian bank loan products.

Extract ALL loan programs from the following HTML content from {bank_name}'s website.

For each program, extract these fields (use null if not found):
- program_name: Name of the loan product
- loan_type: One of KPR, KPA, KPT, MULTIGUNA, KENDARAAN, MODAL_KERJA, INVESTASI, PENDIDIKAN, PMI, TAKE_OVER, REFINANCING, OTHER
- min_interest_rate: Minimum interest rate (number, percentage)
- max_interest_rate: Maximum interest rate (number, percentage)
- rate_type: FIXED, FLOATING, or MIXED
- min_loan_amount: Minimum loan amount in IDR (number)
- max_loan_amount: Maximum loan amount in IDR (number)
- min_tenure_months: Minimum tenure in months (number)
- max_tenure_months: Maximum tenure in months (number)
- min_dp_percentage: Minimum down payment percentage (number)
- min_age: Minimum age requirement (number)
- max_age: Maximum age requirement (number)
- min_income: Minimum monthly income in IDR (number)
- features: List of key features (array of strings)
- required_documents: List of required documents (array of strings)
- admin_fee: Admin fee description (string)
- provisi_fee: Provisi fee description (string)

Respond ONLY with valid JSON in this format:
{{"programs": [{{...fields...}}]}}

HTML Content:
{html}"""


class LLMExtractor(ABC):
    @abstractmethod
    async def extract_loan_data(self, html: str, bank_name: str) -> dict:
        ...


class ClaudeLLMExtractor(LLMExtractor):
    def __init__(self, client: Any, model: str = "claude-sonnet-4-20250514"):
        self._client = client
        self._model = model

    async def extract_loan_data(self, html: str, bank_name: str) -> dict:
        # Truncate HTML to avoid token limits
        truncated = html[:50_000] if len(html) > 50_000 else html

        prompt = EXTRACTION_PROMPT.format(bank_name=bank_name, html=truncated)

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text

            # Try to extract JSON from response
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
                return {"programs": [], "error": "Failed to parse LLM response"}

        except Exception as e:
            logger.error(f"LLM extraction failed for {bank_name}: {e}")
            return {"programs": [], "error": str(e)}
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_llm_extractor.py -v
git add src/ceres/extractors/llm.py tests/test_llm_extractor.py
git commit -m "feat: add Claude API LLM extractor for parser fallback"
```

---

### Task 9: Rate Limiter & Logging Utilities

**Files:**
- Create: `src/ceres/utils/rate_limiter.py`
- Create: `src/ceres/utils/logging.py`
- Create: `tests/test_rate_limiter.py`

- [ ] **Step 1: Write failing test**

`tests/test_rate_limiter.py`:
```python
import asyncio
import time
import pytest
from ceres.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_call_not_delayed(self):
        limiter = RateLimiter(delay_ms=1000)
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Should be immediate

    @pytest.mark.asyncio
    async def test_second_call_delayed(self):
        limiter = RateLimiter(delay_ms=200)
        await limiter.wait()
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15  # Should wait ~200ms (with tolerance)

    @pytest.mark.asyncio
    async def test_per_domain_isolation(self):
        limiter = RateLimiter(delay_ms=500)
        await limiter.wait(domain="a.com")
        start = time.monotonic()
        await limiter.wait(domain="b.com")  # Different domain, no wait
        elapsed = time.monotonic() - start
        assert elapsed < 0.1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_rate_limiter.py -v
```

- [ ] **Step 3: Implement rate limiter and logging**

`src/ceres/utils/rate_limiter.py`:
```python
from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, delay_ms: int = 2000):
        self._delay_s = delay_ms / 1000.0
        self._last_call: dict[str, float] = defaultdict(float)

    async def wait(self, domain: str = "__default__") -> None:
        now = time.monotonic()
        last = self._last_call[domain]
        elapsed = now - last

        if last > 0 and elapsed < self._delay_s:
            await asyncio.sleep(self._delay_s - elapsed)

        self._last_call[domain] = time.monotonic()
```

`src/ceres/utils/logging.py`:
```python
from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Quiet noisy libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_rate_limiter.py -v
git add src/ceres/utils/rate_limiter.py src/ceres/utils/logging.py tests/test_rate_limiter.py
git commit -m "feat: add per-domain rate limiter and structured logging"
```

---

## Phase 3: Agents

### Task 10: Base Agent

**Files:**
- Create: `src/ceres/agents/__init__.py`
- Create: `src/ceres/agents/base.py`
- Create: `tests/test_agent_base.py`

- [ ] **Step 1: Write failing test**

`tests/test_agent_base.py`:
```python
import pytest
from unittest.mock import AsyncMock
from ceres.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    name = "test_agent"

    async def run(self, **kwargs):
        return {"status": "ok"}


class TestBaseAgent:
    @pytest.mark.asyncio
    async def test_agent_has_name(self):
        db = AsyncMock()
        agent = ConcreteAgent(db=db)
        assert agent.name == "test_agent"

    @pytest.mark.asyncio
    async def test_agent_run_returns_result(self):
        db = AsyncMock()
        agent = ConcreteAgent(db=db)
        result = await agent.run()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_agent_execute_wraps_run(self):
        db = AsyncMock()
        agent = ConcreteAgent(db=db)
        result = await agent.execute()
        assert result["status"] == "ok"

    def test_base_agent_cannot_be_instantiated(self):
        db = AsyncMock()
        with pytest.raises(TypeError):
            BaseAgent(db=db)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_agent_base.py -v
```

- [ ] **Step 3: Implement base agent**

`src/ceres/agents/__init__.py`: empty

`src/ceres/agents/base.py`:
```python
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from ceres.database import Database


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, db: Database, config: Optional[Any] = None):
        self.db = db
        self.config = config
        self.logger = logging.getLogger(f"ceres.agents.{self.name}")

    @abstractmethod
    async def run(self, **kwargs) -> dict:
        ...

    async def execute(self, **kwargs) -> dict:
        self.logger.info(f"[{self.name}] Starting execution")
        start = time.monotonic()

        try:
            result = await self.run(**kwargs)
            elapsed = time.monotonic() - start
            self.logger.info(f"[{self.name}] Completed in {elapsed:.1f}s")
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            self.logger.error(f"[{self.name}] Failed after {elapsed:.1f}s: {e}")
            raise
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_agent_base.py -v
git add src/ceres/agents/ tests/test_agent_base.py
git commit -m "feat: add BaseAgent ABC with execution wrapper"
```

---

### Task 11: Scout Agent

**Files:**
- Create: `src/ceres/agents/scout.py`
- Create: `tests/test_scout.py`

- [ ] **Step 1: Write failing test**

`tests/test_scout.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ceres.agents.scout import ScoutAgent


class TestScoutAgent:
    @pytest.mark.asyncio
    async def test_check_website_status_active(self):
        db = AsyncMock()
        agent = ScoutAgent(db=db)

        with patch("ceres.agents.scout.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.head = AsyncMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            status = await agent._check_website("https://bca.co.id")
            assert status == "active"

    @pytest.mark.asyncio
    async def test_check_website_status_unreachable(self):
        db = AsyncMock()
        agent = ScoutAgent(db=db)

        with patch("ceres.agents.scout.aiohttp.ClientSession") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.head = AsyncMock(side_effect=Exception("Connection refused"))
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            status = await agent._check_website("https://invalid.example.com")
            assert status == "unreachable"

    @pytest.mark.asyncio
    async def test_run_updates_all_banks(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "uuid1", "bank_code": "BCA", "website_url": "https://bca.co.id"},
            {"id": "uuid2", "bank_code": "BRI", "website_url": "https://bri.co.id"},
        ])
        db.update_bank_status = AsyncMock()

        agent = ScoutAgent(db=db)

        with patch.object(agent, "_check_website", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = "active"
            result = await agent.run()

        assert result["banks_checked"] == 2
        assert db.update_bank_status.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_scout.py -v
```

- [ ] **Step 3: Implement Scout agent**

`src/ceres/agents/scout.py`:
```python
from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp

from ceres.agents.base import BaseAgent


class ScoutAgent(BaseAgent):
    name = "scout"

    async def run(self, **kwargs) -> dict:
        banks = await self.db.fetch_banks()
        self.logger.info(f"Checking {len(banks)} banks")

        results = {"banks_checked": 0, "active": 0, "unreachable": 0, "blocked": 0}

        # Check in batches of 10
        batch_size = 10
        for i in range(0, len(banks), batch_size):
            batch = banks[i : i + batch_size]
            tasks = [self._check_and_update(bank) for bank in batch]
            statuses = await asyncio.gather(*tasks, return_exceptions=True)

            for status in statuses:
                if isinstance(status, Exception):
                    self.logger.warning(f"Check failed: {status}")
                    continue
                results["banks_checked"] += 1
                if status in results:
                    results[status] += 1

        self.logger.info(
            f"Scout complete: {results['banks_checked']} checked, "
            f"{results['active']} active, {results['unreachable']} unreachable"
        )
        return results

    async def _check_and_update(self, bank: dict) -> str:
        url = bank.get("website_url")
        if not url:
            return "unknown"

        status = await self._check_website(url)
        await self.db.update_bank_status(
            bank["id"], status, last_crawled=True
        )
        self.logger.debug(f"{bank['bank_code']}: {status}")
        return status

    async def _check_website(self, url: str, timeout: int = 15) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as response:
                    if response.status == 403:
                        return "blocked"
                    if response.status < 400:
                        return "active"
                    return "unreachable"
        except asyncio.TimeoutError:
            return "unreachable"
        except Exception:
            return "unreachable"
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_scout.py -v
git add src/ceres/agents/scout.py tests/test_scout.py
git commit -m "feat: add Scout agent for bank website health checks"
```

---

### Task 12: Strategist Agent

**Files:**
- Create: `src/ceres/agents/strategist.py`
- Create: `tests/test_strategist.py`

- [ ] **Step 1: Write failing test**

`tests/test_strategist.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.agents.strategist import StrategistAgent


class TestStrategistAgent:
    @pytest.mark.asyncio
    async def test_determine_bypass_method_api(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": True}
        method = agent._determine_bypass_method(bank, anti_bot_type=None)
        assert method == "api"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_cloudflare(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type="cloudflare")
        assert method == "headless_browser"

    @pytest.mark.asyncio
    async def test_determine_bypass_method_fingerprint(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)
        bank = {"api_available": False}
        method = agent._determine_bypass_method(bank, anti_bot_type="fingerprint")
        assert method == "undetected_chrome"

    @pytest.mark.asyncio
    async def test_discover_loan_urls_from_common_paths(self):
        db = AsyncMock()
        agent = StrategistAgent(db=db)

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>KPR Info</body></html>")
        mock_page.url = "https://bca.co.id/kpr"

        urls = await agent._discover_loan_urls(
            page=mock_page,
            base_url="https://bca.co.id",
        )
        # Should try common paths like /kpr, /kredit, /pinjaman
        assert mock_page.goto.call_count > 0

    @pytest.mark.asyncio
    async def test_run_creates_strategy(self):
        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "uuid1", "bank_code": "BCA", "website_url": "https://bca.co.id",
             "api_available": False, "website_status": "active"}
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.upsert_strategy = AsyncMock(return_value={"id": "strat1", "bank_id": "uuid1", "version": 1})

        agent = StrategistAgent(db=db)

        with patch.object(agent, "_analyze_bank", new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = {
                "anti_bot_detected": False,
                "anti_bot_type": None,
                "bypass_method": "headless_browser",
                "loan_page_urls": ["https://bca.co.id/kpr"],
                "selectors": {},
                "rate_limit_ms": 2000,
            }
            result = await agent.run(bank_code="BCA")

        db.upsert_strategy.assert_called_once()
        assert result["strategies_created"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_strategist.py -v
```

- [ ] **Step 3: Implement Strategist agent**

`src/ceres/agents/strategist.py`:
```python
from __future__ import annotations

from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot


COMMON_LOAN_PATHS = [
    "/kpr", "/kredit", "/pinjaman", "/loan", "/mortgage",
    "/kredit-pemilikan-rumah", "/produk/kredit", "/produk/pinjaman",
    "/personal/kredit", "/personal/pinjaman", "/consumer-loan",
    "/kpa", "/kpt", "/multiguna", "/kredit-multiguna",
    "/kendaraan", "/kredit-kendaraan",
]


class StrategistAgent(BaseAgent):
    name = "strategist"

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        banks = await self.db.fetch_banks()
        if bank_code:
            banks = [b for b in banks if b["bank_code"] == bank_code]

        results = {"strategies_created": 0, "strategies_updated": 0, "errors": 0}

        for bank in banks:
            if bank.get("website_status") not in ("active", "unknown"):
                continue

            existing = await self.db.fetch_active_strategies(bank_id=bank["id"])
            if existing and not kwargs.get("force"):
                continue

            try:
                analysis = await self._analyze_bank(bank)
                await self.db.upsert_strategy(
                    bank_id=bank["id"],
                    selectors=analysis["selectors"],
                    loan_page_urls=analysis["loan_page_urls"],
                    bypass_method=analysis["bypass_method"],
                    anti_bot_detected=analysis["anti_bot_detected"],
                    anti_bot_type=analysis["anti_bot_type"],
                    rate_limit_ms=analysis["rate_limit_ms"],
                )
                if existing:
                    results["strategies_updated"] += 1
                else:
                    results["strategies_created"] += 1
                self.logger.info(f"{bank['bank_code']}: strategy created ({analysis['bypass_method']})")
            except Exception as e:
                results["errors"] += 1
                self.logger.error(f"{bank['bank_code']}: strategy creation failed: {e}")

        return results

    async def _analyze_bank(self, bank: dict) -> dict:
        browser_mgr = BrowserManager()
        browser = None
        page = None

        try:
            browser, page = await browser_mgr.create_context(BrowserType.PLAYWRIGHT)
            await page.goto(bank["website_url"], wait_until="domcontentloaded", timeout=30000)
            html = await page.content()

            anti_bot = detect_anti_bot(html)
            bypass_method = self._determine_bypass_method(bank, anti_bot.anti_bot_type)

            loan_urls = await self._discover_loan_urls(page, bank["website_url"])

            return {
                "anti_bot_detected": anti_bot.detected,
                "anti_bot_type": anti_bot.anti_bot_type,
                "bypass_method": bypass_method,
                "loan_page_urls": loan_urls,
                "selectors": {},  # Will be refined per-page
                "rate_limit_ms": 3000 if anti_bot.detected else 2000,
            }
        finally:
            if browser:
                await browser_mgr.close_context(browser, BrowserType.PLAYWRIGHT)

    def _determine_bypass_method(self, bank: dict, anti_bot_type: Optional[str]) -> str:
        if bank.get("api_available"):
            return "api"
        if anti_bot_type == "fingerprint":
            return "undetected_chrome"
        if anti_bot_type in ("cloudflare", "datadome"):
            return "headless_browser"
        return "headless_browser"

    async def _discover_loan_urls(self, page: Any, base_url: str) -> list[str]:
        found_urls = []
        base = base_url.rstrip("/")

        for path in COMMON_LOAN_PATHS:
            url = f"{base}{path}"
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                if response and response.status < 400:
                    content = await page.content()
                    content_lower = content.lower()
                    # Check if page has loan-related content
                    loan_keywords = ["kredit", "pinjaman", "kpr", "loan", "bunga", "angsuran", "tenor"]
                    if any(kw in content_lower for kw in loan_keywords):
                        found_urls.append(page.url)
                        self.logger.debug(f"Found loan page: {page.url}")
            except Exception:
                continue

        return found_urls if found_urls else [base_url]
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_strategist.py -v
git add src/ceres/agents/strategist.py tests/test_strategist.py
git commit -m "feat: add Strategist agent for anti-bot detection and loan URL discovery"
```

---

### Task 13: Crawler Agent

**Files:**
- Create: `src/ceres/agents/crawler.py`
- Create: `tests/test_crawler.py`

- [ ] **Step 1: Write failing test**

`tests/test_crawler.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.agents.crawler import CrawlerAgent


class TestCrawlerAgent:
    @pytest.mark.asyncio
    async def test_crawl_single_bank(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser", "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 2000,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value="log1")
        db.store_raw_html = AsyncMock(return_value="raw1")
        db.update_crawl_log = AsyncMock()

        agent = CrawlerAgent(db=db)

        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html><body>KPR BCA</body></html>"
            result = await agent.run(bank_code="BCA")

        assert result["banks_crawled"] == 1
        db.store_raw_html.assert_called_once()

    @pytest.mark.asyncio
    async def test_crawl_retries_on_failure(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser", "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 100,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value="log1")
        db.update_crawl_log = AsyncMock()

        agent = CrawlerAgent(db=db, config=MagicMock(max_retries=3))

        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Timeout")
            result = await agent.run(bank_code="BCA")

        assert result["failures"] == 1
        # Should have retried 3 times
        assert mock_fetch.call_count == 3

    @pytest.mark.asyncio
    async def test_crawl_detects_anti_bot(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 100,
            "anti_bot_detected": False, "version": 1,
        }])
        db.create_crawl_log = AsyncMock(return_value="log1")
        db.store_raw_html = AsyncMock(return_value="raw1")
        db.update_crawl_log = AsyncMock()

        agent = CrawlerAgent(db=db)

        html_with_cf = '<html><div class="cf-browser-verification">Check</div></html>'
        with patch.object(agent, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = html_with_cf
            result = await agent.run(bank_code="BCA")

        # Should flag anti-bot detection in crawl log
        update_call = db.update_crawl_log.call_args
        assert update_call.kwargs.get("anti_bot_detected") is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_crawler.py -v
```

- [ ] **Step 3: Implement Crawler agent**

`src/ceres/agents/crawler.py`:
```python
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot
from ceres.utils.rate_limiter import RateLimiter


class CrawlerAgent(BaseAgent):
    name = "crawler"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rate_limiter = RateLimiter()
        max_retries = 3
        if self.config and hasattr(self.config, "max_retries"):
            max_retries = self.config.max_retries
        self._max_retries = max_retries

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        strategies = await self.db.fetch_active_strategies()
        if bank_code:
            strategies = [s for s in strategies if s["bank_code"] == bank_code]

        results = {"banks_crawled": 0, "pages_fetched": 0, "failures": 0, "blocked": 0}

        max_concurrent = 5
        if self.config and hasattr(self.config, "max_concurrency"):
            max_concurrent = self.config.max_concurrency

        semaphore = asyncio.Semaphore(max_concurrent)

        async def crawl_with_semaphore(strategy):
            async with semaphore:
                return await self._crawl_bank(strategy)

        tasks = [crawl_with_semaphore(s) for s in strategies]
        bank_results = await asyncio.gather(*tasks, return_exceptions=True)

        for br in bank_results:
            if isinstance(br, Exception):
                results["failures"] += 1
                continue
            results["banks_crawled"] += 1
            results["pages_fetched"] += br.get("pages", 0)
            if br.get("blocked"):
                results["blocked"] += 1
            if br.get("failed"):
                results["failures"] += 1

        self.logger.info(
            f"Crawl complete: {results['banks_crawled']} banks, "
            f"{results['pages_fetched']} pages, {results['failures']} failures"
        )
        return results

    async def _crawl_bank(self, strategy: dict) -> dict:
        bank_code = strategy["bank_code"]
        bank_id = strategy["bank_id"]
        strategy_id = strategy["id"]

        log_id = await self.db.create_crawl_log(
            bank_id=bank_id, strategy_id=strategy_id
        )

        loan_urls = json.loads(strategy["loan_page_urls"]) if isinstance(
            strategy["loan_page_urls"], str
        ) else strategy["loan_page_urls"]

        rate_limit_ms = strategy.get("rate_limit_ms", 2000)
        rate_limiter = RateLimiter(delay_ms=rate_limit_ms)

        pages_fetched = 0
        blocked = False
        error_msg = None

        for url in loan_urls:
            try:
                html = await self._fetch_with_retry(url, strategy, bank_code)

                if html:
                    anti_bot = detect_anti_bot(html)
                    if anti_bot.detected:
                        blocked = True
                        self.logger.warning(f"{bank_code}: anti-bot detected ({anti_bot.anti_bot_type}) at {url}")
                        await self.db.update_crawl_log(
                            log_id, status="blocked",
                            anti_bot_detected=True,
                            error_type=f"anti_bot_{anti_bot.anti_bot_type}",
                            error_message=f"Anti-bot: {anti_bot.anti_bot_type}",
                        )
                        return {"pages": pages_fetched, "blocked": True, "failed": False}

                    await self.db.store_raw_html(
                        crawl_log_id=log_id, bank_id=bank_id,
                        page_url=url, raw_html=html,
                    )
                    pages_fetched += 1
                    self.logger.debug(f"{bank_code}: fetched {url}")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"{bank_code}: failed to fetch {url}: {e}")

        status = "success" if pages_fetched > 0 else "failed"
        await self.db.update_crawl_log(
            log_id, status=status,
            programs_found=0,  # Parser will update
            error_type="fetch_error" if error_msg else None,
            error_message=error_msg,
            anti_bot_detected=blocked,
        )

        return {"pages": pages_fetched, "blocked": blocked, "failed": pages_fetched == 0}

    async def _fetch_with_retry(self, url: str, strategy: dict,
                                 bank_code: str) -> Optional[str]:
        for attempt in range(self._max_retries):
            try:
                await rate_limiter.wait(domain=bank_code)
                return await self._fetch_page(url, strategy)
            except Exception as e:
                if attempt < self._max_retries - 1:
                    wait_time = (2 ** attempt) * 1
                    self.logger.warning(
                        f"{bank_code}: retry {attempt + 1}/{self._max_retries} "
                        f"for {url} (waiting {wait_time}s): {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise
        return None

    async def _fetch_page(self, url: str, strategy: dict) -> str:
        bypass = strategy.get("bypass_method", "headless_browser")
        browser_type = (
            BrowserType.UNDETECTED if bypass == "undetected_chrome"
            else BrowserType.PLAYWRIGHT
        )

        browser_mgr = BrowserManager()
        browser = None
        try:
            browser, page = await browser_mgr.create_context(browser_type)

            if browser_type == BrowserType.PLAYWRIGHT:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                return await page.content()
            else:
                # Undetected ChromeDriver (synchronous)
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, page.get, url)
                await asyncio.sleep(3)  # Wait for JS rendering
                return await loop.run_in_executor(None, lambda: page.page_source)
        finally:
            if browser:
                await browser_mgr.close_context(browser, browser_type)
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_crawler.py -v
git add src/ceres/agents/crawler.py tests/test_crawler.py
git commit -m "feat: add Crawler agent with retry, anti-bot detection, and concurrent crawling"
```

---

### Task 14: Parser Agent

**Files:**
- Create: `src/ceres/agents/parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing test**

`tests/test_parser.py`:
```python
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ceres.agents.parser import ParserAgent


class TestParserAgent:
    @pytest.mark.asyncio
    async def test_parse_with_selectors(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[{
            "id": "raw1", "bank_id": "uuid1", "bank_code": "BCA",
            "page_url": "https://bca.co.id/kpr",
            "raw_html": """
                <div class="product">
                    <h3 class="name">KPR BCA</h3>
                    <span class="rate">3.5% - 7.0%</span>
                </div>
            """,
            "selectors": json.dumps({
                "container": "div.product",
                "fields": {"name": "h3.name", "rate": "span.rate"},
            }),
        }])
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1", "program_name": "KPR BCA", "loan_type": "KPR"})
        db.mark_parsed = AsyncMock()

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] >= 1
        db.mark_parsed.assert_called_once_with("raw1")

    @pytest.mark.asyncio
    async def test_llm_fallback_on_low_confidence(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[{
            "id": "raw1", "bank_id": "uuid1", "bank_code": "BCA",
            "page_url": "https://bca.co.id/kpr",
            "raw_html": "<div>Some unstructured text about loans</div>",
            "selectors": None,  # No selectors
        }])
        db.upsert_loan_program = AsyncMock(return_value={"id": "lp1", "program_name": "KPR BCA", "loan_type": "KPR"})
        db.mark_parsed = AsyncMock()

        mock_llm = AsyncMock()
        mock_llm.extract_loan_data = AsyncMock(return_value={
            "programs": [{"program_name": "KPR BCA", "loan_type": "KPR", "min_interest_rate": 3.5}]
        })

        agent = ParserAgent(db=db, llm_extractor=mock_llm)
        result = await agent.run()

        mock_llm.extract_loan_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_unparsed_data(self):
        db = AsyncMock()
        db.fetch_unparsed_html = AsyncMock(return_value=[])

        agent = ParserAgent(db=db)
        result = await agent.run()

        assert result["programs_parsed"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_parser.py -v
```

- [ ] **Step 3: Implement Parser agent**

`src/ceres/agents/parser.py`:
```python
from __future__ import annotations

import json
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.extractors.llm import LLMExtractor
from ceres.extractors.normalizer import (
    normalize_amount, normalize_loan_type, normalize_rate, normalize_tenure,
)
from ceres.extractors.selector import SelectorExtractor
from ceres.models import calculate_completeness_score


LLM_CONFIDENCE_THRESHOLD = 0.5


class ParserAgent(BaseAgent):
    name = "parser"

    def __init__(self, llm_extractor: Optional[LLMExtractor] = None, **kwargs):
        super().__init__(**kwargs)
        self._selector_extractor = SelectorExtractor()
        self._llm_extractor = llm_extractor

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        unparsed = await self.db.fetch_unparsed_html(
            bank_id=kwargs.get("bank_id")
        )
        self.logger.info(f"Found {len(unparsed)} unparsed pages")

        results = {"programs_parsed": 0, "llm_fallbacks": 0, "errors": 0}

        for raw in unparsed:
            try:
                programs = await self._parse_page(raw)
                for program in programs:
                    await self.db.upsert_loan_program(**program)
                    results["programs_parsed"] += 1

                await self.db.mark_parsed(raw["id"])
            except Exception as e:
                results["errors"] += 1
                self.logger.error(f"Parse error for {raw.get('bank_code')}: {e}")

        self.logger.info(
            f"Parser complete: {results['programs_parsed']} programs, "
            f"{results['llm_fallbacks']} LLM fallbacks, {results['errors']} errors"
        )
        return results

    async def _parse_page(self, raw: dict) -> list[dict]:
        selectors = raw.get("selectors")
        if isinstance(selectors, str):
            selectors = json.loads(selectors) if selectors else None

        programs = []

        # Try selector-based extraction first
        if selectors and selectors.get("fields"):
            extraction_results = self._selector_extractor.extract(
                raw["raw_html"], selectors
            )
            for result in extraction_results:
                if result.confidence >= LLM_CONFIDENCE_THRESHOLD:
                    program = self._normalize_fields(
                        result.fields, raw, confidence_base=result.confidence
                    )
                    if program:
                        programs.append(program)

        # LLM fallback if no results or low confidence
        if not programs and self._llm_extractor:
            llm_result = await self._llm_extractor.extract_loan_data(
                html=raw["raw_html"],
                bank_name=raw.get("bank_name", raw.get("bank_code", "Unknown")),
            )
            for prog_data in llm_result.get("programs", []):
                program = self._build_program_from_llm(prog_data, raw)
                if program:
                    programs.append(program)

        return programs

    def _normalize_fields(self, fields: dict, raw: dict,
                          confidence_base: float) -> Optional[dict]:
        name = fields.get("name")
        if not name:
            return None

        loan_type = normalize_loan_type(name)

        rate_min, rate_max = normalize_rate(fields.get("rate", ""))
        amount_min, amount_max = normalize_amount(fields.get("amount", ""))
        tenure_min, tenure_max = normalize_tenure(fields.get("tenure", ""))

        data = {
            "program_name": name,
            "loan_type": loan_type,
            "min_interest_rate": rate_min,
            "max_interest_rate": rate_max,
            "min_loan_amount": amount_min,
            "max_loan_amount": amount_max,
            "min_tenure_months": tenure_min,
            "max_tenure_months": tenure_max,
        }

        completeness = calculate_completeness_score(data)

        return {
            "bank_id": raw["bank_id"],
            "program_name": name,
            "loan_type": loan_type,
            "source_url": raw["page_url"],
            "data_confidence": round(confidence_base * 0.8, 2),  # HTML extraction base
            "completeness_score": completeness,
            "raw_data": fields,
            "min_interest_rate": rate_min,
            "max_interest_rate": rate_max,
            "min_loan_amount": amount_min,
            "max_loan_amount": amount_max,
            "min_tenure_months": tenure_min,
            "max_tenure_months": tenure_max,
        }

    def _build_program_from_llm(self, prog_data: dict, raw: dict) -> Optional[dict]:
        name = prog_data.get("program_name")
        if not name:
            return None

        loan_type = prog_data.get("loan_type", normalize_loan_type(name))

        completeness = calculate_completeness_score(prog_data)

        result = {
            "bank_id": raw["bank_id"],
            "program_name": name,
            "loan_type": loan_type,
            "source_url": raw["page_url"],
            "data_confidence": 0.7,  # LLM extraction confidence
            "completeness_score": completeness,
            "raw_data": prog_data,
        }

        # Map LLM fields directly
        direct_fields = [
            "min_interest_rate", "max_interest_rate", "rate_type",
            "min_loan_amount", "max_loan_amount",
            "min_tenure_months", "max_tenure_months",
            "min_dp_percentage", "min_age", "max_age", "min_income",
            "admin_fee", "provisi_fee", "appraisal_fee",
        ]
        for field in direct_fields:
            if field in prog_data and prog_data[field] is not None:
                result[field] = prog_data[field]

        json_fields = ["features", "required_documents", "employment_types"]
        for field in json_fields:
            if field in prog_data and prog_data[field]:
                result[field] = prog_data[field]

        return result
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_parser.py -v
git add src/ceres/agents/parser.py tests/test_parser.py
git commit -m "feat: add Parser agent with selector extraction and LLM fallback"
```

---

### Task 15: Learning Agent

**Files:**
- Create: `src/ceres/agents/learning.py`
- Create: `tests/test_learning.py`

- [ ] **Step 1: Write failing test**

`tests/test_learning.py`:
```python
import pytest
from unittest.mock import AsyncMock

from ceres.agents.learning import LearningAgent


class TestLearningAgent:
    @pytest.mark.asyncio
    async def test_calculates_success_rates(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 100, "successes": 80, "failures": 15,
            "blocked": 5, "banks_crawled": 50, "total_programs_found": 200,
        })
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "BCA", "is_partner_ringkas": False},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value="rec1")

        agent = LearningAgent(db=db)
        result = await agent.run()

        assert result["overall_success_rate"] == 0.8
        assert "report" in result

    @pytest.mark.asyncio
    async def test_identifies_partnership_opportunities(self):
        db = AsyncMock()
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 10, "successes": 8, "failures": 2,
            "blocked": 0, "banks_crawled": 5, "total_programs_found": 20,
        })
        db.fetch_banks = AsyncMock(return_value=[
            {"id": "1", "bank_code": "NEWBANK", "is_partner_ringkas": False,
             "bank_name": "New Bank"},
        ])
        db.fetch_loan_programs = AsyncMock(return_value=[
            {"bank_id": "1", "bank_code": "NEWBANK", "loan_type": "KPR",
             "program_name": "KPR NewBank", "min_interest_rate": 3.0,
             "completeness_score": 0.9, "data_confidence": 0.8},
        ])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.add_recommendation = AsyncMock(return_value="rec1")

        agent = LearningAgent(db=db)
        result = await agent.run()

        # Should have created a partnership recommendation
        db.add_recommendation.assert_called()
        call_kwargs = db.add_recommendation.call_args.kwargs
        assert call_kwargs["rec_type"] == "partnership_opportunity"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_learning.py -v
```

- [ ] **Step 3: Implement Learning agent**

`src/ceres/agents/learning.py`:
```python
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ceres.agents.base import BaseAgent


class LearningAgent(BaseAgent):
    name = "learning"

    async def run(self, days: int = 7, **kwargs) -> dict:
        stats = await self.db.get_crawl_stats(days=days)
        banks = await self.db.fetch_banks()
        programs = await self.db.fetch_loan_programs(latest_only=True)

        total = stats["total_crawls"] or 1
        success_rate = (stats["successes"] or 0) / total

        report = {
            "overall_success_rate": round(success_rate, 2),
            "total_crawls": stats["total_crawls"],
            "successes": stats["successes"],
            "failures": stats["failures"],
            "blocked": stats["blocked"],
            "banks_crawled": stats["banks_crawled"],
            "total_programs": len(programs),
        }

        # Coverage analysis
        coverage = self._analyze_coverage(programs)
        report["coverage"] = coverage

        # Generate recommendations
        recs = await self._generate_recommendations(banks, programs, stats)
        report["recommendations_generated"] = len(recs)
        report["report"] = self._format_report(report)

        self.logger.info(
            f"Learning complete: {success_rate:.0%} success rate, "
            f"{len(programs)} programs, {len(recs)} recommendations"
        )
        return report

    def _analyze_coverage(self, programs: list[dict]) -> dict:
        by_type = defaultdict(int)
        by_bank = defaultdict(int)

        for p in programs:
            by_type[p.get("loan_type", "OTHER")] += 1
            by_bank[p.get("bank_code", "UNKNOWN")] += 1

        return {
            "by_loan_type": dict(by_type),
            "by_bank": dict(by_bank),
            "banks_with_products": len(by_bank),
            "loan_types_covered": len(by_type),
        }

    async def _generate_recommendations(self, banks: list[dict],
                                         programs: list[dict],
                                         stats: dict) -> list[str]:
        rec_ids = []
        non_partner_banks = [b for b in banks if not b.get("is_partner_ringkas")]
        bank_programs = defaultdict(list)
        for p in programs:
            bank_programs[p.get("bank_id")].append(p)

        # Partnership opportunities: non-partners with KPR products
        for bank in non_partner_banks:
            bank_progs = bank_programs.get(bank["id"], [])
            kpr_progs = [p for p in bank_progs if p.get("loan_type") == "KPR"]

            if kpr_progs:
                avg_confidence = sum(
                    p.get("data_confidence", 0) for p in kpr_progs
                ) / len(kpr_progs)

                if avg_confidence >= 0.5:
                    rec_id = await self.db.add_recommendation(
                        rec_type="partnership_opportunity",
                        priority=2,
                        impact_score=avg_confidence,
                        title=f"Partnership opportunity: {bank['bank_name']}",
                        summary=(
                            f"{bank['bank_name']} has {len(kpr_progs)} KPR product(s) "
                            f"but is not a Ringkas partner."
                        ),
                        related_bank_ids=[bank["id"]],
                    )
                    rec_ids.append(rec_id)

        # Product gap analysis
        all_types = {"KPR", "KPA", "KPT", "MULTIGUNA", "KENDARAAN", "MODAL_KERJA"}
        covered_types = {p.get("loan_type") for p in programs}
        missing = all_types - covered_types

        if missing:
            rec_id = await self.db.add_recommendation(
                rec_type="product_gap",
                priority=3,
                impact_score=len(missing) / len(all_types),
                title=f"Missing loan types: {', '.join(sorted(missing))}",
                summary=f"No data found for {len(missing)} loan type(s).",
            )
            rec_ids.append(rec_id)

        return rec_ids

    def _format_report(self, report: dict) -> str:
        lines = [
            "=== CERES Daily Report ===",
            f"Success Rate: {report['overall_success_rate']:.0%}",
            f"Total Crawls: {report['total_crawls']}",
            f"Banks Crawled: {report['banks_crawled']}",
            f"Programs Found: {report['total_programs']}",
            f"Failures: {report['failures']} | Blocked: {report['blocked']}",
            f"Recommendations: {report['recommendations_generated']}",
        ]
        coverage = report.get("coverage", {})
        if coverage.get("by_loan_type"):
            lines.append("\nCoverage by Loan Type:")
            for lt, count in sorted(coverage["by_loan_type"].items()):
                lines.append(f"  {lt}: {count}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_learning.py -v
git add src/ceres/agents/learning.py tests/test_learning.py
git commit -m "feat: add Learning agent with coverage analysis and partnership recommendations"
```

---

### Task 16: Lab Agent

**Files:**
- Create: `src/ceres/agents/lab.py`
- Create: `tests/test_lab.py`

- [ ] **Step 1: Write failing test**

`tests/test_lab.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from ceres.agents.lab import LabAgent


class TestLabAgent:
    @pytest.mark.asyncio
    async def test_run_tests_approaches_sequentially(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 2000,
            "anti_bot_detected": True, "version": 1,
            "success_rate": 0.0,
        }])
        db.add_strategy_feedback = AsyncMock(return_value="fb1")
        db.upsert_strategy = AsyncMock(return_value={"id": "strat1", "bank_id": "uuid1", "version": 2})

        agent = LabAgent(db=db)

        with patch.object(agent, "_test_approach", new_callable=AsyncMock) as mock_test:
            mock_test.side_effect = [
                {"success": False},  # headless fails
                {"success": True, "bypass_method": "undetected_chrome"},  # UC works
            ]
            result = await agent.run(bank_code="BCA")

        assert result["tests_run"] >= 2
        assert result["fixes_found"] == 1

    @pytest.mark.asyncio
    async def test_escalates_after_max_attempts(self):
        db = AsyncMock()
        db.fetch_active_strategies = AsyncMock(return_value=[{
            "id": "strat1", "bank_id": "uuid1", "bank_code": "BCA",
            "bank_name": "BCA", "website_url": "https://bca.co.id",
            "bypass_method": "headless_browser",
            "loan_page_urls": '["https://bca.co.id/kpr"]',
            "selectors": '{}', "rate_limit_ms": 2000,
            "anti_bot_detected": True, "version": 1,
            "success_rate": 0.0,
        }])
        db.add_strategy_feedback = AsyncMock(return_value="fb1")

        agent = LabAgent(db=db)

        with patch.object(agent, "_test_approach", new_callable=AsyncMock) as mock_test:
            mock_test.return_value = {"success": False}
            result = await agent.run(bank_code="BCA")

        assert result["escalated"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_lab.py -v
```

- [ ] **Step 3: Implement Lab agent**

`src/ceres/agents/lab.py`:
```python
from __future__ import annotations

import asyncio
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.browser.manager import BrowserManager, BrowserType
from ceres.browser.stealth import detect_anti_bot


TEST_APPROACHES = [
    {"name": "undetected_chromedriver", "bypass_method": "undetected_chrome",
     "browser_type": BrowserType.UNDETECTED},
    {"name": "mobile_user_agent", "bypass_method": "headless_browser",
     "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)"},
    {"name": "increased_delay", "bypass_method": "headless_browser",
     "rate_limit_ms": 5000},
    {"name": "proxy_rotation", "bypass_method": "proxy_pool",
     "requires_proxy": True},
    {"name": "api_discovery", "bypass_method": "api",
     "check_api": True},
]

MAX_TEST_ATTEMPTS = 5


class LabAgent(BaseAgent):
    name = "lab"

    async def run(self, bank_code: Optional[str] = None, **kwargs) -> dict:
        strategies = await self.db.fetch_active_strategies()
        if bank_code:
            strategies = [s for s in strategies if s["bank_code"] == bank_code]

        # Focus on failing strategies
        failing = [s for s in strategies if s.get("success_rate", 0) < 0.3 or s.get("anti_bot_detected")]

        results = {"tests_run": 0, "fixes_found": 0, "escalated": 0}

        for strategy in failing:
            fix_found = False

            for approach in TEST_APPROACHES:
                if approach.get("requires_proxy"):
                    continue  # Skip proxy-dependent approaches in v1

                results["tests_run"] += 1
                test_result = await self._test_approach(strategy, approach)

                await self.db.add_strategy_feedback(
                    strategy_id=strategy["id"],
                    test_approach=approach["name"],
                    result="success" if test_result["success"] else "failure",
                    improvement_score=1.0 if test_result["success"] else 0.0,
                    recommended_changes={"bypass_method": approach["bypass_method"]},
                )

                if test_result["success"]:
                    results["fixes_found"] += 1
                    fix_found = True

                    # Auto-apply if successful
                    await self.db.upsert_strategy(
                        bank_id=strategy["bank_id"],
                        selectors=strategy.get("selectors", {}),
                        loan_page_urls=strategy.get("loan_page_urls", []),
                        bypass_method=approach["bypass_method"],
                        rate_limit_ms=approach.get("rate_limit_ms", strategy.get("rate_limit_ms", 2000)),
                    )
                    self.logger.info(
                        f"{strategy['bank_code']}: fix found — {approach['name']}"
                    )
                    break

            if not fix_found:
                results["escalated"] += 1
                self.logger.warning(
                    f"{strategy['bank_code']}: all approaches failed — needs manual review"
                )

        return results

    async def _test_approach(self, strategy: dict, approach: dict) -> dict:
        import json
        loan_urls = strategy.get("loan_page_urls", "[]")
        if isinstance(loan_urls, str):
            loan_urls = json.loads(loan_urls)

        if not loan_urls:
            return {"success": False}

        test_url = loan_urls[0]
        browser_type = approach.get("browser_type", BrowserType.PLAYWRIGHT)
        browser_mgr = BrowserManager()
        browser = None

        try:
            browser, page = await browser_mgr.create_context(browser_type)

            if browser_type == BrowserType.PLAYWRIGHT:
                await page.goto(test_url, wait_until="domcontentloaded", timeout=30000)
                html = await page.content()
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, page.get, test_url)
                await asyncio.sleep(3)
                html = await loop.run_in_executor(None, lambda: page.page_source)

            anti_bot = detect_anti_bot(html)
            content_length = len(html)

            # Success = no anti-bot AND meaningful content
            success = not anti_bot.detected and content_length > 1000
            return {"success": success, "content_length": content_length}

        except Exception as e:
            self.logger.debug(f"Test approach {approach['name']} failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if browser:
                await browser_mgr.close_context(browser, browser_type)
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_lab.py -v
git add src/ceres/agents/lab.py tests/test_lab.py
git commit -m "feat: add Lab agent for testing strategy fixes with approach escalation"
```

---

## Phase 4: CLI, Seed Data & Integration

### Task 17: CLI Entry Point

**Files:**
- Create: `src/ceres/main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

`tests/test_cli.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner

from ceres.main import cli


class TestCLI:
    def test_status_command(self):
        runner = CliRunner()
        with patch("ceres.main.asyncio.run") as mock_run:
            mock_run.return_value = None
            result = runner.invoke(cli, ["status"])
            assert result.exit_code == 0 or "DATABASE_URL" in (result.output or "")

    def test_help_shows_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "scout" in result.output
        assert "crawler" in result.output
        assert "parser" in result.output
        assert "learning" in result.output
        assert "status" in result.output
        assert "daily" in result.output

    def test_crawler_with_bank_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["crawler", "--help"])
        assert "--bank" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/test_cli.py -v
```

- [ ] **Step 3: Implement CLI**

`src/ceres/main.py`:
```python
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from ceres.config import CeresConfig, MissingConfigError, load_config
from ceres.database import Database
from ceres.utils.logging import setup_logging


def _get_config() -> CeresConfig:
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    return load_config(str(config_path) if config_path.exists() else None)


async def _run_agent(agent_name: str, bank_code: Optional[str] = None, **kwargs):
    config = _get_config()
    db = Database(config.database_url)
    await db.connect()

    try:
        if agent_name == "scout":
            from ceres.agents.scout import ScoutAgent
            agent = ScoutAgent(db=db, config=config)
        elif agent_name == "strategist":
            from ceres.agents.strategist import StrategistAgent
            agent = StrategistAgent(db=db, config=config)
        elif agent_name == "crawler":
            from ceres.agents.crawler import CrawlerAgent
            agent = CrawlerAgent(db=db, config=config)
        elif agent_name == "parser":
            from ceres.agents.parser import ParserAgent
            llm = None
            if config.anthropic_api_key:
                import anthropic
                from ceres.extractors.llm import ClaudeLLMExtractor
                client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
                llm = ClaudeLLMExtractor(client=client)
            agent = ParserAgent(db=db, config=config, llm_extractor=llm)
        elif agent_name == "learning":
            from ceres.agents.learning import LearningAgent
            agent = LearningAgent(db=db, config=config)
        elif agent_name == "lab":
            from ceres.agents.lab import LabAgent
            agent = LabAgent(db=db, config=config)
        else:
            click.echo(f"Unknown agent: {agent_name}")
            return

        result = await agent.execute(bank_code=bank_code, **kwargs)

        if isinstance(result, dict) and "report" in result:
            click.echo(result["report"])
        else:
            click.echo(f"[{agent_name}] Result: {result}")

    finally:
        await db.disconnect()


@click.group()
def cli():
    """CERES - Indonesian Loan Programs Crawler"""
    setup_logging()


@cli.command()
def scout():
    """Discover and check all Indonesian bank websites."""
    asyncio.run(_run_agent("scout"))


@cli.command()
@click.option("--bank", default=None, help="Specific bank code (e.g., BCA)")
@click.option("--force", is_flag=True, help="Force strategy rebuild")
def strategist(bank: Optional[str], force: bool):
    """Build or update crawl strategies for banks."""
    asyncio.run(_run_agent("strategist", bank_code=bank, force=force))


@cli.command()
@click.option("--bank", default=None, help="Specific bank code (e.g., BCA)")
def crawler(bank: Optional[str]):
    """Execute crawl strategies to extract loan data."""
    asyncio.run(_run_agent("crawler", bank_code=bank))


@cli.command()
@click.option("--bank", default=None, help="Specific bank code (e.g., BCA)")
def parser(bank: Optional[str]):
    """Normalize crawled data into loan programs."""
    asyncio.run(_run_agent("parser", bank_code=bank))


@cli.command()
@click.option("--days", default=7, help="Analysis window in days")
def learning(days: int):
    """Analyze crawl results and generate recommendations."""
    asyncio.run(_run_agent("learning", days=days))


@cli.command()
@click.option("--bank", default=None, help="Specific bank code (e.g., BCA)")
def lab(bank: Optional[str]):
    """Test new approaches for failing strategies."""
    asyncio.run(_run_agent("lab", bank_code=bank))


@cli.command()
@click.option("--bank", default=None, help="Specific bank code status")
def status(bank: Optional[str]):
    """Show crawl system status."""
    async def _status():
        config = _get_config()
        db = Database(config.database_url)
        await db.connect()
        try:
            if bank:
                banks = await db.fetch_banks()
                target = [b for b in banks if b["bank_code"] == bank.upper()]
                if target:
                    b = target[0]
                    click.echo(f"Bank: {b['bank_code']} — {b['bank_name']}")
                    click.echo(f"Status: {b['website_status']}")
                    click.echo(f"Last crawled: {b.get('last_crawled_at', 'Never')}")
                    programs = await db.fetch_loan_programs(bank_id=b["id"])
                    click.echo(f"Programs: {len(programs)}")
                else:
                    click.echo(f"Bank '{bank}' not found")
            else:
                stats = await db.get_crawl_stats()
                banks = await db.fetch_banks()
                programs = await db.fetch_loan_programs()
                click.echo("=== CERES Status ===")
                click.echo(f"Banks: {len(banks)}")
                click.echo(f"Programs: {len(programs)}")
                click.echo(f"Last 7 days: {stats['total_crawls']} crawls, "
                          f"{stats['successes']} success, {stats['failures']} failed")
        finally:
            await db.disconnect()

    asyncio.run(_status())


@cli.command()
def daily():
    """Run full daily pipeline: scout → crawler → parser → learning."""
    async def _daily():
        config = _get_config()
        db = Database(config.database_url)
        await db.connect()

        try:
            from ceres.agents.scout import ScoutAgent
            from ceres.agents.crawler import CrawlerAgent
            from ceres.agents.parser import ParserAgent
            from ceres.agents.learning import LearningAgent

            click.echo("=== CERES Daily Pipeline ===\n")

            click.echo("[1/4] Running Scout...")
            scout_agent = ScoutAgent(db=db, config=config)
            await scout_agent.execute()

            click.echo("[2/4] Running Crawler...")
            crawler_agent = CrawlerAgent(db=db, config=config)
            await crawler_agent.execute()

            click.echo("[3/4] Running Parser...")
            llm = None
            if config.anthropic_api_key:
                import anthropic
                from ceres.extractors.llm import ClaudeLLMExtractor
                client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
                llm = ClaudeLLMExtractor(client=client)
            parser_agent = ParserAgent(db=db, config=config, llm_extractor=llm)
            await parser_agent.execute()

            click.echo("[4/4] Running Learning...")
            learning_agent = LearningAgent(db=db, config=config)
            result = await learning_agent.execute()

            if isinstance(result, dict) and "report" in result:
                click.echo(f"\n{result['report']}")

            click.echo("\n=== Daily Pipeline Complete ===")

        finally:
            await db.disconnect()

    asyncio.run(_daily())


if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Run tests, commit**

```bash
poetry run pytest tests/test_cli.py -v
git add src/ceres/main.py tests/test_cli.py
git commit -m "feat: add CLI with all agent commands and daily pipeline"
```

---

### Task 18: Database Setup & Bank Seed Script

**Files:**
- Create: `scripts/setup_database.py`
- Create: `scripts/seed_banks.py`

- [ ] **Step 1: Create database setup script**

`scripts/setup_database.py`:
```python
"""Run database/schema.sql against the configured database."""
import asyncio
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import os


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    schema_path = Path(__file__).parent.parent / "database" / "schema.sql"
    if not schema_path.exists():
        print(f"ERROR: Schema file not found at {schema_path}")
        sys.exit(1)

    sql = schema_path.read_text()
    conn = await asyncpg.connect(url)

    try:
        print("Running schema migration...")
        await conn.execute(sql)
        print("Schema created successfully!")

        # Verify tables
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        print(f"Tables: {', '.join(t['tablename'] for t in tables)}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Create bank seed script**

`scripts/seed_banks.py`:
```python
"""Seed the banks table with 62 Indonesian banks."""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BANKS = [
    # BUMN
    ("BRI", "Bank Rakyat Indonesia", "Bank Rakyat Indonesia", "https://bri.co.id", "BUMN", "KONVENSIONAL", True),
    ("BNI", "Bank Negara Indonesia", "Bank Negara Indonesia", "https://www.bni.co.id", "BUMN", "KONVENSIONAL", True),
    ("BTN", "Bank Tabungan Negara", "Bank Tabungan Negara", "https://www.btn.co.id", "BUMN", "KONVENSIONAL", True),
    ("MANDIRI", "Bank Mandiri", "Bank Mandiri", "https://www.bankmandiri.co.id", "BUMN", "KONVENSIONAL", True),

    # Swasta Nasional
    ("BCA", "Bank Central Asia", "Bank Central Asia", "https://www.bca.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("CIMB", "CIMB Niaga", "CIMB Niaga", "https://www.cimbniaga.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PERMATA", "Bank Permata", "Bank Permata", "https://www.permatabank.com", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("DANAMON", "Bank Danamon", "Bank Danamon", "https://www.danamon.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),
    ("PANIN", "Panin Bank", "Panin Bank", "https://www.panin.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BJB", "Bank BJB", "Bank Pembangunan Daerah Jawa Barat dan Banten", "https://www.bankbjb.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BTPN", "Bank BTPN", "Bank BTPN", "https://www.btpn.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("SINARMAS", "Bank Sinarmas", "Bank Sinarmas", "https://www.banksinarmas.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("BUKOPIN", "Bank Bukopin", "Bank Bukopin", "https://www.bukopin.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MAYAPADA", "Bank Mayapada", "Bank Mayapada", "https://www.bankmayapada.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("MEGA", "Bank Mega", "Bank Mega", "https://www.bankmega.com", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("ANDARA", "Bank Andara", "Bank Andara", "https://www.bankandara.co.id", "SWASTA_NASIONAL", "KONVENSIONAL", False),
    ("OCBC", "OCBC NISP", "OCBC NISP", "https://www.ocbc.id", "SWASTA_NASIONAL", "KONVENSIONAL", True),

    # Asing
    ("STANCHART", "Standard Chartered", "Standard Chartered", "https://www.sc.com/id", "ASING", "KONVENSIONAL", False),
    ("CITIBANK", "Citibank", "Citibank", "https://www.citibank.co.id", "ASING", "KONVENSIONAL", False),
    ("HSBC", "HSBC Indonesia", "HSBC Indonesia", "https://www.hsbc.co.id", "ASING", "KONVENSIONAL", False),
    ("DBS", "DBS Indonesia", "DBS Indonesia", "https://www.dbs.id", "ASING", "KONVENSIONAL", False),
    ("UOB", "UOB Indonesia", "UOB Indonesia", "https://www.uob.co.id", "ASING", "KONVENSIONAL", True),
    ("DEUTSCHE", "Deutsche Bank", "Deutsche Bank", "https://www.db.com/indonesia", "ASING", "KONVENSIONAL", False),

    # BPD
    ("BPDDIY", "Bank BPD DIY", "Bank Pembangunan Daerah DIY", "https://www.bpddiy.co.id", "BPD", "KONVENSIONAL", False),
    ("BPDJT", "Bank DKI", "Bank DKI", "https://www.bankdki.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATENG", "Bank Jateng", "Bank Pembangunan Daerah Jawa Tengah", "https://www.bankjateng.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKJATIM", "Bank Jatim", "Bank Pembangunan Daerah Jawa Timur", "https://www.bankjatim.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKKALTENG", "Bank Kalteng", "Bank Pembangunan Daerah Kalimantan Tengah", "https://www.bankkalteng.co.id", "BPD", "KONVENSIONAL", False),
    ("BANKKALIMANTAN", "Bank Kalbar", "Bank Pembangunan Daerah Kalimantan Barat", "https://www.bankkalbar.co.id", "BPD", "KONVENSIONAL", False),
    ("SUMSELBABEL", "Bank Sumsel Babel", "Bank Pembangunan Daerah Sumatera Selatan dan Bangka Belitung", "https://www.banksumselbabel.com", "BPD", "KONVENSIONAL", False),
    ("BANTEN", "Bank Banten", "Bank Pembangunan Daerah Banten", "https://www.bankbanten.co.id", "BPD", "KONVENSIONAL", False),
    ("NUSA", "Bank NTB Syariah", "Bank NTB Syariah", "https://www.bankntbsyariah.co.id", "BPD", "SYARIAH", False),
    ("SAUDARA", "Bank Woori Saudara", "Bank Woori Saudara", "https://www.banksaudara.com", "BPD", "KONVENSIONAL", False),
    ("NTB", "Bank NTB", "Bank NTB", "https://www.bankntb.co.id", "BPD", "KONVENSIONAL", False),
    ("NTT", "Bank NTT", "Bank NTT", "https://www.bankntt.co.id", "BPD", "KONVENSIONAL", False),
    ("MALUKU", "Bank Maluku Malut", "Bank Maluku Malut", "https://www.bankmalukumalut.co.id", "BPD", "KONVENSIONAL", False),
    ("PAPUA", "Bank Papua", "Bank Papua", "https://www.bankpapua.co.id", "BPD", "KONVENSIONAL", False),
    ("SULSELBAR", "Bank Sulselbar", "Bank Sulselbar", "https://www.banksulselbar.co.id", "BPD", "KONVENSIONAL", False),
    ("GORONTALO", "Bank Gorontalo", "Bank Gorontalo", "https://www.bankgorontalo.co.id", "BPD", "KONVENSIONAL", False),
    ("SULUT", "Bank SulutGo", "Bank SulutGo", "https://www.banksulutgo.co.id", "BPD", "KONVENSIONAL", False),
    ("MALUKUUTARA", "Bank Maluku Utara", "Bank Maluku Utara", "https://www.bankmalukuutara.co.id", "BPD", "KONVENSIONAL", False),
    ("KALSEL", "Bank Kalsel", "Bank Kalsel", "https://www.bankkalsel.co.id", "BPD", "KONVENSIONAL", False),
    ("KALBAR", "Bank Kalbar", "Bank Kalbar", "https://www.bankkalbar.co.id", "BPD", "KONVENSIONAL", False),
    ("KALTARA", "Bank Kaltara", "Bank Kaltara", "https://www.bankkaltara.co.id", "BPD", "KONVENSIONAL", False),
    ("BENGKULU", "Bank Bengkulu", "Bank Bengkulu", "https://www.bankbengkulu.co.id", "BPD", "KONVENSIONAL", False),
    ("JAMBI", "Bank Jambi", "Bank Jambi", "https://www.bankjambi.co.id", "BPD", "KONVENSIONAL", False),
    ("RIAUKEPRI", "Bank Riau Kepri", "Bank Riau Kepri", "https://www.bankriaukepri.co.id", "BPD", "KONVENSIONAL", False),
    ("LAMPUNG", "Bank Lampung", "Bank Lampung", "https://www.banklampung.co.id", "BPD", "KONVENSIONAL", False),
    ("SUMSEL", "Bank Sumsel", "Bank Sumsel", "https://www.banksumsel.com", "BPD", "KONVENSIONAL", False),

    # Syariah
    ("BSI", "Bank Syariah Indonesia", "Bank Syariah Indonesia", "https://www.bankbsi.co.id", "SYARIAH", "SYARIAH", True),
    ("BCAS", "BCA Syariah", "BCA Syariah", "https://www.bcasyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BNIS", "BNI Syariah", "BNI Syariah", "https://www.bnisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BRIS", "BRI Syariah", "BRI Syariah", "https://www.brisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("MANDIRIS", "Mandiri Syariah", "Mandiri Syariah", "https://www.mandirisyariah.co.id", "SYARIAH", "SYARIAH", False),
    ("BTNIS", "BTN Syariah", "BTN Syariah", "https://www.btn.co.id/syariah", "SYARIAH", "SYARIAH", False),
    ("JATIMSY", "Bank Jatim Syariah", "Bank Jatim Syariah", "https://www.bankjatim.co.id/syariah", "SYARIAH", "SYARIAH", False),
    ("NAGARI", "Bank Nagari", "Bank Nagari", "https://www.banknagari.co.id", "SYARIAH", "SYARIAH", False),
]


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = await asyncpg.connect(url)

    try:
        print(f"Seeding {len(BANKS)} banks...")
        inserted = 0
        updated = 0

        for bank in BANKS:
            code, name, name_id, website, category, btype, partner = bank
            result = await conn.fetchrow("""
                INSERT INTO banks (bank_code, bank_name, bank_name_indonesia,
                                   website_url, bank_category, bank_type, is_partner_ringkas)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (bank_code) DO UPDATE SET
                    bank_name = EXCLUDED.bank_name,
                    website_url = EXCLUDED.website_url,
                    is_partner_ringkas = EXCLUDED.is_partner_ringkas,
                    updated_at = NOW()
                RETURNING (xmax = 0) AS is_insert
            """, code, name, name_id, website, category, btype, partner)

            if result["is_insert"]:
                inserted += 1
            else:
                updated += 1

        print(f"Done: {inserted} inserted, {updated} updated")
        total = await conn.fetchval("SELECT COUNT(*) FROM banks")
        print(f"Total banks in database: {total}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Commit**

```bash
git add scripts/
git commit -m "feat: add database setup and 62-bank seed scripts"
```

---

### Task 19: Run Schema & Seed Against Supabase

- [ ] **Step 1: Run schema migration**

```bash
cd /Users/edwardpham/Documents/Programming/Projects/ceres
poetry run python scripts/setup_database.py
```
Expected: "Schema created successfully!" with table list

- [ ] **Step 2: Run seed script**

```bash
poetry run python scripts/seed_banks.py
```
Expected: "Done: 62 inserted, 0 updated"

- [ ] **Step 3: Verify with status command**

```bash
poetry run python -m ceres.main status
```
Expected: Shows 62 banks, 0 programs

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "chore: verify database setup and seed data"
```

---

### Task 20: Integration Test & Full Test Suite

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

`tests/test_integration.py`:
```python
"""Integration smoke tests — verify all modules import and wire together."""
import pytest
from unittest.mock import AsyncMock, MagicMock


class TestIntegration:
    def test_all_agents_importable(self):
        from ceres.agents.scout import ScoutAgent
        from ceres.agents.strategist import StrategistAgent
        from ceres.agents.crawler import CrawlerAgent
        from ceres.agents.parser import ParserAgent
        from ceres.agents.learning import LearningAgent
        from ceres.agents.lab import LabAgent

    def test_all_extractors_importable(self):
        from ceres.extractors.selector import SelectorExtractor
        from ceres.extractors.normalizer import normalize_rate, normalize_amount
        from ceres.extractors.llm import ClaudeLLMExtractor

    def test_browser_importable(self):
        from ceres.browser.manager import BrowserManager, BrowserType
        from ceres.browser.stealth import detect_anti_bot
        from ceres.browser.proxy import NoOpProxyProvider

    def test_cli_importable(self):
        from ceres.main import cli

    @pytest.mark.asyncio
    async def test_daily_pipeline_wiring(self):
        """Verify the daily pipeline can wire up all agents with mock DB."""
        from ceres.agents.scout import ScoutAgent
        from ceres.agents.crawler import CrawlerAgent
        from ceres.agents.parser import ParserAgent
        from ceres.agents.learning import LearningAgent

        db = AsyncMock()
        db.fetch_banks = AsyncMock(return_value=[])
        db.fetch_active_strategies = AsyncMock(return_value=[])
        db.fetch_unparsed_html = AsyncMock(return_value=[])
        db.get_crawl_stats = AsyncMock(return_value={
            "total_crawls": 0, "successes": 0, "failures": 0,
            "blocked": 0, "banks_crawled": 0, "total_programs_found": 0,
        })
        db.fetch_loan_programs = AsyncMock(return_value=[])

        await ScoutAgent(db=db).execute()
        await CrawlerAgent(db=db).execute()
        await ParserAgent(db=db).execute()
        await LearningAgent(db=db).execute()
```

- [ ] **Step 2: Run full test suite**

```bash
poetry run pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 3: Check coverage**

```bash
poetry run pytest tests/ --cov=ceres --cov-report=term-missing
```
Expected: 80%+ coverage

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration smoke tests and verify full test suite"
```

---

### Task 21: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

`README.md`:
```markdown
# CERES - Indonesian Loan Programs Crawler

Production-ready web crawling system that extracts loan products from 62+ Indonesian banks, normalizes the data, and generates competitive intelligence for Ringkas.

## Quick Start

### Prerequisites
- Python 3.11+
- Poetry
- PostgreSQL (Supabase)

### Setup

```bash
# Install dependencies
poetry install

# Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and ANTHROPIC_API_KEY

# Setup database
poetry run python scripts/setup_database.py

# Seed banks
poetry run python scripts/seed_banks.py

# Install Playwright browsers
poetry run playwright install chromium
```

### Usage

```bash
# Full daily pipeline
poetry run ceres daily

# Individual agents
poetry run ceres scout              # Check bank websites
poetry run ceres strategist          # Build crawl strategies
poetry run ceres crawler             # Crawl all banks
poetry run ceres crawler --bank BCA  # Crawl specific bank
poetry run ceres parser              # Normalize extracted data
poetry run ceres learning            # Generate reports
poetry run ceres lab --bank BCA      # Test fixes for failing banks

# Status
poetry run ceres status
poetry run ceres status --bank BCA
```

### Testing

```bash
poetry run pytest tests/ -v
poetry run pytest tests/ --cov=ceres --cov-report=term-missing
```

## Architecture

Six async agents orchestrated by a CLI:

| Agent | Schedule | Purpose |
|-------|----------|---------|
| Scout | 06:00 UTC | Discover & health-check bank websites |
| Strategist | On-demand | Build per-bank crawl strategies |
| Crawler | 07:00 UTC | Extract raw HTML using Playwright/UC |
| Parser | 08:30 UTC | Normalize data with CSS selectors + LLM fallback |
| Learning | 09:00 UTC | Analyze patterns, generate recommendations |
| Lab | On-demand | Test fixes for failing strategies |

Self-healing loop: Crawler fails → Learning detects → Lab tests fix → auto-apply if confidence > 0.8.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup, usage, and architecture overview"
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1: Foundation | 1-4 | Project setup, config, database, models |
| 2: Browser & Extraction | 5-9 | Browser manager, proxy/CAPTCHA stubs, extractors, rate limiter |
| 3: Agents | 10-16 | BaseAgent, Scout, Strategist, Crawler, Parser, Learning, Lab |
| 4: CLI & Integration | 17-21 | CLI entry point, seed data, integration tests, README |

Total: **21 tasks**, ~25 files, ~2000 lines of Python
