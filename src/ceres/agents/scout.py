"""Scout agent for checking bank website health status."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

import aiohttp

from ceres.agents.base import BaseAgent
from ceres.database import Database

BATCH_SIZE = 10
DEFAULT_TIMEOUT = 15


class ScoutAgent(BaseAgent):
    """Agent that checks bank website availability and updates status."""

    name: str = "scout"

    def __init__(self, db: Database, config: Optional[Any] = None) -> None:
        super().__init__(db=db, config=config)

    async def run(self, **kwargs) -> dict:
        """Fetch all banks and check their websites in batches.

        Returns a stats dict with banks_checked, active, unreachable,
        and blocked counts.
        """
        banks = await self.db.fetch_banks()
        stats = {"banks_checked": 0, "active": 0, "unreachable": 0, "blocked": 0}

        for i in range(0, len(banks), BATCH_SIZE):
            batch = banks[i : i + BATCH_SIZE]
            results = await asyncio.gather(
                *(self._check_and_update(bank) for bank in batch)
            )
            for status in results:
                stats["banks_checked"] += 1
                stats[status] = stats.get(status, 0) + 1

        self.logger.info(
            f"Scout complete: {stats['banks_checked']} checked, "
            f"{stats['active']} active, {stats['unreachable']} unreachable, "
            f"{stats['blocked']} blocked"
        )
        return stats

    async def _check_and_update(self, bank: dict) -> str:
        """Check a single bank's website and update its status in the DB.

        Args:
            bank: Dict with 'id', 'bank_code', and 'website_url' keys.

        Returns:
            Status string: 'active', 'blocked', or 'unreachable'.
        """
        url = bank["website_url"]
        bank_id = bank["id"]
        status = await self._check_website(url)
        await self.db.update_bank_status(bank_id, status, last_crawled=True)
        self.logger.debug(f"Bank {bank.get('bank_code', bank_id)}: {status}")
        return status

    async def _check_website(self, url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        """Check whether a website is reachable via HTTP HEAD request.

        Args:
            url: The URL to check.
            timeout: Request timeout in seconds.

        Returns:
            'active' if status < 400, 'blocked' if 403, 'unreachable' otherwise.
        """
        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                response = await session.head(url)
                if response.status == 403:
                    return "blocked"
                if response.status < 400:
                    return "active"
                return "unreachable"
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout checking {url}")
            return "unreachable"
        except Exception as exc:
            self.logger.warning(f"Error checking {url}: {exc}")
            return "unreachable"
