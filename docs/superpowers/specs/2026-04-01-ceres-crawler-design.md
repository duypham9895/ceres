# CERES — Indonesian Loan Programs Crawler

## Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Author:** Edward + Claude

---

## 1. Purpose

Build a production-ready web crawling system that discovers and extracts loan product data from all Indonesian banks (~80), normalizes it into a standard schema, and generates actionable intelligence for Ringkas.

### Business Goals
- Comprehensive loan product database across all Indonesian banks
- Competitive intelligence (rates, fees, terms comparisons)
- Partnership opportunity identification for Ringkas
- Self-healing crawl system requiring minimal manual intervention

---

## 2. Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | Supabase (asyncpg direct) | Full SQL control, async batch ops, Supabase pooler |
| Python env | Poetry + virtualenv | Modern deps management, reproducible builds |
| Primary browser | Playwright | Fast, async, stealth plugin support |
| Fallback browser | Undetected ChromeDriver | Proven anti-fingerprint bypass |
| Proxy/CAPTCHA | Stubbed interfaces | Build ABCs now, activate when needed |
| Parser strategy | Selectors + LLM fallback | CSS/XPath first, Claude API for low-confidence |
| Async model | asyncio throughout | Concurrent bank crawling, non-blocking I/O |

---

## 3. System Architecture

```
ORCHESTRATOR (main.py / CLI)
    │
    ├── DISCOVERY LAYER
    │   ├── Scout Agent      — Discover & track banks (HTTP checks, OJK registry)
    │   └── Strategist Agent — Build per-bank crawl strategies
    │
    ├── EXECUTION LAYER
    │   ├── Crawler Agent    — Execute strategies (Playwright / UC ChromeDriver)
    │   └── Parser Agent     — Normalize data (selectors + LLM fallback)
    │
    └── INTELLIGENCE LAYER
        ├── Learning Agent   — Analyze patterns, generate recommendations
        └── Lab Agent        — Test fixes for failing strategies
```

### Daily Schedule (UTC)
| Time  | Agent     | Task |
|-------|-----------|------|
| 06:00 | Scout     | Discover/update bank list |
| 07:00 | Crawler   | Execute all active strategies |
| 08:30 | Parser    | Normalize extracted data |
| 09:00 | Learning  | Analyze results, generate reports |

### Self-Healing Loop
```
Crawler fails → Learning detects pattern → Lab tests alternative approach
    ├── Success (confidence > 0.8) → Auto-update strategy
    └── Failure (5 attempts) → Flag for manual review
```

---

## 4. Database Schema

**PostgreSQL on Supabase** — 7 tables with UUID primary keys, JSONB for flexible fields, triggers for `updated_at`.

### banks
Master data for all Indonesian banks.
- `id` UUID PK
- `bank_code` VARCHAR UNIQUE (e.g., 'BCA', 'BRI')
- `bank_name`, `bank_name_indonesia` VARCHAR
- `logo_url`, `website_url` VARCHAR
- `is_partner_ringkas` BOOLEAN DEFAULT false
- `bank_category` ENUM: BUMN, SWASTA_NASIONAL, BPD, ASING, SYARIAH
- `bank_type` ENUM: KONVENSIONAL, SYARIAH
- `website_status` ENUM: active, unreachable, blocked, unknown
- `api_available` BOOLEAN DEFAULT false
- `last_crawled_at`, `last_success_at` TIMESTAMPTZ
- `crawl_streak` INTEGER DEFAULT 0
- `created_at`, `updated_at` TIMESTAMPTZ

