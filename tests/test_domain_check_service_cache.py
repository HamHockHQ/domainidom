import os

from domainidom.storage.cache import DomainCache
from domainidom.services.domain_check import check_domains


def test_service_uses_cache(tmp_path, monkeypatch):
    db = tmp_path / "cache.sqlite3"
    monkeypatch.setenv("DOMAIN_CACHE_PATH", str(db))

    cache = DomainCache(str(db))
    cache.set("example.com", (True, 10.0, "stub", None))

    results = check_domains({"ex": ["example.com"]})
    assert "ex" in results
    assert len(results["ex"]) == 1
    domain, dcr = results["ex"][0]
    assert domain == "example.com"
    assert dcr.available is True
    assert dcr.provider == "stub"
    assert dcr.registrar_price_usd == 10.0
