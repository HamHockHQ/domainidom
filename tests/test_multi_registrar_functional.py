"""Functional tests for multi-registrar pricing system."""

import pytest
import tempfile
import os
from pathlib import Path
from domainidom.models import RegistrarPrice, PriceComparison, DomainCheckResult, ScoredCandidate
from domainidom.package import write_reports
import json


class TestMultiRegistrarFunctional:
    """Functional tests that verify the multi-registrar system works end-to-end."""

    def test_price_comparison_model(self):
        """Test that the PriceComparison model works correctly."""
        prices = [
            RegistrarPrice("namecom", 15.99, "USD", True),
            RegistrarPrice("godaddy", 12.99, "USD", True),
            RegistrarPrice("cloudflare", None, error="not_available"),
        ]
        comparison = PriceComparison("example.com", prices)

        assert comparison.domain == "example.com"
        assert len(comparison.prices) == 3
        assert comparison.best_price is not None
        assert comparison.best_price.registrar == "godaddy"
        assert comparison.best_price.price_usd == 12.99

    def test_price_comparison_no_available(self):
        """Test price comparison when no registrars have available domains."""
        prices = [
            RegistrarPrice("namecom", None, error="not_available"),
            RegistrarPrice("godaddy", 12.99, "USD", False),  # price but not available
        ]
        comparison = PriceComparison("example.com", prices)

        assert comparison.best_price is None

    def test_domain_check_result_with_price_comparison(self):
        """Test that DomainCheckResult correctly includes price comparison data."""
        price_comparison = PriceComparison(
            "example.com",
            [
                RegistrarPrice("namecom", 15.99, "USD", True),
                RegistrarPrice("godaddy", 12.99, "USD", True),
            ],
        )

        dcr = DomainCheckResult(
            "example.com", True, 12.99, "multi-registrar", None, price_comparison
        )

        assert dcr.price_comparison is not None
        assert dcr.price_comparison.best_price.price_usd == 12.99
        assert dcr.registrar_price_usd == 12.99

    def test_json_report_with_price_comparison(self):
        """Test that JSON reports include the new price comparison data."""
        price_comparison = PriceComparison(
            "example.com",
            [
                RegistrarPrice("namecom", 15.99, "USD", True, "https://name.com"),
                RegistrarPrice("godaddy", 12.99, "USD", True, "https://godaddy.com"),
            ],
        )

        domain_result = DomainCheckResult(
            "example.com", True, 12.99, "multi-registrar", None, price_comparison
        )

        scored_candidate = ScoredCandidate("Example", 85.5, {"length": 75.0}, [domain_result])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            try:
                write_reports([scored_candidate], Path(f.name))

                # Read and parse the JSON
                with open(f.name, "r") as rf:
                    data = json.load(rf)

                # Verify structure
                assert "results" in data
                assert len(data["results"]) == 1

                result = data["results"][0]
                assert result["name"] == "Example"
                assert len(result["domains"]) == 1

                domain = result["domains"][0]
                assert domain["domain"] == "example.com"
                assert "price_comparison" in domain

                price_comp = domain["price_comparison"]
                assert "registrar_prices" in price_comp
                assert "best_price" in price_comp
                assert len(price_comp["registrar_prices"]) == 2

                # Check best price
                best_price = price_comp["best_price"]
                assert best_price["registrar"] == "godaddy"
                assert best_price["price_usd"] == 12.99

            finally:
                os.unlink(f.name)

    def test_csv_report_with_price_comparison(self):
        """Test that CSV reports include the new price comparison columns."""
        price_comparison = PriceComparison(
            "example.com",
            [
                RegistrarPrice("namecom", 15.99, "USD", True),
                RegistrarPrice("godaddy", 12.99, "USD", True),
                RegistrarPrice("cloudflare", None, error="not_available"),
                RegistrarPrice("namecheap", 14.99, "USD", True),
            ],
        )

        domain_result = DomainCheckResult(
            "example.com", True, 12.99, "multi-registrar", None, price_comparison
        )

        scored_candidate = ScoredCandidate("Example", 85.5, {"length": 75.0}, [domain_result])

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            try:
                write_reports([scored_candidate], Path(f.name))

                # Read and check CSV content
                with open(f.name, "r") as rf:
                    content = rf.read()

                lines = content.strip().split("\n")
                assert len(lines) == 2  # Header + 1 data row

                header = lines[0].split(",")
                data = lines[1].split(",")

                # Check for new columns
                assert "best_price_usd" in header
                assert "best_registrar" in header
                assert "namecom_price" in header
                assert "godaddy_price" in header
                assert "cloudflare_price" in header
                assert "namecheap_price" in header

                # Check data values
                best_price_idx = header.index("best_price_usd")
                best_registrar_idx = header.index("best_registrar")
                namecom_price_idx = header.index("namecom_price")
                godaddy_price_idx = header.index("godaddy_price")

                assert data[best_price_idx] == "12.99"
                assert data[best_registrar_idx] == "godaddy"
                assert data[namecom_price_idx] == "15.99"
                assert data[godaddy_price_idx] == "12.99"

            finally:
                os.unlink(f.name)

    def test_backward_compatibility(self):
        """Test that the system works with legacy DomainCheckResult without price_comparison."""
        # Create a legacy-style domain result
        domain_result = DomainCheckResult(
            "example.com",
            True,
            15.99,
            "name.com",
            None,
            # No price_comparison field
        )

        scored_candidate = ScoredCandidate("Example", 85.5, {"length": 75.0}, [domain_result])

        # Should not crash when generating reports
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            try:
                write_reports([scored_candidate], Path(f.name))

                with open(f.name, "r") as rf:
                    data = json.load(rf)

                domain = data["results"][0]["domains"][0]
                assert domain["domain"] == "example.com"
                assert domain["price_usd"] == 15.99
                # price_comparison should not be present or should be None
                assert domain.get("price_comparison") is None

            finally:
                os.unlink(f.name)
