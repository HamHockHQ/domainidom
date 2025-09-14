from domainidom.storage.cache import DomainCache


def test_cache_roundtrip(tmp_path):
    db = tmp_path / "cache.sqlite3"
    cache = DomainCache(str(db))
    assert cache.get("example.com") is None
    cache.set("example.com", (True, 12.34, "stub", None))
    got = cache.get("example.com")
    assert got is not None
    assert got[0] is True
    assert got[1] == 12.34
    assert got[2] == "stub"
