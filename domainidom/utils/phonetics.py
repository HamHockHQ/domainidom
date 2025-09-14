from __future__ import annotations

from typing import Tuple

from metaphone import doublemetaphone


def phonetic_similarity(a: str, b: str) -> float:
    da = doublemetaphone(a or "")
    db = doublemetaphone(b or "")
    score = 0.0
    if da[0] and da[0] == db[0]:
        score += 0.7
    if da[1] and db[1] and da[1] == db[1]:
        score += 0.3
    return score


def vowel_consonant_balance(s: str) -> float:
    if not s:
        return 0.0
    s2 = ''.join(ch.lower() for ch in s if ch.isalpha())
    if not s2:
        return 0.0
    vowels = sum(1 for ch in s2 if ch in 'aeiou')
    cons = max(1, len(s2) - vowels)
    ratio = vowels / cons
    # Ideal ratio ~ 0.6–1.4; map to 0..1
    if ratio < 0.6:
        return max(0.0, ratio / 0.6)
    if ratio > 1.4:
        return max(0.0, (2.0 - ratio) / 0.6)
    return 1.0
