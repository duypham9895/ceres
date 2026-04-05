"""Learning agent with coverage analysis and partnership recommendations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

from ceres.agents.base import BaseAgent
from ceres.database import Database

EXPECTED_LOAN_TYPES = frozenset({
    "KPR", "KPA", "KPT", "MULTIGUNA", "KENDARAAN", "MODAL_KERJA",
})

MIN_PARTNERSHIP_CONFIDENCE = 0.5


class LearningAgent(BaseAgent):
    """Agent that analyzes crawl performance and generates recommendations."""

    name: str = "learning"

    def __init__(self, db: Database, config: Optional[Any] = None) -> None:
        super().__init__(db=db, config=config)

    async def run(self, days: int = 7, **kwargs) -> dict:
        """Analyze crawl stats and generate learning report.

        Args:
            days: Number of days to analyze.

        Returns:
            Dict with overall_success_rate, parse_success_rate, coverage,
            recommendations, and report.
        """
        stats = await self.db.get_crawl_stats(days=days)
        banks = await self.db.fetch_banks()
        programs = await self.db.fetch_loan_programs()
        parse_stats = await self.db.get_parse_stats(days=days)

        total = stats.get("total_crawls", 0)
        successes = stats.get("successful", 0)
        overall_success_rate = successes / total if total > 0 else 0.0

        total_raw = sum(row["total_raw_rows"] for row in parse_stats)
        total_with_programs = sum(
            row["rows_with_programs"] for row in parse_stats
        )
        parse_success_rate = (
            total_with_programs / total_raw if total_raw > 0 else 0.0
        )

        coverage = _analyze_coverage(programs)
        recommendation_ids = await self._generate_recommendations(
            banks, programs, stats,
        )

        report_data = {
            "overall_success_rate": overall_success_rate,
            "parse_success_rate": parse_success_rate,
            "total_crawls": total,
            "banks_crawled": stats.get("banks_crawled", 0),
            "total_programs_found": stats.get("total_programs_found", 0),
            "failures": stats.get("failed", 0),
            "blocked": stats.get("blocked", 0),
            "coverage": coverage,
            "parse_stats": parse_stats,
            "recommendation_ids": recommendation_ids,
        }

        report_text = _format_report(report_data)

        return {
            **report_data,
            "report": report_text,
        }

    async def _generate_recommendations(
        self,
        banks: list[dict],
        programs: list[dict],
        stats: dict,
    ) -> list[str]:
        """Generate partnership and product-gap recommendations.

        Returns:
            List of recommendation IDs created via db.add_recommendation.
        """
        recommendation_ids: list[str] = []

        # Clear existing recommendations before regenerating to avoid duplicates.
        await self.db.clear_recommendations_by_type(rec_type="product_gap")
        await self.db.clear_recommendations_by_type(rec_type="partnership_opportunity")

        # Product gap analysis: find missing loan types.
        covered_types = {
            p.get("loan_type") for p in programs if p.get("loan_type")
        }
        missing_types = EXPECTED_LOAN_TYPES - covered_types

        for loan_type in sorted(missing_types):
            rec = await self.db.add_recommendation(
                rec_type="product_gap",
                priority=3,
                title=f"Missing loan type: {loan_type}",
                summary=f"No banks currently offer {loan_type} products. Consider expanding coverage.",
                impact_score=0.5,
            )
            recommendation_ids.append(str(rec["id"]))

        # Partnership opportunities: non-partner banks with KPR products
        # and average data_confidence >= threshold.
        programs_by_bank: dict[str, list[dict]] = defaultdict(list)
        for prog in programs:
            programs_by_bank[str(prog.get("bank_id", ""))].append(prog)

        for bank in banks:
            if bank.get("is_partner_ringkas", False):
                continue

            bank_code = bank.get("bank_code", "")
            bank_programs = programs_by_bank.get(str(bank.get("id", "")), [])
            kpr_programs = [
                p for p in bank_programs if p.get("loan_type") == "KPR"
            ]

            if not kpr_programs:
                continue

            avg_confidence = sum(
                p.get("data_confidence", 0) for p in kpr_programs
            ) / len(kpr_programs)

            if avg_confidence < MIN_PARTNERSHIP_CONFIDENCE:
                continue

            rec = await self.db.add_recommendation(
                rec_type="partnership_opportunity",
                priority=2,
                title=f"Partnership opportunity: {bank.get('bank_name', bank_code)}",
                summary=(
                    f"{len(kpr_programs)} KPR programs found with "
                    f"{avg_confidence:.0%} avg confidence. "
                    f"Non-partner bank with strong data."
                ),
                impact_score=avg_confidence,
            )
            recommendation_ids.append(str(rec["id"]))

        return recommendation_ids


def _analyze_coverage(programs: list[dict]) -> dict:
    """Analyze product coverage by loan type and bank.

    Returns:
        Dict with by_loan_type, by_bank, banks_with_products,
        and loan_types_covered counts.
    """
    by_loan_type: dict[str, int] = defaultdict(int)
    by_bank: dict[str, int] = defaultdict(int)

    for prog in programs:
        loan_type = prog.get("loan_type", "unknown")
        bank_key = prog.get("bank_code") or str(prog.get("bank_id", "unknown"))
        by_loan_type[loan_type] += 1
        by_bank[bank_key] += 1

    return {
        "by_loan_type": dict(by_loan_type),
        "by_bank": dict(by_bank),
        "banks_with_products": len(by_bank),
        "loan_types_covered": len(by_loan_type),
    }


def _format_report(report_data: dict) -> str:
    """Format report data as a human-readable text report."""
    success_pct = report_data["overall_success_rate"] * 100
    parse_pct = report_data.get("parse_success_rate", 0) * 100
    coverage = report_data.get("coverage", {})
    by_loan_type = coverage.get("by_loan_type", {})
    rec_count = len(report_data.get("recommendation_ids", []))

    lines = [
        "=== CERES Learning Report ===",
        f"Crawl Success:      {success_pct:.1f}%",
        f"Parse Success:      {parse_pct:.1f}%",
        f"Total Crawls:       {report_data['total_crawls']}",
        f"Banks Crawled:      {report_data['banks_crawled']}",
        f"Programs Found:     {report_data['total_programs_found']}",
        f"Failures:           {report_data['failures']}",
        f"Blocked:            {report_data['blocked']}",
        f"Recommendations:    {rec_count}",
        "",
        "--- Coverage by Loan Type ---",
    ]

    for loan_type, count in sorted(by_loan_type.items()):
        lines.append(f"  {loan_type}: {count}")

    if not by_loan_type:
        lines.append("  (no programs found)")

    parse_stats = report_data.get("parse_stats", [])
    if parse_stats:
        lines.append("")
        lines.append("--- Parse Success by Bank ---")
        for row in parse_stats:
            total = row["total_raw_rows"]
            with_progs = row["rows_with_programs"]
            pct = (with_progs / total * 100) if total > 0 else 0
            lines.append(
                f"  {row['bank_code']}: {with_progs}/{total} ({pct:.0f}%)"
            )

    return "\n".join(lines)
