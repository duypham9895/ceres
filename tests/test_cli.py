"""Tests for the CLI entry point."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner
from ceres.main import cli


class TestCLI:
    def test_help_shows_commands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert "scout" in result.output
        assert "crawler" in result.output
        assert "parser" in result.output
        assert "learning" in result.output
        assert "status" in result.output
        assert "daily" in result.output
        assert "lab" in result.output
        assert "strategist" in result.output

    def test_crawler_with_bank_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["crawler", "--help"])
        assert "--bank" in result.output

    def test_parser_with_bank_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["parser", "--help"])
        assert "--bank" in result.output

    def test_strategist_with_bank_and_force_options(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["strategist", "--help"])
        assert "--bank" in result.output
        assert "--force" in result.output

    def test_learning_with_days_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["learning", "--help"])
        assert "--days" in result.output

    def test_lab_with_bank_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["lab", "--help"])
        assert "--bank" in result.output

    def test_status_with_bank_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert "--bank" in result.output
