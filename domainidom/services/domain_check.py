from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

import httpx

from ..storage.cache import DomainCache
from ..models import DomainCheckResult

RATE_LIMIT_RPS = float(os.getenv("DOMAIN_CHECK_RPS", "3"))
BURST = int(os.getenv("DOMAIN_CHECK_BURST", "5"))
RETRY_BACKOFF = [0.5, 1.0, 2.0]
CACHE_PATH = os.getenv("DOMAIN_CACHE_PATH", "domain_cache.sqlite3")

DOMAINR_BASE = "https://api.domainr.com/v2/status"


@dataclass
class ProviderResponse:
    available: bool | None
    price_usd: float | None
    provider: str
    error: str | None = None


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


async def _fetch_namecom(domain: str) -> ProviderResponse:
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
    # Prioritize Name.com (dev) then Domainr; others stubbed
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
        tasks: List[Tuple[str, str, asyncio.Task[ProviderResponse]]] = []
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
                tasks.append((name, d, asyncio.create_task(_fetch_best(d))))
                calls_made += 1
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
            )
            results.setdefault(name, []).append((domain, dcr))
            cache.set(domain, (dcr.available, dcr.registrar_price_usd, dcr.provider, dcr.error))
        return results

    return asyncio.run(_run())
