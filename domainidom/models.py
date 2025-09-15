from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class IdeaInput:
    idea: Optional[str] = None
    repo_path: Optional[str] = None
    tlds: Optional[List[str]] = None
    max_candidates: int = 50


@dataclass
class NameCandidate:
    name: str
    domains: List[str]
    meta: Dict[str, str] | None = None


@dataclass
class RegistrarPrice:
    """Price information from a specific registrar."""

    registrar: str
    price_usd: Optional[float]
    currency: str = "USD"
    is_available: Optional[bool] = None
    registration_url: Optional[str] = None
    renewal_price_usd: Optional[float] = None
    transfer_price_usd: Optional[float] = None
    error: Optional[str] = None


@dataclass
class PriceComparison:
    """Comparison of prices across multiple registrars."""

    domain: str
    prices: List[RegistrarPrice]
    best_price: Optional[RegistrarPrice] = None

    def __post_init__(self):
        """Calculate the best price after initialization."""
        if not self.best_price and self.prices:
            available_prices = [
                p for p in self.prices if p.price_usd is not None and p.is_available
            ]
            if available_prices:
                self.best_price = min(available_prices, key=lambda p: p.price_usd)


@dataclass
class DomainCheckResult:
    domain: str
    available: Optional[bool]
    registrar_price_usd: Optional[float] = None
    provider: Optional[str] = None
    error: Optional[str] = None
    # New multi-registrar pricing data
    price_comparison: Optional[PriceComparison] = None


@dataclass
class ScoredCandidate:
    name: str
    score: float
    details: Dict[str, float]
    domains: List[DomainCheckResult]
