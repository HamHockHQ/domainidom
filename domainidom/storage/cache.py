from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Tuple


class DomainCache:
    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self._ensure()

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS domain_cache (
                    domain TEXT PRIMARY KEY,
                    available INTEGER,
                    price_usd REAL,
                    provider TEXT,
                    error TEXT
                )
                """
            )
            conn.commit()

    def get(
        self, domain: str
    ) -> Optional[Tuple[Optional[bool], Optional[float], Optional[str], Optional[str]]]:
        with sqlite3.connect(self.path) as conn:
            cur = conn.execute(
                "SELECT available, price_usd, provider, error FROM domain_cache WHERE domain=?",
                (domain,),
            )
            row = cur.fetchone()
            if not row:
                return None
            available = None if row[0] is None else bool(row[0])
            price = None if row[1] is None else float(row[1])
            provider = row[2]
            error = row[3]
            return (available, price, provider, error)

    def set(
        self,
        domain: str,
        data: Tuple[Optional[bool], Optional[float], Optional[str], Optional[str]],
    ) -> None:
        available, price, provider, error = data
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                "REPLACE INTO domain_cache(domain, available, price_usd, provider, error) VALUES(?,?,?,?,?)",
                (
                    domain,
                    None if available is None else int(bool(available)),
                    price,
                    provider,
                    error,
                ),
            )
            conn.commit()
