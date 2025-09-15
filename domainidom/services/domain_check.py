from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Import httpx only when available
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from ..storage.cache import DomainCache
from ..models import DomainCheckResult, PriceComparison
from .pricing import get_multi_registrar_pricing

RATE_LIMIT_RPS = float(os.getenv("DOMAIN_CHECK_RPS", "3"))
BURST = int(os.getenv("DOMAIN_CHECK_BURST", "5"))
RETRY_BACKOFF = [0.5, 1.0, 2.0]
CACHE_PATH = os.getenv("DOMAIN_CACHE_PATH", "domain_cache.sqlite3")

DOMAINR_BASE = "https://api.domainr.com/v2/status"

# MCP FastDomainCheck configuration
MCP_BATCH_SIZE = int(os.getenv("MCP_BATCH_SIZE", "20"))


# Enable multi-registrar pricing comparison (read dynamically for tests)
def is_multi_registrar_enabled() -> bool:
    return os.getenv("ENABLE_MULTI_REGISTRAR", "1") == "1"


# Enable MCP FastDomainCheck integration
def is_mcp_fastdomaincheck_enabled() -> bool:
    return os.getenv("MCP_FASTDOMAINCHECK_ENABLED", "0") == "1"


@dataclass
class ProviderResponse:
    available: bool | None
    price_usd: float | None
    provider: str
    error: str | None = None
    price_comparison: PriceComparison | None = None


class TokenBucket:
    def __init__(self, rps: float, burst: int):
        self.rps = rps
        self.capacity = burst
        self.tokens = burst
        self.timestamp = time.monotonic()

    async def acquire(self) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self.timestamp
            self.timestamp = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rps)
            if self.tokens >= 1:
                self.tokens -= 1
                return
            await asyncio.sleep(max(0.05, (1 - self.tokens) / self.rps))


bucket = TokenBucket(RATE_LIMIT_RPS, BURST)


@dataclass
class MCPBatchRequest:
    """MCP FastDomainCheck batch request format."""
    domains: List[str]
    include_pricing: bool = False


@dataclass 
class MCPDomainResult:
    """MCP FastDomainCheck domain result format."""
    domain: str
    available: bool | None
    price_usd: float | None = None
    error: str | None = None


@dataclass
class MCPBatchResponse:
    """MCP FastDomainCheck batch response format."""
    results: List[MCPDomainResult]
    provider: str = "mcp-fastdomaincheck"


