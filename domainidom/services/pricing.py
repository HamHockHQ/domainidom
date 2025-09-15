from __future__ import annotations

import asyncio
import os
from typing import Optional
import time

# Import httpx only when available
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from ..models import RegistrarPrice, PriceComparison

# Configuration - Base URLs (static)
NAMECOM_BASE = os.getenv("NAME_COM_BASE", "https://api.dev.name.com/v4")
GODADDY_BASE = "https://api.godaddy.com/v1"
CLOUDFLARE_BASE = "https://api.cloudflare.com/client/v4"
NAMECHEAP_BASE = "https://api.namecheap.com/xml.response"


# Credential getters - read dynamically for test compatibility
def _get_namecom_credentials():
    """Get Name.com credentials dynamically."""
    username = os.getenv("NAME_COM_USERNAME") or os.getenv("name_com_DEV_USERNAME")
    token = os.getenv("NAME_COM_API_KEY") or os.getenv("name_com_DEV_API_KEY")
    return username, token


def _get_godaddy_credentials():
    """Get GoDaddy credentials dynamically."""
    return os.getenv("GODADDY_API_KEY"), os.getenv("GODADDY_API_SECRET")


def _get_cloudflare_credentials():
    """Get Cloudflare credentials dynamically."""
    return os.getenv("CLOUDFLARE_API_TOKEN")


def _get_namecheap_credentials():
    """Get Namecheap credentials dynamically."""
    return os.getenv("NAMECHEAP_API_USER"), os.getenv("NAMECHEAP_API_KEY")


# Rate limiting per registrar
REGISTRAR_RATE_LIMITS = {
    "namecom": float(os.getenv("NAMECOM_RPS", "2")),
    "godaddy": float(os.getenv("GODADDY_RPS", "1")),
    "cloudflare": float(os.getenv("CLOUDFLARE_RPS", "5")),
    "namecheap": float(os.getenv("NAMECHEAP_RPS", "1")),
}


# Enabled registrars (can be disabled via environment)
def _is_registrar_enabled(name: str) -> bool:
    """Check if a registrar is enabled via environment variable."""
    return os.getenv(f"ENABLE_{name.upper()}", "1") == "1"


class RateLimiter:
    """Simple rate limiter for each registrar."""

    def __init__(self, rps: float):
        self.rps = rps
        self.last_call = 0

    async def acquire(self):
        if self.rps <= 0:
            return
        now = time.time()
        elapsed = now - self.last_call
        min_interval = 1.0 / self.rps
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self.last_call = time.time()


# Rate limiters for each registrar
rate_limiters = {name: RateLimiter(rps) for name, rps in REGISTRAR_RATE_LIMITS.items()}


async def get_namecom_price(domain: str) -> RegistrarPrice:
    """Get pricing from Name.com API."""
    username, token = _get_namecom_credentials()
    if not _is_registrar_enabled("namecom") or not (username and token):
        return RegistrarPrice("namecom", None, error="missing_credentials_or_disabled")

    await rate_limiters["namecom"].acquire()
    url = f"{NAMECOM_BASE}/domains:checkAvailability"
    payload = {"domainNames": [domain]}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, auth=(username, token))
            resp.raise_for_status()
            data = resp.json()
            item = data.get("results", [{}])[0]

            available = bool(item.get("purchasable", False))
            price = None
            renewal_price = None

            if "purchasePrice" in item and isinstance(item["purchasePrice"], dict):
                amount = item["purchasePrice"].get("amount")
                try:
                    price = float(amount) if amount is not None else None
                except Exception:
                    price = None

            if "renewalPrice" in item and isinstance(item["renewalPrice"], dict):
                amount = item["renewalPrice"].get("amount")
                try:
                    renewal_price = float(amount) if amount is not None else None
                except Exception:
                    renewal_price = None

            return RegistrarPrice(
                registrar="namecom",
                price_usd=price,
                is_available=available,
                renewal_price_usd=renewal_price,
                registration_url=(
                    f"https://www.name.com/domain/search/{domain}" if available else None
                ),
            )
    except Exception as e:
        return RegistrarPrice("namecom", None, error=str(e))


