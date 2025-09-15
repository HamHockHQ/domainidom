from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List

from .models import ScoredCandidate


def write_reports(scored: List[ScoredCandidate], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".csv":
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "name",
                    "score",
                    "length",
                    "balance",
                    "availability",
                    "domain",
                    "price_usd",
                    "provider",
                ]
            )
            for c in scored:
                # Write a row per domain to include pricing
                if c.domains:
                    for d in c.domains:
                        w.writerow(
                            [
                                c.name,
                                c.score,
                                c.details.get("length"),
                                c.details.get("balance"),
                                c.details.get("availability"),
                                d.domain,
                                d.registrar_price_usd,
                                d.provider,
                            ]
                        )
                else:
                    w.writerow(
                        [
                            c.name,
                            c.score,
                            c.details.get("length"),
                            c.details.get("balance"),
                            c.details.get("availability"),
                            None,
                            None,
                            None,
                        ]
                    )
    else:
        data = [
            {
                "name": c.name,
                "score": c.score,
                "details": c.details,
                "domains": [
                    {
                        "domain": d.domain,
                        "available": d.available,
                        "provider": d.provider,
                        "price_usd": d.registrar_price_usd,
                        "error": d.error,
                    }
                    for d in c.domains
                ],
            }
            for c in scored
        ]
        out.write_text(json.dumps({"results": data}, indent=2), encoding="utf-8")
