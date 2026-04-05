# Ceres — Local Docker Setup Guide

Complete step-by-step guide to run the full Ceres system on your laptop.

---

## Prerequisites

Install these before starting:

| Tool | Version | Install |
|------|---------|---------|
| **Docker Desktop** | 4.x+ | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.x+ | Already installed if you cloned this repo |

Verify Docker is running:

```bash
docker --version        # Docker version 27.x.x
docker compose version  # Docker Compose version v2.x.x
```

---

## Step 1: Clone the Repository

```bash
git clone git@github.com:duypham9895/ceres.git
cd ceres
```

---

## Step 2: Create the `.env` File

Copy the example and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` in your editor and configure:

```env
# ─── Required ────────────────────────────────────────────
# Docker Compose overrides this automatically — leave as-is
DATABASE_URL=postgresql://ceres:ceres@postgres:5432/ceres
REDIS_URL=redis://redis:6379

# ─── LLM Extraction (at least one required) ─────────────
# The crawler uses LLM to extract loan data from bank pages.
# You need at least ONE of these API keys.
#
# Option A: Anthropic Claude (recommended, more accurate)
#   Get key at: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-your-key-here
#
# Option B: MiniMax (cheaper alternative)
#   Get key at: https://www.minimax.chat/
MINIMAX_API_KEY=

# ─── Authentication (optional) ──────────────────────────
# Set a shared secret to protect the dashboard and API.
# Leave empty to disable auth (OK for local development).
CERES_AUTH_TOKEN=
VITE_AUTH_TOKEN=

# ─── Proxy (optional) ───────────────────────────────────
# Some Indonesian banks block datacenter IPs.
# Single proxy:
PROXY_URL=
# Or multiple proxies (comma-separated):
PROXY_LIST=

# ─── Captcha Solving (optional) ─────────────────────────
# For banks with reCAPTCHA protection.
# Get key at: https://2captcha.com/
TWOCAPTCHA_API_KEY=
```

### Minimum Required

For the system to crawl loan data, you need **at least one LLM API key**:

- `ANTHROPIC_API_KEY` — Claude API (recommended)
- `MINIMAX_API_KEY` — MiniMax API (alternative)

Everything else is optional for local development.

---

## Step 3: Build and Start

```bash
docker compose up --build -d
```

This starts 5 services:

| Service | Port | Purpose |
|---------|------|---------|
| **postgres** | 5432 | PostgreSQL database (auto-creates tables on first run) |
| **redis** | 6379 | Job queue + pub/sub (persistent with AOF) |
| **api** | 8000 | FastAPI backend |
| **worker** | — | arq worker (processes crawl jobs, runs daily cron at 2 AM) |
| **dashboard** | 3000 | React ops dashboard |

### Startup Order

Docker Compose handles dependencies automatically:

```
postgres (healthy) ──┐
                     ├──> api (healthy) ──> worker
redis (healthy)    ──┘                  ──> dashboard
```

First build takes ~5 minutes (downloads Playwright browser + npm packages).
Subsequent starts take ~10 seconds.

---

## Step 4: Verify Everything is Running

```bash
# Check all services are up
docker compose ps
```

Expected output — all services should show `Up (healthy)`:

```
NAME              STATUS          PORTS
ceres-postgres-1  Up (healthy)   0.0.0.0:5432->5432/tcp
ceres-redis-1     Up (healthy)   0.0.0.0:6379->6379/tcp
ceres-api-1       Up (healthy)   0.0.0.0:8000->8000/tcp
ceres-worker-1    Up             
ceres-dashboard-1 Up             0.0.0.0:3000->3000/tcp
```

Test the API:

```bash
curl http://localhost:8000/api/status
```

Should return JSON with `"status": "ok"`.

---

## Step 5: Open the Dashboard

Open your browser:

```
http://localhost:3000
```

You should see the Ceres ops dashboard with:
- **Overview** — KPIs, heatmap, alerts
- **Banks** — all Indonesian banks
- **Loan Programs** — extracted loan data
- **Jobs** — queue status and job management
- **Crawl Logs** — crawl history
- **Strategies** — per-bank crawl strategies

---

## Step 6: Run Your First Crawl

### Option A: From the Dashboard

1. Go to `http://localhost:3000`
2. Click **"Crawl All Banks"** button on the Overview page
3. Watch the pipeline progress in the sidebar

### Option B: From the API

```bash
# Crawl all banks (full pipeline: scout → strategist → crawler → parser)
curl -X POST http://localhost:8000/api/crawl/daily

# Crawl a single bank
curl -X POST http://localhost:8000/api/crawl/crawler?bank_code=BCA

# Check job status
curl http://localhost:8000/api/queue/status
```

### Option C: From the CLI (inside the container)

```bash
docker compose exec api ceres daily
```

### What Happens During a Crawl

```
1. Scout     — checks which bank websites are reachable
2. Strategist — visits each bank, discovers loan page URLs, generates CSS selectors
3. Crawler   — fetches loan pages using Playwright (headless Chrome)
4. Parser    — extracts loan programs using selectors → heuristics → LLM fallback
5. Learning  — analyzes results, generates recommendations
```

The full pipeline takes ~10-30 minutes depending on how many banks are reachable.

---

## Step 7: Automatic Daily Crawl

