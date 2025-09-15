"""Integration tests for multi-registrar pricing with domain checking."""

import pytest
import tempfile
from unittest.mock import patch, Mock
from domainidom.models import PriceComparison, RegistrarPrice
from domainidom.services.domain_check import check_domains


class TestMultiRegistrarIntegration:
    def test_domain_check_with_multi_registrar_enabled(self, monkeypatch):
        """Test that domain checking integrates with multi-registrar pricing."""
        # Set up temporary cache
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            monkeypatch.setenv("DOMAIN_CACHE_PATH", tmp.name)
            monkeypatch.setenv("ENABLE_MULTI_REGISTRAR", "1")
            
            # Mock the pricing function
            mock_price_comparison = PriceComparison(
                "example.com",
                [
                    RegistrarPrice("namecom", 15.99, "USD", True),
                    RegistrarPrice("godaddy", 12.99, "USD", True),
                ]
            )
            
            with patch("domainidom.services.domain_check.get_multi_registrar_pricing") as mock_pricing:
                mock_pricing.return_value = mock_price_comparison
                
                # Run domain check
                results = check_domains({"test": ["example.com"]})
                
                # Verify results include multi-registrar data
                assert "test" in results
                assert len(results["test"]) == 1
                
                domain, dcr = results["test"][0]
                assert domain == "example.com"
                assert dcr.available is True  # From first available registrar
                assert dcr.registrar_price_usd == 12.99  # Best price
                assert dcr.provider == "namecom"  # First provider with availability
                assert dcr.price_comparison is not None
                assert dcr.price_comparison.best_price.registrar == "godaddy"

    def test_domain_check_with_multi_registrar_disabled(self, monkeypatch):
        """Test that domain checking falls back to legacy behavior when multi-registrar is disabled."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            monkeypatch.setenv("DOMAIN_CACHE_PATH", tmp.name)
            monkeypatch.setenv("ENABLE_MULTI_REGISTRAR", "0")
            
            # Mock Name.com response
            mock_response = Mock()
            mock_response.json.return_value = {
                "results": [{
                    "purchasable": True,
                    "purchasePrice": {"amount": "15.99"}
                }]
            }
            mock_response.raise_for_status.return_value = None
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                # Set up Name.com credentials
                monkeypatch.setenv("NAME_COM_USERNAME", "test")
                monkeypatch.setenv("NAME_COM_API_KEY", "test")
                
                results = check_domains({"test": ["example.com"]})
                
                # Verify legacy behavior
                assert "test" in results
                domain, dcr = results["test"][0]
                assert dcr.available is True
                assert dcr.registrar_price_usd == 15.99
                assert dcr.provider == "name.com"
                assert dcr.price_comparison is None  # No multi-registrar data

    def test_domain_check_with_pricing_error(self, monkeypatch):
        """Test graceful degradation when multi-registrar pricing fails."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            monkeypatch.setenv("DOMAIN_CACHE_PATH", tmp.name)
            monkeypatch.setenv("ENABLE_MULTI_REGISTRAR", "1")
            
            # Mock pricing function to raise an exception
            with patch("domainidom.services.domain_check.get_multi_registrar_pricing") as mock_pricing:
                mock_pricing.side_effect = Exception("API Error")
                
                # Mock fallback Name.com response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "results": [{
                        "purchasable": True,
                        "purchasePrice": {"amount": "15.99"}
                    }]
                }
                mock_response.raise_for_status.return_value = None
                
                with patch("httpx.AsyncClient") as mock_client:
                    mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                    
                    monkeypatch.setenv("NAME_COM_USERNAME", "test")
                    monkeypatch.setenv("NAME_COM_API_KEY", "test")
                    
                    results = check_domains({"test": ["example.com"]})
                    
                    # Should fall back to legacy behavior
                    assert "test" in results
                    domain, dcr = results["test"][0]
                    assert dcr.available is True
                    assert dcr.provider == "name.com"
                    assert dcr.price_comparison is None

    def test_domain_check_caching_compatibility(self, monkeypatch):
        """Test that caching still works with new price comparison fields."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            monkeypatch.setenv("DOMAIN_CACHE_PATH", tmp.name)
            
            # First call should hit the API and cache the result
            mock_response = Mock()
            mock_response.json.return_value = {
                "results": [{
                    "purchasable": True,
                    "purchasePrice": {"amount": "15.99"}
                }]
            }
            mock_response.raise_for_status.return_value = None
            
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
                
                monkeypatch.setenv("NAME_COM_USERNAME", "test")
                monkeypatch.setenv("NAME_COM_API_KEY", "test")
                
                # First call
                results1 = check_domains({"test": ["example.com"]})
                
                # Second call should use cache (mock should not be called again)
                mock_client.reset_mock()
                results2 = check_domains({"test": ["example.com"]})
                
                # Verify both calls return the same data
                assert results1["test"][0][1].available == results2["test"][0][1].available
                assert results1["test"][0][1].registrar_price_usd == results2["test"][0][1].registrar_price_usd
                
                # Verify second call didn't make HTTP requests
                mock_client.assert_not_called()