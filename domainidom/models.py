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
class DomainCheckResult:
    domain: str
    available: Optional[bool]
    registrar_price_usd: Optional[float] = None
    provider: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ScoredCandidate:
    name: str
    score: float
    details: Dict[str, float]
    domains: List[DomainCheckResult]
