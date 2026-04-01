import pytest
from ceres.extractors.selector import SelectorExtractor, ExtractionResult


class TestSelectorExtractor:
    def test_extract_with_css_selector(self):
        html = '<div class="product-card"><h3 class="title">KPR BCA</h3><span class="rate">3.5% - 7.0%</span></div>'
        selectors = {
            "container": "div.product-card",
            "fields": {"name": "h3.title", "rate": "span.rate"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert len(results) == 1
        assert results[0].fields["name"] == "KPR BCA"
        assert results[0].fields["rate"] == "3.5% - 7.0%"

    def test_extract_multiple_products(self):
        html = '<div class="product"><h3>Product A</h3></div><div class="product"><h3>Product B</h3></div>'
        selectors = {"container": "div.product", "fields": {"name": "h3"}}
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert len(results) == 2

    def test_extract_with_missing_field_returns_none(self):
        html = '<div class="product"><h3>Product A</h3></div>'
        selectors = {
            "container": "div.product",
            "fields": {"name": "h3", "rate": "span.rate"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert results[0].fields["rate"] is None

    def test_confidence_score_based_on_fields_found(self):
        html = '<div class="p"><h3>Name</h3></div>'
        selectors = {
            "container": "div.p",
            "fields": {"name": "h3", "rate": "span.r", "amount": "span.a"},
        }
        extractor = SelectorExtractor()
        results = extractor.extract(html, selectors)
        assert results[0].confidence < 0.5

    def test_empty_html_returns_empty(self):
        extractor = SelectorExtractor()
        results = extractor.extract("", {"container": "div", "fields": {}})
        assert results == []
