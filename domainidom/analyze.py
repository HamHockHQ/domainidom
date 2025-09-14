from __future__ import annotations

from typing import Dict, List, Tuple

from .models import ScoredCandidate, DomainCheckResult
from .utils.phonetics import vowel_consonant_balance


def score_candidates(
    names: List[str], research_results: Dict[str, List[Tuple[str, DomainCheckResult]]]
) -> List[ScoredCandidate]:
    out: List[ScoredCandidate] = []
    for n in names:
        availability_score = 0.0
        domains = research_results.get(n, [])
        if domains:
            avail_count = sum(1 for _d, r in domains if getattr(r, "available", None))
            availability_score = min(1.0, avail_count / max(1, len(domains)))
        length_score = max(0.0, min(1.0, 12 / max(3, len(n))))
        balance_score = vowel_consonant_balance(n)
        final = 0.45 * length_score + 0.35 * balance_score + 0.20 * availability_score
        out.append(
            ScoredCandidate(
                name=n,
                score=round(final, 4),
                details={
                    "length": round(length_score, 4),
                    "balance": round(balance_score, 4),
                    "availability": round(availability_score, 4),
                },
                domains=[r for _d, r in domains],
            )
        )
    out.sort(key=lambda c: c.score, reverse=True)
    return out
