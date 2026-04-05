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
poetry run ceres verify
poetry run ceres verify --docker
poetry run ceres verify-release
poetry run ceres verify-release --bank BCA
poetry run pytest tests/ -v
poetry run pytest tests/ --cov=ceres --cov-report=term-missing
```

Canonical scenario matrix:
- `docs/full-test-scenarios.md`
- Code manifest and API smoke implementation:
  - `src/ceres/verification.py`

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

Self-healing loop: Crawler fails -> Learning detects -> Lab tests fix -> auto-apply if confidence > 0.8.

## Tech Stack

- **Python 3.11+** with asyncio
- **PostgreSQL** (Supabase) via asyncpg
- **Playwright** + Undetected ChromeDriver for browser automation
- **Claude API** for LLM-assisted data extraction
- **Click** for CLI interface
