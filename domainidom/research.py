from __future__ import annotations

from typing import Dict, List

from .services.domain_check import check_domains as service_check_domains


def check_domains_for_names(names: List[str], tlds: List[str]) -> Dict[str, List[str]]:
    return {n: [f"{n}.{t}" for t in tlds] for n in names}


def check_domains(domain_candidates: Dict[str, List[str]]):
    return check_domains_for_candidates(domain_candidates)


def check_domains_for_candidates(domain_candidates: Dict[str, List[str]]):
    return service_check_domains(domain_candidates)
