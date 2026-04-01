import pytest
from unittest.mock import AsyncMock, patch

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
                bank_code="BCA", bank_name="Bank Central Asia",
                website_url="https://bca.co.id",
                bank_category="SWASTA_NASIONAL", bank_type="KONVENSIONAL",
            )
            assert result["id"] == "uuid1"
            call_sql = pool_instance.fetchrow.call_args[0][0]
            assert "ON CONFLICT" in call_sql
