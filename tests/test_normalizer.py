from ceres.extractors.normalizer import (
    normalize_rate,
    normalize_amount,
    normalize_loan_type,
    normalize_tenure,
)


class TestNormalizeRate:
    def test_range_format(self):
        assert normalize_rate("3.5% - 7.0%") == (3.5, 7.0)

    def test_single_rate(self):
        assert normalize_rate("5.25%") == (5.25, 5.25)

    def test_indonesian_format(self):
        assert normalize_rate("Bunga 3,5% s.d. 7,0%") == (3.5, 7.0)

    def test_per_annum(self):
        assert normalize_rate("6.5% p.a.") == (6.5, 6.5)

    def test_invalid_returns_none(self):
        assert normalize_rate("Contact us") == (None, None)


class TestNormalizeAmount:
    def test_rupiah_billions(self):
        assert normalize_amount("Rp 500 Juta - 5 Miliar") == (
            500_000_000,
            5_000_000_000,
        )

    def test_numeric_format(self):
        assert normalize_amount("100.000.000 - 5.000.000.000") == (
            100_000_000,
            5_000_000_000,
        )

    def test_single_amount(self):
        result = normalize_amount("Rp 1 Miliar")
        assert result[0] == 1_000_000_000 or result[1] == 1_000_000_000


class TestNormalizeLoanType:
    def test_kpr_keywords(self):
        assert normalize_loan_type("Kredit Pemilikan Rumah") == "KPR"
        assert normalize_loan_type("KPR BCA") == "KPR"

    def test_kpa_keywords(self):
        assert normalize_loan_type("Kredit Pemilikan Apartemen") == "KPA"

    def test_multiguna(self):
        assert normalize_loan_type("Kredit Multiguna") == "MULTIGUNA"

    def test_kendaraan(self):
        assert normalize_loan_type("Kredit Kendaraan Bermotor") == "KENDARAAN"

    def test_unknown_returns_other(self):
        assert normalize_loan_type("Special Product XYZ") == "OTHER"


class TestNormalizeTenure:
    def test_years_format(self):
        assert normalize_tenure("1 - 25 tahun") == (12, 300)

    def test_months_format(self):
        assert normalize_tenure("12 - 360 bulan") == (12, 360)

    def test_single_max(self):
        assert normalize_tenure("Maks. 20 tahun") == (None, 240)