The worker runs a **cron job at 2:00 AM UTC** automatically.
No setup needed — it runs as long as the worker container is up.

To check the schedule:

```bash
docker compose logs worker | grep "cron"
```

---

## Common Commands

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f worker

# Last 100 lines
docker compose logs --tail=100 worker
```

### Stop / Start / Restart

```bash
# Stop everything (data persists)
docker compose down

# Stop and DELETE all data (fresh start)
docker compose down -v

# Restart a specific service
docker compose restart worker

# Rebuild after code changes
docker compose up --build -d
```

### Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U ceres -d ceres

# Useful queries:
# See all banks
SELECT bank_code, bank_name, website_status FROM banks ORDER BY bank_code;

# See latest loan programs
SELECT b.bank_code, lp.program_name, lp.min_interest_rate, lp.loan_type
FROM loan_programs lp
JOIN banks b ON b.id = lp.bank_id
WHERE lp.is_latest = true
ORDER BY lp.min_interest_rate;

# See recent crawl jobs
SELECT agent_name, status, started_at, finished_at 
FROM agent_runs 
ORDER BY started_at DESC 
LIMIT 20;
```

### Redis Queue Inspection

```bash
docker compose exec redis redis-cli

# Check queue depth
ZCARD arq:queue

# List pending jobs
ZRANGE arq:queue 0 -1
```

---

## Troubleshooting

### "Cannot connect to database"

```bash
# Check postgres is running
docker compose ps postgres

# Check logs
docker compose logs postgres

# Verify connectivity
docker compose exec api python -c "import asyncpg; print('OK')"
```

### "No loan programs found after crawl"

1. Check you have an LLM API key set in `.env`:
   ```bash
   grep "API_KEY" .env
   ```

2. Check crawler logs for errors:
   ```bash
   docker compose logs worker | grep -i "error\|failed\|blocked"
   ```

3. Check if banks are reachable:
   ```bash
   curl http://localhost:8000/api/banks | python3 -m json.tool | grep website_status
   ```

### "Dashboard shows 0% quality"

This is normal on first run — quality populates after the first successful crawl completes.

### "Container keeps restarting"

```bash
# Check what's failing
docker compose logs --tail=50 <service-name>

# Common causes:
# - Missing .env file
# - Invalid API keys
# - Port already in use (5432, 6379, 8000, 3000)
```

### "Port already in use"

```bash
# Find what's using the port (e.g., 5432)
lsof -i :5432

# Either stop that process, or change the port in docker-compose.yml:
# ports: ["5433:5432"]  # maps to localhost:5433
```

### Build Fails on Apple Silicon (M1/M2/M3)

The Playwright Docker image supports ARM64. If you still get issues:

```bash
# Force platform
docker compose build --no-cache
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Dashboard (:3000)                 │
│                    React + Vite                      │
└─────────────────┬───────────────────────────────────┘
                  │ REST API + WebSocket
┌─────────────────▼───────────────────────────────────┐
│                    API Server (:8000)                │
│                FastAPI + uvicorn                     │
│  ┌───────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Routes    │  │ Tasks    │  │ WebSocket        │  │
│  │ (REST)    │  │ (Jobs)   │  │ (Live updates)   │  │
│  └───────────┘  └──────────┘  └──────────────────┘  │
└────────┬────────────────┬───────────────────────────┘
         │                │ enqueue
┌────────▼────────┐  ┌────▼───────────────────────────┐
│   PostgreSQL    │  │       Redis (:6379)             │
│    (:5432)      │  │   Job Queue + Pub/Sub           │
│                 │  └────┬───────────────────────────┘
│  banks          │       │ dequeue
│  bank_strategies│  ┌────▼───────────────────────────┐
│  loan_programs  │  │       Worker                    │
│  crawl_logs     │  │   arq + Playwright              │
│  crawl_raw_data │  │                                 │
│  agent_runs     │  │  Scout → Strategist → Crawler   │
│                 │  │  → Parser → Learning            │
└─────────────────┘  │                                 │
                     │  Cron: daily crawl at 2 AM UTC  │
                     └─────────────────────────────────┘
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes* | — | PostgreSQL connection string (*auto-set by Docker Compose) |
| `REDIS_URL` | Yes* | `redis://redis:6379` | Redis connection string (*auto-set) |
| `ANTHROPIC_API_KEY` | One LLM key required | — | Claude API key for LLM extraction |
| `MINIMAX_API_KEY` | One LLM key required | — | MiniMax API key (alternative to Claude) |
| `CERES_AUTH_TOKEN` | No | — | API authentication token (empty = auth disabled) |
| `VITE_AUTH_TOKEN` | No | — | Dashboard auth token (must match `CERES_AUTH_TOKEN`) |
| `PROXY_URL` | No | — | Single proxy URL for crawling |
| `PROXY_LIST` | No | — | Comma-separated proxy URLs for rotation |
| `TWOCAPTCHA_API_KEY` | No | — | 2captcha API key for solving reCAPTCHAs |
| `CERES_MAX_RETRIES` | No | `3` | Max retry attempts for failed crawl jobs |
| `S3_BUCKET` | No | — | S3 bucket for raw HTML archival |
| `S3_ACCESS_KEY` | No | — | S3 access key |
| `S3_SECRET_KEY` | No | — | S3 secret key |
