"""Integration smoke tests — verify all modules import and wire together."""

import pytest
from unittest.mock import AsyncMock


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
        db.add_recommendation = AsyncMock(return_value="rec1")

        await ScoutAgent(db=db).execute()
        await CrawlerAgent(db=db).execute()
        await ParserAgent(db=db).execute()
        await LearningAgent(db=db).execute()
