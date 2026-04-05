from __future__ import annotations

from ceres.models import (
    Bank, BankCategory, BankType, LoanType, CrawlStatus,
    LoanProgram, CrawlLog, Strategy,
    calculate_completeness_score,
)


class TestBank:
    def test_bank_creation(self):
        bank = Bank(
            bank_code="BCA",
            bank_name="Bank Central Asia",
            website_url="https://bca.co.id",
            bank_category=BankCategory.SWASTA_NASIONAL,
            bank_type=BankType.KONVENSIONAL,
        )
        assert bank.bank_code == "BCA"
        assert bank.is_partner_ringkas is False

    def test_bank_is_frozen(self):
        bank = Bank(
            bank_code="BCA",
            bank_name="Bank Central Asia",
            website_url="https://bca.co.id",
            bank_category=BankCategory.SWASTA_NASIONAL,
            bank_type=BankType.KONVENSIONAL,
        )
        try:
            bank.bank_code = "NEW"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestCompletenessScore:
    def test_full_data_scores_high(self):
        data = {
            "program_name": "KPR BCA",
            "loan_type": "KPR",
            "min_interest_rate": 3.5,
            "max_interest_rate": 7.0,
            "min_amount": 100_000_000,
            "max_amount": 5_000_000_000,
            "min_tenor_months": 12,
            "max_tenor_months": 300,
        }
        score = calculate_completeness_score(data)
        assert score == 1.0

    def test_minimal_data_scores_low(self):
        data = {"program_name": "KPR BCA", "loan_type": "KPR"}
        score = calculate_completeness_score(data)
        assert score < 0.5

    def test_empty_data_scores_zero(self):
        score = calculate_completeness_score({})
        assert score == 0.0