class MCPFastDomainCheckClient:
    """Mock MCP FastDomainCheck client for bulk domain availability."""
    
    def __init__(self):
        self.endpoint = os.getenv("MCP_FASTDOMAINCHECK_ENDPOINT", "http://localhost:8080/v1/domains/check")
        self.api_key = os.getenv("MCP_FASTDOMAINCHECK_API_KEY")
        self.timeout = float(os.getenv("MCP_FASTDOMAINCHECK_TIMEOUT", "30"))
        
    async def check_domains_batch(self, domains: List[str]) -> MCPBatchResponse:
        """Check domain availability in batch via MCP FastDomainCheck."""
        if not HTTPX_AVAILABLE:
            # Return stub response when httpx not available
            return MCPBatchResponse([
                MCPDomainResult(domain, None, None, "httpx_not_available") for domain in domains
            ])
            
        if not self.api_key:
            # Return stub response when API key not configured
            return MCPBatchResponse([
                MCPDomainResult(domain, None, None, "missing_api_key") for domain in domains
            ])
            
        # Split into batches of configured size
        batch_size = min(MCP_BATCH_SIZE, len(domains))
        if len(domains) > batch_size:
            domains = domains[:batch_size]
            
        request_data = MCPBatchRequest(domains=domains, include_pricing=True)
        
        for backoff in [0] + RETRY_BACKOFF:
            try:
                if backoff:
                    await asyncio.sleep(backoff)
                    
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    await bucket.acquire()
                    response = await client.post(
                        self.endpoint,
                        json={
                            "domains": request_data.domains,
                            "include_pricing": request_data.include_pricing
                        },
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Parse MCP response format
                    results = []
                    for item in data.get("results", []):
                        results.append(MCPDomainResult(
                            domain=item.get("domain", ""),
                            available=item.get("available"),
                            price_usd=item.get("price_usd"),
                            error=item.get("error")
                        ))
                    
                    return MCPBatchResponse(results=results)
                    
            except Exception as e:
                if backoff == RETRY_BACKOFF[-1]:  # Last retry
                    # Return error responses for all domains on final failure
                    return MCPBatchResponse([
                        MCPDomainResult(domain, None, None, f"mcp_error: {str(e)}")
                        for domain in domains
                    ])
                continue
                
        # Fallback response
        return MCPBatchResponse([
            MCPDomainResult(domain, None, None, "mcp_timeout") for domain in domains
        ])


async def _fetch_mcp_fastdomaincheck(domains: List[str]) -> List[ProviderResponse]:
    """Fetch domain availability via MCP FastDomainCheck in batch."""
    if not is_mcp_fastdomaincheck_enabled():
        return [ProviderResponse(None, None, "stub", "mcp_disabled") for _ in domains]
        
    try:
        client = MCPFastDomainCheckClient()
        batch_response = await client.check_domains_batch(domains)
        
        responses = []
        for result in batch_response.results:
            responses.append(ProviderResponse(
                available=result.available,
                price_usd=result.price_usd,
                provider="mcp-fastdomaincheck",
                error=result.error
            ))
            
        # Ensure we return the same number of responses as domains requested
        while len(responses) < len(domains):
            responses.append(ProviderResponse(None, None, "mcp-fastdomaincheck", "missing_result"))
            
        return responses[:len(domains)]
        
    except Exception as e:
        return [ProviderResponse(None, None, "mcp-fastdomaincheck", f"batch_error: {str(e)}") for _ in domains]


async def _fetch_namecom(domain: str) -> ProviderResponse:
    if not HTTPX_AVAILABLE:
        return ProviderResponse(None, None, "stub", "httpx_not_available")
        
    NAMECOM_API_USERNAME = os.getenv("NAME_COM_USERNAME") or os.getenv("name_com_DEV_USERNAME")
    NAMECOM_API_TOKEN = os.getenv("NAME_COM_API_KEY") or os.getenv("name_com_DEV_API_KEY")
    NAMECOM_BASE = os.getenv("NAME_COM_BASE", "https://api.dev.name.com/v4")
    if not (NAMECOM_API_USERNAME and NAMECOM_API_TOKEN):
        return ProviderResponse(None, None, "stub", "missing_namecom_keys")
    url = f"{NAMECOM_BASE}/domains:checkAvailability"
    payload = {"domainNames": [domain]}
    for backoff in [0] + RETRY_BACKOFF:
        try:
            if backoff:
                await asyncio.sleep(backoff)
            async with httpx.AsyncClient(timeout=10) as client:
                await bucket.acquire()
                resp = await client.post(
                    url, json=payload, auth=(NAMECOM_API_USERNAME, NAMECOM_API_TOKEN)
                )
                resp.raise_for_status()
                data = resp.json()
                # Name.com returns array of check results; use first
                item = data.get("results", [{}])[0]
                available = bool(item.get("purchasable", False))
                price = None
                if "purchasePrice" in item and isinstance(item["purchasePrice"], dict):
                    price = float(item["purchasePrice"].get("amount", 0))
                return ProviderResponse(available, price, "name.com")
        except Exception:
            continue
    return ProviderResponse(None, None, "name.com", "request_failed")


async def _fetch_domainr(domain: str) -> ProviderResponse:
    if not HTTPX_AVAILABLE:
        return ProviderResponse(None, None, "stub", "httpx_not_available")
        
    DOMAINR_API_KEY = os.getenv("DOMAINR_API_KEY")
    if not DOMAINR_API_KEY:
        return ProviderResponse(None, None, "stub", "missing_domainr_key")
    params = {"domain": domain, "key": DOMAINR_API_KEY}
    for backoff in [0] + RETRY_BACKOFF:
        try:
            if backoff:
                await asyncio.sleep(backoff)
            async with httpx.AsyncClient(timeout=10) as client:
                await bucket.acquire()
                resp = await client.get(DOMAINR_BASE, params=params)
                resp.raise_for_status()
                statuses = resp.json().get("status", [])
                available = None
                if statuses:
                    s = statuses[0].get("status", "")
                    available = "inactive" in s or "undelegated" in s or "available" in s
                return ProviderResponse(available, None, "domainr")
        except Exception:
            continue
    return ProviderResponse(None, None, "domainr", "request_failed")


async def _fetch_whoisxml(domain: str) -> ProviderResponse:
    # WhoisXML offers complex suite; we will not call availability here to avoid quota burn by default.
    # Return stub unless explicitly enabled via env var.
    WHOISXML_API_KEY = os.getenv("WHOISXML_API_KEY")
    if not WHOISXML_API_KEY or os.getenv("USE_WHOISXML_FOR_AVAIL", "0") != "1":
        return ProviderResponse(None, None, "stub", "whoisxml_disabled")
    return ProviderResponse(None, None, "whoisxml", "not_implemented")


async def _fetch_best(domain: str) -> ProviderResponse:
    """Fetch domain info with optional multi-registrar pricing comparison."""
    # If multi-registrar pricing is enabled, get comprehensive pricing data
    if is_multi_registrar_enabled():
        try:
            price_comparison = await get_multi_registrar_pricing(domain)

            # Determine availability from any registrar that provided data
            available = None
            best_price = None
            primary_provider = "multi-registrar"

            for price in price_comparison.prices:
                if price.is_available is not None:
                    available = price.is_available
                    primary_provider = price.registrar
                    break

            if price_comparison.best_price:
                best_price = price_comparison.best_price.price_usd

            return ProviderResponse(
                available=available,
                price_usd=best_price,
                provider=primary_provider,
                price_comparison=price_comparison,
            )
        except Exception:
            # Fall back to legacy behavior on error
            pass

    # Prioritize MCP FastDomainCheck (if enabled), then Name.com (dev), then Domainr; others stubbed
    if is_mcp_fastdomaincheck_enabled():
        # For single domain, use batch endpoint with single domain
        mcp_responses = await _fetch_mcp_fastdomaincheck([domain])
        if mcp_responses and mcp_responses[0].available is not None:
            return mcp_responses[0]
    
    res = await _fetch_namecom(domain)
    if res.available is not None:
        return res
    res = await _fetch_domainr(domain)
    if res.available is not None:
        return res
    return ProviderResponse(None, None, "stub", "no_provider")


def check_domains(
    domain_candidates: Dict[str, List[str]],
) -> Dict[str, List[Tuple[str, DomainCheckResult]]]:
    cache_path = os.getenv("DOMAIN_CACHE_PATH", "domain_cache.sqlite3")
    cache = DomainCache(cache_path)
    max_calls_total = int(os.getenv("DOMAIN_CHECK_MAX_CALLS", "80"))
    calls_made = 0

    async def _run() -> Dict[str, List[Tuple[str, DomainCheckResult]]]:
        nonlocal calls_made
        results: Dict[str, List[Tuple[str, DomainCheckResult]]] = {}
        
        # Track domains that need checking (not in cache)
        domains_to_check: List[Tuple[str, str]] = []  # (name, domain) pairs
        
        # First pass: handle cached domains and collect uncached ones
        for name, domains in domain_candidates.items():
            results[name] = []
            for d in domains:
                cached = cache.get(d)
                if cached is not None:
                    available, price, provider, error = cached
                    results[name].append(
                        (d, DomainCheckResult(d, available, price, provider, error))
                    )
                    continue
                if calls_made >= max_calls_total:
                    results[name].append(
                        (d, DomainCheckResult(d, None, None, "quota", "max_calls_reached"))
                    )
                    continue
                domains_to_check.append((name, d))
                calls_made += 1

        # If MCP is enabled and we have domains to check, use batch processing
        if is_mcp_fastdomaincheck_enabled() and domains_to_check:
            # Extract just the domain names for batch processing
            batch_domains = [domain for _, domain in domains_to_check]
            
            try:
                # Process in batches
                batch_size = MCP_BATCH_SIZE
                for i in range(0, len(batch_domains), batch_size):
                    batch = batch_domains[i:i + batch_size]
                    batch_responses = await _fetch_mcp_fastdomaincheck(batch)
                    
                    # Map responses back to results
                    for j, resp in enumerate(batch_responses):
                        if i + j < len(domains_to_check):
                            name, domain = domains_to_check[i + j]
                            dcr = DomainCheckResult(
                                domain=domain,
                                available=resp.available,
                                registrar_price_usd=resp.price_usd,
                                provider=resp.provider,
                                error=resp.error,
                                price_comparison=resp.price_comparison,
                            )
                            results.setdefault(name, []).append((domain, dcr))
                            cache.set(domain, (dcr.available, dcr.registrar_price_usd, dcr.provider, dcr.error))
                            
            except Exception as e:
                # Fallback to individual processing if batch fails
                for name, domain in domains_to_check:
                    resp = ProviderResponse(None, None, "mcp-fastdomaincheck", f"batch_fallback_error: {str(e)}")
                    dcr = DomainCheckResult(
                        domain=domain,
                        available=resp.available,
                        registrar_price_usd=resp.price_usd,
                        provider=resp.provider,
                        error=resp.error,
                        price_comparison=resp.price_comparison,
                    )
                    results.setdefault(name, []).append((domain, dcr))
                    cache.set(domain, (dcr.available, dcr.registrar_price_usd, dcr.provider, dcr.error))
        else:
            # Traditional individual processing
            tasks: List[Tuple[str, str, asyncio.Task[ProviderResponse]]] = []
            for name, domain in domains_to_check:
                tasks.append((name, domain, asyncio.create_task(_fetch_best(domain))))
                
            for name, domain, task in tasks:
                try:
                    resp = await task
                except Exception as e:
                    resp = ProviderResponse(None, None, "error", str(e))
                dcr = DomainCheckResult(
                    domain=domain,
                    available=resp.available,
                    registrar_price_usd=resp.price_usd,
                    provider=resp.provider,
                    error=resp.error,
                    price_comparison=resp.price_comparison,
                )
                results.setdefault(name, []).append((domain, dcr))
                cache.set(domain, (dcr.available, dcr.registrar_price_usd, dcr.provider, dcr.error))
                
        return results

    return asyncio.run(_run())
