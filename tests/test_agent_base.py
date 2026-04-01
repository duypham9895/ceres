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