### bank_strategies
Per-bank crawl configuration with versioning.
- `id` UUID PK
- `bank_id` UUID FK → banks
- `version` INTEGER DEFAULT 1
- `anti_bot_detected` BOOLEAN DEFAULT false
- `anti_bot_type` VARCHAR (cloudflare, recaptcha, custom_js, fingerprint, datadome)
- `bypass_method` VARCHAR (headless_browser, api, proxy_pool, undetected_chrome, manual)
- `selectors` JSONB — CSS/XPath extraction rules
- `loan_page_urls` JSONB — list of URLs to crawl
- `rate_limit_ms` INTEGER DEFAULT 2000
- `required_headers`, `user_agent_pattern` JSONB
- `proxy_required` BOOLEAN DEFAULT false
- `proxy_type` VARCHAR
- `success_rate` DECIMAL DEFAULT 0
- `total_attempts`, `total_successes` INTEGER DEFAULT 0
- `is_active` BOOLEAN DEFAULT true
- `is_primary` BOOLEAN DEFAULT true
- `created_at`, `updated_at` TIMESTAMPTZ

### loan_programs
Normalized loan products — the core output.
- `id` UUID PK
- `bank_id` UUID FK → banks
- `program_name` VARCHAR
- `loan_type` ENUM: KPR, KPA, KPT, MULTIGUNA, KENDARAAN, MODAL_KERJA, INVESTASI, PENDIDIKAN, PMI, TAKE_OVER, REFINANCING, OTHER
- `min_loan_amount`, `max_loan_amount` DECIMAL
- `min_tenure_months`, `max_tenure_months` INTEGER
- `min_interest_rate`, `max_interest_rate` DECIMAL (percentage)
- `rate_type` ENUM: FIXED, FLOATING, MIXED
- `min_dp_percentage` DECIMAL
- `min_age`, `max_age` INTEGER
- `min_income` DECIMAL
- `employment_types` JSONB (array)
- `collateral_required` BOOLEAN
- `collateral_type` VARCHAR
- `features`, `special_offers` JSONB
- `admin_fee`, `provisi_fee`, `appraisal_fee` VARCHAR
- `early_repayment_penalty` VARCHAR
- `required_documents` JSONB
- `available_regions` JSONB (array or 'ALL')
- `is_latest` BOOLEAN DEFAULT true
- `is_active` BOOLEAN DEFAULT true
- `is_verified` BOOLEAN DEFAULT false
- `data_confidence` DECIMAL (0-1)
- `completeness_score` DECIMAL (0-1)
- `raw_data` JSONB
- `source_url` VARCHAR
- `created_at`, `updated_at` TIMESTAMPTZ

### crawl_logs
Execution history for every crawl attempt.
- `id` UUID PK
- `bank_id` UUID FK → banks
- `strategy_id` UUID FK → bank_strategies
- `started_at`, `completed_at` TIMESTAMPTZ
- `duration_ms` INTEGER
- `status` ENUM: queued, running, success, partial, failed, blocked, timeout
- `programs_found`, `programs_new`, `programs_updated` INTEGER DEFAULT 0
- `error_type`, `error_message` VARCHAR
- `anti_bot_detected` BOOLEAN DEFAULT false
- `screenshot_url`, `html_sample` TEXT
- `created_at` TIMESTAMPTZ

### strategy_feedback
Learning loop data for strategy improvements.
- `id` UUID PK
- `strategy_id` UUID FK → bank_strategies
- `test_approach` VARCHAR
- `result` ENUM: success, partial, failure
- `improvement_score` DECIMAL
- `recommended_changes` JSONB
- `applied` BOOLEAN DEFAULT false
- `created_at` TIMESTAMPTZ

### ringkas_recommendations
Strategic recommendations generated by Learning agent.
- `id` UUID PK
- `rec_type` ENUM: partnership_opportunity, product_gap, competitive_analysis, pricing, market_trend
- `priority` INTEGER (1-5)
- `impact_score` DECIMAL
- `title`, `summary` VARCHAR
- `detailed_analysis` TEXT
- `suggested_actions` JSONB
- `related_bank_ids` JSONB (array of UUIDs)
- `status` ENUM: pending, reviewed, approved, implemented, dismissed
- `created_at`, `updated_at` TIMESTAMPTZ

