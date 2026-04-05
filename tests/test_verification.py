import pytest
from unittest.mock import AsyncMock

from ceres.verification import assert_schema_compatibility


class TestSchemaCompatibility:
    @pytest.mark.asyncio
    async def test_schema_compatibility_passes_when_required_columns_exist(self):
        db = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[
            {"table_name": "banks", "column_name": "bank_code"},
            {"table_name": "banks", "column_name": "website_status"},
            {"table_name": "bank_strategies", "column_name": "loan_page_urls"},
            {"table_name": "bank_strategies", "column_name": "success_rate"},
            {"table_name": "crawl_logs", "column_name": "programs_found"},
            {"table_name": "crawl_logs", "column_name": "pages_crawled"},
            {"table_name": "crawl_raw_data", "column_name": "parsed"},
            {"table_name": "crawl_raw_data", "column_name": "programs_produced"},
            {"table_name": "loan_programs", "column_name": "is_latest"},
            {"table_name": "loan_programs", "column_name": "min_tenor_months"},
            {"table_name": "loan_programs", "column_name": "max_tenor_months"},
            {"table_name": "agent_runs", "column_name": "agent_name"},
            {"table_name": "agent_runs", "column_name": "status"},
        ])

        await assert_schema_compatibility(db)

    @pytest.mark.asyncio
    async def test_schema_compatibility_fails_when_required_column_missing(self):
        db = AsyncMock()
        db.pool.fetch = AsyncMock(return_value=[
            {"table_name": "banks", "column_name": "bank_code"},
        ])

        with pytest.raises(RuntimeError, match="crawl_raw_data.programs_produced"):
            await assert_schema_compatibility(db)
