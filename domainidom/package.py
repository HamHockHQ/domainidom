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
            # Enhanced header with price comparison data
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
                    "best_price_usd",
                    "best_registrar",
                    "namecom_price",
                    "godaddy_price",
                    "cloudflare_price",
                    "namecheap_price",
                    "registration_urls",
                ]
            )
            for c in scored:
                # Write a row per domain to include pricing
                if c.domains:
                    for d in c.domains:
                        # Extract price comparison data
                        best_price = None
                        best_registrar = None
                        namecom_price = None
                        godaddy_price = None
                        cloudflare_price = None
                        namecheap_price = None
                        registration_urls = []

                        if d.price_comparison:
                            if d.price_comparison.best_price:
                                best_price = d.price_comparison.best_price.price_usd
                                best_registrar = d.price_comparison.best_price.registrar

                            for price in d.price_comparison.prices:
                                if price.registrar == "namecom":
                                    namecom_price = price.price_usd
                                elif price.registrar == "godaddy":
                                    godaddy_price = price.price_usd
                                elif price.registrar == "cloudflare":
                                    cloudflare_price = price.price_usd
                                elif price.registrar == "namecheap":
                                    namecheap_price = price.price_usd

                                if price.registration_url:
                                    registration_urls.append(
                                        f"{price.registrar}:{price.registration_url}"
                                    )

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
                                best_price,
                                best_registrar,
                                namecom_price,
                                godaddy_price,
                                cloudflare_price,
                                namecheap_price,
                                "; ".join(registration_urls),
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
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        ]
                    )
    else:
        data = []
        for c in scored:
            domain_data = []
            for d in c.domains:
                domain_entry = {
                    "domain": d.domain,
                    "available": d.available,
                    "provider": d.provider,
                    "price_usd": d.registrar_price_usd,
                    "error": d.error,
                }

                # Add price comparison data
                if d.price_comparison:
                    price_comparison_data = {"registrar_prices": [], "best_price": None}

                    for price in d.price_comparison.prices:
                        price_comparison_data["registrar_prices"].append(
                            {
                                "registrar": price.registrar,
                                "price_usd": price.price_usd,
                                "currency": price.currency,
                                "is_available": price.is_available,
                                "registration_url": price.registration_url,
                                "renewal_price_usd": price.renewal_price_usd,
                                "transfer_price_usd": price.transfer_price_usd,
                                "error": price.error,
                            }
                        )

                    if d.price_comparison.best_price:
                        price_comparison_data["best_price"] = {
                            "registrar": d.price_comparison.best_price.registrar,
                            "price_usd": d.price_comparison.best_price.price_usd,
                            "registration_url": d.price_comparison.best_price.registration_url,
                        }

                    domain_entry["price_comparison"] = price_comparison_data

                domain_data.append(domain_entry)

            data.append(
                {
                    "name": c.name,
                    "score": c.score,
                    "details": c.details,
                    "domains": domain_data,
                }
            )

        out.write_text(json.dumps({"results": data}, indent=2), encoding="utf-8")
