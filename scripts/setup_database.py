"""Run database/schema.sql against the configured database."""
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


async def main() -> None:
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
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        print(f"Tables: {', '.join(t['tablename'] for t in tables)}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