### proxies
Proxy pool management (stubbed for v1).
- `id` UUID PK
- `proxy_url` VARCHAR
- `proxy_type` ENUM: residential, datacenter, mobile
- `country` VARCHAR DEFAULT 'ID'
- `avg_response_ms` INTEGER
- `success_rate` DECIMAL DEFAULT 1.0
- `status` ENUM: active, rate_limited, banned, expired
- `rotation_enabled` BOOLEAN DEFAULT true
- `rotation_weight` DECIMAL DEFAULT 1.0
- `last_used_at` TIMESTAMPTZ
- `created_at`, `updated_at` TIMESTAMPTZ

---

## 5. Agent Specifications

### Scout Agent
**Trigger:** Daily 06:00 UTC or manual
**Input:** Current banks table
**Output:** Updated banks table with status changes, new discoveries

Tasks:
1. HTTP HEAD/GET check on all bank website URLs
2. Update `website_status` based on response
3. Detect new loan product pages (sitemap.xml, common URL patterns)
4. Update `last_crawled_at` timestamps
5. Flag new banks discovered from OJK registry or cross-references

### Strategist Agent
**Trigger:** On-demand (new bank discovered, strategy failed)
**Input:** Bank record, website URL
**Output:** New/updated bank_strategies record

Tasks:
1. Visit bank homepage with Playwright
2. Detect anti-bot measures (Cloudflare challenge page, reCAPTCHA elements, fingerprint JS)
3. Discover loan product page URLs
4. Build CSS/XPath selectors by analyzing page structure
5. Set rate limits, headers, user-agent based on detection
6. Store strategy with version 1

Decision framework:
- API available → bypass_method = 'api'
- Cloudflare detected → bypass_method = 'headless_browser' + stealth
- Fingerprint detected → bypass_method = 'undetected_chrome'
- IP blocked → bypass_method = 'proxy_pool'
- Default → bypass_method = 'headless_browser'

### Crawler Agent
**Trigger:** Daily 07:00 UTC or manual (per-bank)
**Input:** Active strategies from bank_strategies
**Output:** Raw HTML/data stored, crawl_logs entries

Tasks:
1. Load strategy for target bank
2. Initialize appropriate browser (Playwright or Undetected ChromeDriver)
3. Navigate to each loan page URL in strategy
4. Handle anti-bot challenges (wait for Cloudflare, etc.)
5. Extract raw HTML content
6. Follow pagination if present
7. Log results to crawl_logs
8. Retry on failure (3 attempts, exponential backoff)

Concurrency: Up to 5 banks in parallel (configurable), sequential pages per bank.

### Parser Agent
**Trigger:** After Crawler completes
**Input:** Raw HTML from crawler, strategy selectors
**Output:** Normalized loan_programs records

Tasks:
1. Apply CSS/XPath selectors from strategy to extract fields
2. Calculate extraction confidence per field
3. If overall confidence < 0.5 → invoke LLM fallback (Claude API)
4. Map extracted data to loan_programs schema
5. Normalize Indonesian banking terminology (e.g., "Bunga" → interest_rate)
6. Deduplicate against existing programs
7. Calculate completeness_score
8. Upsert to loan_programs (mark previous versions as `is_latest = false`)

### Learning Agent
**Trigger:** Daily 09:00 UTC
**Input:** crawl_logs, loan_programs, bank_strategies
**Output:** ringkas_recommendations, strategy improvement suggestions

Analysis:
1. Success rate per bank and overall
2. Anti-bot pattern detection (new blocking types appearing)
3. Data quality analysis (incomplete programs, missing fields)
4. Coverage analysis (loan types, regions, products per bank)
5. Staleness detection (unchanged programs, long gaps)