async def get_godaddy_price(domain: str) -> RegistrarPrice:
    """Get pricing from GoDaddy API."""
    api_key, api_secret = _get_godaddy_credentials()
    if not _is_registrar_enabled("godaddy") or not (api_key and api_secret):
        return RegistrarPrice("godaddy", None, error="missing_credentials_or_disabled")

    await rate_limiters["godaddy"].acquire()
    url = f"{GODADDY_BASE}/domains/available"
    headers = {
        "Authorization": f"sso-key {api_key}:{api_secret}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{url}?domain={domain}", headers=headers)
            resp.raise_for_status()
            data = resp.json()

            available = data.get("available", False)
            price = data.get("price")  # GoDaddy returns price in micros sometimes

            # Convert price if needed
            if price and isinstance(price, dict):
                price = float(price.get("amount", 0)) / 1_000_000  # Convert from micros
            elif price:
                # GoDaddy price is typically in micros (even when it's a plain number)
                price = float(price) / 1_000_000

            return RegistrarPrice(
                registrar="godaddy",
                price_usd=price,
                is_available=available,
                registration_url=(
                    f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"
                    if available
                    else None
                ),
            )
    except Exception as e:
        return RegistrarPrice("godaddy", None, error=str(e))


async def get_cloudflare_price(domain: str) -> RegistrarPrice:
    """Get pricing from Cloudflare Registrar API."""
    api_token = _get_cloudflare_credentials()
    if not _is_registrar_enabled("cloudflare") or not api_token:
        return RegistrarPrice("cloudflare", None, error="missing_credentials_or_disabled")

    await rate_limiters["cloudflare"].acquire()

    try:
        # Note: Cloudflare's registrar API is limited and may not provide direct availability checking
        # This is a simplified implementation - in practice, you'd need to check their actual API docs
        # Cloudflare typically charges at-cost pricing, but availability checking is limited
        # For now, return a stub implementation
        return RegistrarPrice(
            registrar="cloudflare",
            price_usd=None,
            error="api_not_publicly_available",
            registration_url="https://dash.cloudflare.com/registrar",
        )
    except Exception as e:
        return RegistrarPrice("cloudflare", None, error=str(e))


async def get_namecheap_price(domain: str) -> RegistrarPrice:
    """Get pricing from Namecheap API."""
    api_user, api_key = _get_namecheap_credentials()
    if not _is_registrar_enabled("namecheap") or not (api_user and api_key):
        return RegistrarPrice("namecheap", None, error="missing_credentials_or_disabled")

    await rate_limiters["namecheap"].acquire()

    try:
        # Namecheap uses XML API - this is a simplified implementation
        params = {
            "ApiUser": api_user,
            "ApiKey": api_key,
            "UserName": api_user,
            "Command": "namecheap.domains.check",
            "ClientIp": "127.0.0.1",  # You'd need to get actual client IP
            "DomainList": domain,
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NAMECHEAP_BASE, params=params)
            resp.raise_for_status()

            # Parse XML response (simplified - you'd want proper XML parsing)
            text = resp.text
            available = 'Available="true"' in text

            # Namecheap doesn't typically return pricing in availability check
            # You'd need separate pricing API calls
            return RegistrarPrice(
                registrar="namecheap",
                price_usd=None,  # Would need separate pricing call
                is_available=available,
                registration_url=(
                    f"https://www.namecheap.com/domains/registration/results/?domain={domain}"
                    if available
                    else None
                ),
                error="pricing_requires_separate_api_call",
            )
    except Exception as e:
        return RegistrarPrice("namecheap", None, error=str(e))


async def get_multi_registrar_pricing(domain: str) -> PriceComparison:
    """Get pricing from all enabled registrars in parallel."""
    if not HTTPX_AVAILABLE:
        # Return stub pricing when httpx not available
        return PriceComparison(domain, [RegistrarPrice("stub", None, error="httpx_not_available")])

    tasks = []

    if _is_registrar_enabled("namecom"):
        tasks.append(("namecom", get_namecom_price(domain)))
    if _is_registrar_enabled("godaddy"):
        tasks.append(("godaddy", get_godaddy_price(domain)))
    if _is_registrar_enabled("cloudflare"):
        tasks.append(("cloudflare", get_cloudflare_price(domain)))
    if _is_registrar_enabled("namecheap"):
        tasks.append(("namecheap", get_namecheap_price(domain)))

    if not tasks:
        return PriceComparison(domain, [])

    # Execute all pricing requests in parallel
    results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

    prices = []
    for (registrar, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            prices.append(RegistrarPrice(registrar, None, error=str(result)))
        else:
            prices.append(result)

    return PriceComparison(domain, prices)


# Legacy function for backward compatibility
async def get_namecom_price_legacy(domain: str) -> Optional[float]:
    """Legacy function for backward compatibility."""
    result = await get_namecom_price(domain)
    return result.price_usd
