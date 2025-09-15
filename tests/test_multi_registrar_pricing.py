"""Tests for multi-registrar pricing system."""

import pytest
import time
from unittest.mock import AsyncMock, patch, Mock
from domainidom.models import RegistrarPrice, PriceComparison
from domainidom.services.pricing import (
    get_namecom_price,
    get_godaddy_price,
    get_cloudflare_price,
    get_namecheap_price,
    get_multi_registrar_pricing,
)


class TestRegistrarPrice:
    def test_registrar_price_basic(self):
        price = RegistrarPrice("namecom", 12.99, "USD", True)
        assert price.registrar == "namecom"
        assert price.price_usd == 12.99
        assert price.currency == "USD"
        assert price.is_available is True

    def test_registrar_price_with_error(self):
        price = RegistrarPrice("godaddy", None, error="api_error")
        assert price.registrar == "godaddy"
        assert price.price_usd is None
        assert price.error == "api_error"


class TestPriceComparison:
    def test_price_comparison_auto_best_price(self):
        prices = [
            RegistrarPrice("namecom", 15.99, "USD", True),
            RegistrarPrice("godaddy", 12.99, "USD", True),
            RegistrarPrice("cloudflare", None, error="not_available"),
        ]
        comparison = PriceComparison("example.com", prices)

        assert comparison.domain == "example.com"
        assert len(comparison.prices) == 3
        assert comparison.best_price.registrar == "godaddy"
        assert comparison.best_price.price_usd == 12.99

    def test_price_comparison_no_available_prices(self):
        prices = [
            RegistrarPrice("namecom", None, error="not_available"),
            RegistrarPrice("godaddy", 12.99, "USD", False),  # not available for registration
        ]
        comparison = PriceComparison("example.com", prices)

        assert comparison.best_price is None

    def test_price_comparison_manual_best_price(self):
        prices = [
            RegistrarPrice("namecom", 15.99, "USD", True),
            RegistrarPrice("godaddy", 12.99, "USD", True),
        ]
        manual_best = RegistrarPrice("custom", 10.99, "USD", True)
        comparison = PriceComparison("example.com", prices, manual_best)

        assert comparison.best_price.registrar == "custom"
        assert comparison.best_price.price_usd == 10.99


class TestNamecomPricing:
    @pytest.mark.asyncio
    async def test_namecom_price_success(self, monkeypatch):
        # Clear existing env vars and set test values
        monkeypatch.delenv("NAME_COM_USERNAME", raising=False)
        monkeypatch.delenv("NAME_COM_API_KEY", raising=False)
        monkeypatch.setenv("NAME_COM_USERNAME", "test_user")
        monkeypatch.setenv("NAME_COM_API_KEY", "test_key")
        monkeypatch.setenv("ENABLE_NAMECOM", "1")

        # Mock HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "purchasable": True,
                    "purchasePrice": {"amount": "12.99"},
                    "renewalPrice": {"amount": "15.99"},
                }
            ]
        }
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Patch the rate limiter to avoid delays
            with patch("domainidom.services.pricing.rate_limiters") as mock_limiters:
                mock_limiter = AsyncMock()
                mock_limiters.__getitem__.return_value = mock_limiter

                result = await get_namecom_price("example.com")

                assert result.registrar == "namecom"
                assert result.price_usd == 12.99
                assert result.renewal_price_usd == 15.99
                assert result.is_available is True
                assert "name.com" in result.registration_url

    @pytest.mark.asyncio
    async def test_namecom_price_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("NAME_COM_USERNAME", raising=False)
        monkeypatch.delenv("NAME_COM_API_KEY", raising=False)

        result = await get_namecom_price("example.com")

        assert result.registrar == "namecom"
        assert result.price_usd is None
        assert result.error == "missing_credentials_or_disabled"

    @pytest.mark.asyncio
    async def test_namecom_price_disabled(self, monkeypatch):
        monkeypatch.setenv("NAME_COM_USERNAME", "test_user")
        monkeypatch.setenv("NAME_COM_API_KEY", "test_key")
        monkeypatch.setenv("ENABLE_NAMECOM", "0")

        result = await get_namecom_price("example.com")

        assert result.registrar == "namecom"
        assert result.price_usd is None
        assert result.error == "missing_credentials_or_disabled"


class TestGodaddyPricing:
    @pytest.mark.asyncio
    async def test_godaddy_price_success(self, monkeypatch):
        # Clear and set environment variables
        monkeypatch.delenv("GODADDY_API_KEY", raising=False)
        monkeypatch.delenv("GODADDY_API_SECRET", raising=False)
        monkeypatch.setenv("GODADDY_API_KEY", "test_key")
        monkeypatch.setenv("GODADDY_API_SECRET", "test_secret")
        monkeypatch.setenv("ENABLE_GODADDY", "1")

        mock_response = Mock()
        mock_response.json.return_value = {"available": True, "price": 1299000}  # Price in micros
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with patch("domainidom.services.pricing.rate_limiters") as mock_limiters:
                mock_limiter = AsyncMock()
                mock_limiters.__getitem__.return_value = mock_limiter

                result = await get_godaddy_price("example.com")

                assert result.registrar == "godaddy"
                assert result.price_usd == 1.299  # Converted from micros
                assert result.is_available is True

    @pytest.mark.asyncio
    async def test_godaddy_price_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("GODADDY_API_KEY", raising=False)
        monkeypatch.delenv("GODADDY_API_SECRET", raising=False)

        result = await get_godaddy_price("example.com")

        assert result.registrar == "godaddy"
        assert result.price_usd is None
        assert result.error == "missing_credentials_or_disabled"


