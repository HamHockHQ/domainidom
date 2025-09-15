from __future__ import annotations

from typing import Dict, List
import re

from .services.domain_check import check_domains as service_check_domains


def _to_label(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"^`+|`+$", "", s)
    s = s.strip("\"' ,")  # strip quotes/commas if present
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def check_domains_for_names(names: List[str], tlds: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for n in names:
        label = _to_label(n)
        if not label:
            out[n] = []
            continue
        out[n] = [f"{label}.{t}" for t in tlds]
    return out


def check_domains(domain_candidates: Dict[str, List[str]]):
    return check_domains_for_candidates(domain_candidates)


def check_domains_for_candidates(domain_candidates: Dict[str, List[str]]):
    return service_check_domains(domain_candidates)
