"""Tests for MCP FastDomainCheck integration."""

import os
import pytest
from unittest.mock import patch

from domainidom.services.domain_check import (
    is_mcp_fastdomaincheck_enabled,
    check_domains,
)


def test_mcp_fastdomaincheck_disabled_by_default():
    """Test that MCP FastDomainCheck is disabled by default."""
    # Ensure env var is not set
    os.environ.pop("MCP_FASTDOMAINCHECK_ENABLED", None)
    assert not is_mcp_fastdomaincheck_enabled()


def test_mcp_fastdomaincheck_enabled_with_env():
    """Test that MCP FastDomainCheck can be enabled via env var."""
    with patch.dict(os.environ, {"MCP_FASTDOMAINCHECK_ENABLED": "1"}):
        assert is_mcp_fastdomaincheck_enabled()


def test_check_domains_with_mcp_disabled(tmp_path, monkeypatch):
    """Test check_domains works normally when MCP is disabled."""
    db = tmp_path / "cache.sqlite3"
    monkeypatch.setenv("DOMAIN_CACHE_PATH", str(db))
    monkeypatch.setenv("MCP_FASTDOMAINCHECK_ENABLED", "0")
    
    # Without httpx available, should get stub responses
    results = check_domains({"test": ["example.com"]})
    
    assert "test" in results
    assert len(results["test"]) == 1
    
    domain, dcr = results["test"][0]
    assert domain == "example.com"
    # When httpx is not available, multi-registrar pricing returns a stub
    assert dcr.provider in ["stub", "error", "multi-registrar"]


def test_check_domains_with_mcp_enabled_no_httpx(tmp_path, monkeypatch):
    """Test check_domains with MCP enabled but no httpx available."""
    db = tmp_path / "cache.sqlite3"
    monkeypatch.setenv("DOMAIN_CACHE_PATH", str(db))
    monkeypatch.setenv("MCP_FASTDOMAINCHECK_ENABLED", "1")
    monkeypatch.setenv("MCP_FASTDOMAINCHECK_API_KEY", "test-key")
    
    results = check_domains({"test": ["example.com"]})
    
    assert "test" in results
    assert len(results["test"]) == 1
    
    domain, dcr = results["test"][0]
    assert domain == "example.com"
    # Should get httpx_not_available error or fallback to other providers
    assert dcr.provider in ["mcp-fastdomaincheck", "stub", "error"]


def test_mcp_batch_size_configuration():
    """Test MCP batch size can be configured via environment."""
    with patch.dict(os.environ, {"MCP_BATCH_SIZE": "50"}):
        # Need to reload the module to pick up new env var
        import importlib
        import domainidom.services.domain_check
        importlib.reload(domainidom.services.domain_check)
        
        from domainidom.services.domain_check import MCP_BATCH_SIZE
        assert MCP_BATCH_SIZE == 50


def test_mcp_configuration_defaults():
    """Test MCP configuration defaults."""
    # Clear environment
    for key in ["MCP_FASTDOMAINCHECK_ENABLED", "MCP_BATCH_SIZE"]:
        os.environ.pop(key, None)
    
    # Reload module to get defaults
    import importlib
    import domainidom.services.domain_check
    importlib.reload(domainidom.services.domain_check)
    
    from domainidom.services.domain_check import MCP_BATCH_SIZE, is_mcp_fastdomaincheck_enabled
    
    assert MCP_BATCH_SIZE == 20  # Default batch size
    assert not is_mcp_fastdomaincheck_enabled()  # Disabled by default


def test_check_domains_cached_results_with_mcp(tmp_path, monkeypatch):
    """Test that cached results are used even when MCP is enabled."""
    db = tmp_path / "cache.sqlite3"
    monkeypatch.setenv("DOMAIN_CACHE_PATH", str(db))
    monkeypatch.setenv("MCP_FASTDOMAINCHECK_ENABLED", "1")
    
    # Pre-populate cache
    from domainidom.storage.cache import DomainCache
    cache = DomainCache(str(db))
    cache.set("cached.com", (True, 15.0, "cache-provider", None))
    
    results = check_domains({"test": ["cached.com", "uncached.com"]})
    
    assert "test" in results
    assert len(results["test"]) == 2
    
    # Find cached result
    cached_result = None
    uncached_result = None
    for domain, dcr in results["test"]:
        if domain == "cached.com":
            cached_result = dcr
        elif domain == "uncached.com":
            uncached_result = dcr
    
    assert cached_result is not None
    assert cached_result.available is True
    assert cached_result.registrar_price_usd == 15.0
    assert cached_result.provider == "cache-provider"
    
    assert uncached_result is not None
    # Uncached should have been processed by MCP or fallback provider