class TestCloudflareAndNamecheap:
    @pytest.mark.asyncio
    async def test_cloudflare_price_stub(self, monkeypatch):
        # Enable cloudflare but don't provide token
        monkeypatch.setenv("ENABLE_CLOUDFLARE", "1")
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

        result = await get_cloudflare_price("example.com")

        assert result.registrar == "cloudflare"
        assert result.price_usd is None
        assert "missing_credentials_or_disabled" in result.error

    @pytest.mark.asyncio
    async def test_namecheap_price_success(self, monkeypatch):
        # Clear and set environment variables
        monkeypatch.delenv("NAMECHEAP_API_USER", raising=False)
        monkeypatch.delenv("NAMECHEAP_API_KEY", raising=False)
        monkeypatch.setenv("NAMECHEAP_API_USER", "test_user")
        monkeypatch.setenv("NAMECHEAP_API_KEY", "test_key")
        monkeypatch.setenv("ENABLE_NAMECHEAP", "1")

        mock_response = Mock()
        mock_response.text = '<xml><result Available="true" Domain="example.com"/></xml>'
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with patch("domainidom.services.pricing.rate_limiters") as mock_limiters:
                mock_limiter = AsyncMock()
                mock_limiters.__getitem__.return_value = mock_limiter

                result = await get_namecheap_price("example.com")

                assert result.registrar == "namecheap"
                assert result.is_available is True
                assert "pricing_requires_separate_api_call" in result.error


class TestMultiRegistrarPricing:
    @pytest.mark.asyncio
    async def test_multi_registrar_pricing_all_enabled(self, monkeypatch):
        # Enable all registrars
        monkeypatch.setenv("ENABLE_NAMECOM", "1")
        monkeypatch.setenv("ENABLE_GODADDY", "1")
        monkeypatch.setenv("ENABLE_CLOUDFLARE", "1")
        monkeypatch.setenv("ENABLE_NAMECHEAP", "1")

        # Mock individual pricing functions
        with (
            patch("domainidom.services.pricing.get_namecom_price") as mock_namecom,
            patch("domainidom.services.pricing.get_godaddy_price") as mock_godaddy,
            patch("domainidom.services.pricing.get_cloudflare_price") as mock_cloudflare,
            patch("domainidom.services.pricing.get_namecheap_price") as mock_namecheap,
        ):

            mock_namecom.return_value = RegistrarPrice("namecom", 15.99, "USD", True)
            mock_godaddy.return_value = RegistrarPrice("godaddy", 12.99, "USD", True)
            mock_cloudflare.return_value = RegistrarPrice("cloudflare", None, error="not_available")
            mock_namecheap.return_value = RegistrarPrice(
                "namecheap", None, error="pricing_unavailable"
            )

            result = await get_multi_registrar_pricing("example.com")

            assert result.domain == "example.com"
            assert len(result.prices) == 4
            assert result.best_price.registrar == "godaddy"
            assert result.best_price.price_usd == 12.99

            # Verify all functions were called
            mock_namecom.assert_called_once_with("example.com")
            mock_godaddy.assert_called_once_with("example.com")
            mock_cloudflare.assert_called_once_with("example.com")
            mock_namecheap.assert_called_once_with("example.com")

    @pytest.mark.asyncio
    async def test_multi_registrar_pricing_disabled(self, monkeypatch):
        # Disable all registrars
        monkeypatch.setenv("ENABLE_NAMECOM", "0")
        monkeypatch.setenv("ENABLE_GODADDY", "0")
        monkeypatch.setenv("ENABLE_CLOUDFLARE", "0")
        monkeypatch.setenv("ENABLE_NAMECHEAP", "0")

        result = await get_multi_registrar_pricing("example.com")

        assert result.domain == "example.com"
        assert len(result.prices) == 0
        assert result.best_price is None

    @pytest.mark.asyncio
    async def test_multi_registrar_pricing_partial_enabled(self, monkeypatch):
        # Enable only namecom and godaddy
        monkeypatch.setenv("ENABLE_NAMECOM", "1")
        monkeypatch.setenv("ENABLE_GODADDY", "1")
        monkeypatch.setenv("ENABLE_CLOUDFLARE", "0")
        monkeypatch.setenv("ENABLE_NAMECHEAP", "0")

        with (
            patch("domainidom.services.pricing.get_namecom_price") as mock_namecom,
            patch("domainidom.services.pricing.get_godaddy_price") as mock_godaddy,
        ):

            mock_namecom.return_value = RegistrarPrice("namecom", 15.99, "USD", True)
            mock_godaddy.return_value = RegistrarPrice("godaddy", 12.99, "USD", True)

            result = await get_multi_registrar_pricing("example.com")

            assert result.domain == "example.com"
            assert len(result.prices) == 2
            assert result.best_price.registrar == "godaddy"

            mock_namecom.assert_called_once()
            mock_godaddy.assert_called_once()


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limiter(self):
        from domainidom.services.pricing import RateLimiter
        import time

        # Test rate limiter with 2 RPS
        limiter = RateLimiter(2.0)

        start_time = time.time()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()  # This should trigger a delay
        end_time = time.time()

        # Should take at least 0.5 seconds (1/2 RPS) for the third call
        assert (end_time - start_time) >= 0.4  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_zero_rps(self):
        from domainidom.services.pricing import RateLimiter

        # Rate limiter with 0 RPS should not block
        limiter = RateLimiter(0)

        start_time = time.time()
        await limiter.acquire()
        await limiter.acquire()
        end_time = time.time()

        # Should be nearly instantaneous
        assert (end_time - start_time) < 0.1
