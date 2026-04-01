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
            Dict with overall_success_rate, coverage, recommendations, and report.
        """
        stats = await self.db.get_crawl_stats()
        banks = await self.db.fetch_banks()
        programs = await self.db.fetch_loan_programs()

        total = stats.get("total_crawls", 0)
        successes = stats.get("successes", 0)
        overall_success_rate = successes / total if total > 0 else 0.0

        coverage = _analyze_coverage(programs)
        recommendation_ids = await self._generate_recommendations(
            banks, programs, stats,
        )

        report_data = {
            "overall_success_rate": overall_success_rate,
            "total_crawls": total,
            "banks_crawled": stats.get("banks_crawled", 0),
            "total_programs_found": stats.get("total_programs_found", 0),
            "failures": stats.get("failures", 0),
            "blocked": stats.get("blocked", 0),
            "coverage": coverage,
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

        # Product gap analysis: find missing loan types.
        covered_types = {
            p.get("loan_type") for p in programs if p.get("loan_type")
        }
        missing_types = EXPECTED_LOAN_TYPES - covered_types

        for loan_type in sorted(missing_types):
            rec_id = await self.db.add_recommendation(
                rec_type="product_gap",
                bank_code="ALL",
                details={"missing_loan_type": loan_type},
            )
            recommendation_ids.append(rec_id)

        # Partnership opportunities: non-partner banks with KPR products
        # and average data_confidence >= threshold.
        programs_by_bank: dict[str, list[dict]] = defaultdict(list)
        for prog in programs:
            programs_by_bank[prog.get("bank_code", "")].append(prog)

        for bank in banks:
            if bank.get("is_partner_ringkas", False):
                continue

            bank_code = bank.get("bank_code", "")
            bank_programs = programs_by_bank.get(bank_code, [])
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

            rec_id = await self.db.add_recommendation(
                rec_type="partnership_opportunity",
                bank_code=bank_code,
                details={
                    "bank_name": bank.get("bank_name", ""),
                    "kpr_program_count": len(kpr_programs),
                    "avg_confidence": avg_confidence,
                },
            )
            recommendation_ids.append(rec_id)

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
        bank_code = prog.get("bank_code", "unknown")
        by_loan_type[loan_type] += 1
        by_bank[bank_code] += 1

    return {
        "by_loan_type": dict(by_loan_type),
        "by_bank": dict(by_bank),
        "banks_with_products": len(by_bank),
        "loan_types_covered": len(by_loan_type),
    }


def _format_report(report_data: dict) -> str:
    """Format report data as a human-readable text report."""
    success_pct = report_data["overall_success_rate"] * 100
    coverage = report_data.get("coverage", {})
    by_loan_type = coverage.get("by_loan_type", {})
    rec_count = len(report_data.get("recommendation_ids", []))

    lines = [
        "=== CERES Learning Report ===",
        f"Success Rate:       {success_pct:.1f}%",
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

    return "\n".join(lines)