Recommendations:
- Partnership opportunities (non-partner banks with competitive products)
- Product gaps (loan types Ringkas doesn't cover)
- Market trends (rate changes, new product launches)
- Data quality actions (banks needing strategy updates)

### Lab Agent
**Trigger:** On-demand (strategy failing, Learning recommendation)
**Input:** Failing strategy, bank record
**Output:** strategy_feedback records, potentially updated strategy

Test approaches (sequential):
1. Undetected ChromeDriver with stealth settings
2. Proxy rotation (if proxies configured)
3. Different timing (off-peak hours)
4. Mobile user agent
5. API discovery (check for XHR endpoints in network tab)

Escalation: After 5 failed approaches → flag for manual review.

---

## 6. External Interfaces

### Stubbed Interfaces (v1)

```python
class ProxyProvider(ABC):
    async def get_proxy(self) -> Optional[str]: ...
    async def report_result(self, proxy: str, success: bool): ...

class CaptchaSolver(ABC):
    async def solve(self, challenge_type: str, page_url: str) -> Optional[str]: ...

class LLMExtractor(ABC):
    async def extract_loan_data(self, html: str, bank_name: str) -> dict: ...
```

`ProxyProvider` and `CaptchaSolver` have no-op defaults. `LLMExtractor` has a Claude API implementation.

### CLI Interface

```bash
python -m ceres.main daily          # Full daily pipeline
python -m ceres.main scout          # Discovery only
python -m ceres.main crawler        # All banks
python -m ceres.main crawler --bank BRI  # Single bank
python -m ceres.main parser         # Normalize pending data
python -m ceres.main learning       # Analysis & recommendations
python -m ceres.main lab --bank BCA # Test strategies for a bank
python -m ceres.main status         # Overall dashboard
python -m ceres.main status --bank BCA  # Per-bank status
```

---

## 7. Code Structure

```
ceres/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── config/
│   └── config.yaml
├── database/
│   └── schema.sql
├── src/
│   └── ceres/
│       ├── __init__.py
│       ├── main.py                 # CLI entry point (click/typer)
│       ├── config.py               # Config loader (.env + yaml)
│       ├── database.py             # asyncpg pool, queries
│       ├── models.py               # Dataclasses for domain objects
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py             # BaseAgent ABC
│       │   ├── scout.py
│       │   ├── strategist.py
│       │   ├── crawler.py
│       │   ├── parser.py
│       │   ├── learning.py
│       │   └── lab.py
│       ├── browser/
│       │   ├── __init__.py
│       │   ├── manager.py          # BrowserManager (Playwright + UC)
│       │   ├── stealth.py          # Stealth/anti-detect config
│       │   └── proxy.py            # ProxyProvider ABC + NoOpProxy
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── selector.py         # CSS/XPath extraction
│       │   ├── llm.py              # Claude API fallback extractor
│       │   └── normalizer.py       # Indonesian banking term normalization
│       └── utils/
│           ├── __init__.py
│           ├── rate_limiter.py
│           ├── captcha.py          # CaptchaSolver ABC + NoOpSolver
│           └── logging.py         # Structured logging
├── scripts/
│   ├── setup_database.py
│   └── seed_banks.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_scout.py
│   ├── test_crawler.py
│   ├── test_parser.py
│   ├── test_normalizer.py
│   └── test_learning.py
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-01-ceres-crawler-design.md
```

~25 Python files, ~1500-2000 lines for v1.

---

## 8. Seed Data

62 Indonesian banks across 5 categories:

- **BUMN (4):** BRI, BNI, BTN, MANDIRI
- **Swasta Nasional (13):** BCA, CIMB, PERMATA, DANAMON, PANIN, BJB, BTPN, SINARMAS, BUKOPIN, MAYAPADA, MEGA, ANDARA, OCBC
- **Asing (6):** STANCHART, CITIBANK, HSBC, DBS, UOB, DEUTSCHE
- **BPD (27):** Regional development banks across all provinces
- **Syariah (8):** BSI, BCAS, BNIS, BRIS, MANDIRIS, BTNIS, JATIMSY, NAGARI

Each seeded with: bank_code, bank_name, website_url, bank_category, bank_type.

---

## 9. Success Criteria

1. Can crawl all 62 seed banks (or gracefully handle unreachable ones)
2. Extracts loan programs with 80%+ completeness score
3. Self-heals from failures via Lab agent
4. Daily reports generated with coverage and quality metrics
5. Ringkas recommendations are actionable (partnership, product gaps)
6. Zero manual intervention for routine crawls
