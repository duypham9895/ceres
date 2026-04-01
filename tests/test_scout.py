import pytest
from unittest.mock import AsyncMock, patch

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
