---
name: supabase-database
description: Ceres uses Supabase (PgBouncer) as database — requires statement_cache_size=0, no local Postgres in Docker
type: project
---

Ceres connects to Supabase PostgreSQL via PgBouncer pooler.

**Why:** Supabase uses PgBouncer in transaction mode for connection pooling. asyncpg's prepared statement cache is incompatible with PgBouncer.

**How to apply:** Always set `statement_cache_size=0` in asyncpg pool creation. Never add a local Postgres service to docker-compose.yml. The DATABASE_URL in .env points to Supabase's pooler endpoint (port 6543).
