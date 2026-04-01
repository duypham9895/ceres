"""CLI entry point for CERES — Click-based command interface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

from ceres.config import CeresConfig, load_config
from ceres.database import Database
from ceres.utils.logging import setup_logging


def _get_config() -> CeresConfig:
    """Load .env and config.yaml, returning a CeresConfig."""
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    yaml_path = project_root / "config" / "config.yaml"
    yaml_str = str(yaml_path) if yaml_path.exists() else None
    return load_config(yaml_str)


async def _run_agent(agent_name: str, bank_code: Optional[str] = None, **kwargs) -> None:
    """Instantiate and execute an agent by name.

    1. Load config, create and connect Database
    2. Import the appropriate agent class
    3. For parser: optionally create LLM extractor
    4. Execute agent
    5. Print report if available
    6. Disconnect DB in finally block
    """
    config = _get_config()
    db = Database(config.database_url)
    try:
        await db.connect()
        agent = _create_agent(agent_name, db=db, config=config, **kwargs)
        run_kwargs: dict = {}
        if bank_code is not None:
            run_kwargs["bank_code"] = bank_code
        result = await agent.execute(**run_kwargs)
        if result:
            click.echo(f"\n--- {agent_name.upper()} Report ---")
            for key, value in result.items():
                click.echo(f"  {key}: {value}")
    finally:
        await db.disconnect()


def _create_agent(agent_name: str, *, db: Database, config: CeresConfig, **kwargs):
    """Import and instantiate the correct agent class."""
    if agent_name == "scout":
        from ceres.agents.scout import ScoutAgent
        return ScoutAgent(db=db, config=config)

    if agent_name == "strategist":
        from ceres.agents.strategist import StrategistAgent
        return StrategistAgent(db=db, config=config)

    if agent_name == "crawler":
        from ceres.agents.crawler import CrawlerAgent
        return CrawlerAgent(db=db, config=config)

    if agent_name == "parser":
        from ceres.agents.parser import ParserAgent

        llm_extractor = None
        if config.anthropic_api_key:
            try:
                import anthropic
                from ceres.extractors.llm import ClaudeLLMExtractor

                client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
                llm_extractor = ClaudeLLMExtractor(client=client)
            except ImportError:
                click.echo("Warning: anthropic package not installed, LLM extraction disabled")
        return ParserAgent(db=db, config=config, llm_extractor=llm_extractor)

    if agent_name == "learning":
        from ceres.agents.learning import LearningAgent
        return LearningAgent(db=db, config=config)

    if agent_name == "lab":
        from ceres.agents.lab import LabAgent
        return LabAgent(db=db, config=config)

    raise click.ClickException(f"Unknown agent: {agent_name}")


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """CERES — Vietnamese bank loan data pipeline."""
    setup_logging()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@cli.command()
def scout() -> None:
    """Run ScoutAgent to check bank website health."""
    asyncio.run(_run_agent("scout"))


@cli.command()
@click.option("--bank", default=None, help="Filter by bank code.")
@click.option("--force", is_flag=True, default=False, help="Recreate strategies even if active ones exist.")
def strategist(bank: Optional[str], force: bool) -> None:
    """Run StrategistAgent for anti-bot detection and URL discovery."""
    asyncio.run(_run_agent("strategist", bank_code=bank, force=force))


@cli.command()
@click.option("--bank", default=None, help="Filter by bank code.")
def crawler(bank: Optional[str]) -> None:
    """Run CrawlerAgent to fetch bank loan pages."""
    asyncio.run(_run_agent("crawler", bank_code=bank))


@cli.command()
@click.option("--bank", default=None, help="Filter by bank code.")
def parser(bank: Optional[str]) -> None:
    """Run ParserAgent to extract loan data from crawled HTML."""
    asyncio.run(_run_agent("parser", bank_code=bank))


@cli.command()
@click.option("--days", default=7, help="Number of days to analyze (default: 7).")
def learning(days: int) -> None:
    """Run LearningAgent to analyze crawl performance."""
    asyncio.run(_run_agent("learning", days=days))


@cli.command()
@click.option("--bank", default=None, help="Filter by bank code.")
def lab(bank: Optional[str]) -> None:
    """Run LabAgent to test strategy fixes."""
    asyncio.run(_run_agent("lab", bank_code=bank))


@cli.command()
@click.option("--bank", default=None, help="Show status for a specific bank code.")
def status(bank: Optional[str]) -> None:
    """Show overall pipeline status or per-bank status."""
    asyncio.run(_show_status(bank_code=bank))


@cli.command()
def daily() -> None:
    """Run the full daily pipeline: scout -> crawler -> parser -> learning."""
    asyncio.run(_run_daily_pipeline())


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------

async def _show_status(bank_code: Optional[str] = None) -> None:
    """Display crawl stats and bank status."""
    config = _get_config()
    db = Database(config.database_url)
    try:
        await db.connect()

        # Show entity counts
        banks = await db.fetch_banks()
        programs = await db.fetch_loan_programs(latest_only=True)
        click.echo("\n--- CERES Overview ---")
        click.echo(f"  Banks: {len(banks)}")
        click.echo(f"  Loan Programs (latest): {len(programs)}")

        stats = await db.get_crawl_stats(days=7)
        click.echo("\n--- Crawl Stats (last 7 days) ---")
        for key, value in stats.items():
            click.echo(f"  {key}: {value}")

        if bank_code:
            banks = await db.fetch_banks()
            matched = [b for b in banks if dict(b).get("bank_code") == bank_code]
            if matched:
                click.echo(f"\n--- Bank: {bank_code} ---")
                for key, value in dict(matched[0]).items():
                    click.echo(f"  {key}: {value}")
            else:
                click.echo(f"\nBank '{bank_code}' not found.")
    finally:
        await db.disconnect()


# ---------------------------------------------------------------------------
# Daily pipeline
# ---------------------------------------------------------------------------

async def _run_daily_pipeline() -> None:
    """Execute the full pipeline: scout -> crawler -> parser -> learning."""
    config = _get_config()
    db = Database(config.database_url)
    try:
        await db.connect()

        steps = [
            ("scout", {}),
            ("crawler", {}),
            ("parser", {}),
            ("learning", {}),
        ]

        results: dict = {}
        for step_name, step_kwargs in steps:
            click.echo(f"\n>>> Running {step_name}...")
            agent = _create_agent(step_name, db=db, config=config)
            result = await agent.execute(**step_kwargs)
            results[step_name] = result
            click.echo(f"<<< {step_name} complete.")

        click.echo("\n=== Daily Pipeline Summary ===")
        for step_name, result in results.items():
            click.echo(f"\n--- {step_name.upper()} ---")
            if result:
                for key, value in result.items():
                    click.echo(f"  {key}: {value}")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    cli()
