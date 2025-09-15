# Multi-Registrar Pricing Configuration Guide

The domainidom system now supports multi-registrar pricing comparison across multiple domain registrars. This guide explains how to configure and use this feature.

## Supported Registrars

- **Name.com** - Full support with pricing and availability
- **GoDaddy** - Full support with pricing and availability  
- **Cloudflare** - Limited support (API access restricted)
- **Namecheap** - Availability checking only (pricing requires separate API calls)

## Environment Configuration

### Required API Keys

Configure the following environment variables for each registrar you want to use:

```bash
# Name.com (default: development API)
NAME_COM_USERNAME=your_username
NAME_COM_API_KEY=your_api_key
NAME_COM_BASE=https://api.dev.name.com/v4  # or https://api.name.com/v4 for production

# GoDaddy
GODADDY_API_KEY=your_api_key
GODADDY_API_SECRET=your_api_secret

# Cloudflare (limited availability)
CLOUDFLARE_API_TOKEN=your_api_token

# Namecheap
NAMECHEAP_API_USER=your_username
NAMECHEAP_API_KEY=your_api_key
```

### Feature Control

Enable or disable specific registrars:

```bash
# Enable/disable registrars (default: all enabled)
ENABLE_NAMECOM=1
ENABLE_GODADDY=1
ENABLE_CLOUDFLARE=1
ENABLE_NAMECHEAP=1

# Enable/disable multi-registrar pricing comparison (default: enabled)
ENABLE_MULTI_REGISTRAR=1
```

### Rate Limiting

Configure rate limits per registrar to respect API terms:

```bash
# Rate limits (requests per second)
NAMECOM_RPS=2
GODADDY_RPS=1
CLOUDFLARE_RPS=5
NAMECHEAP_RPS=1
```

## Usage

### CLI Usage

The CLI commands automatically use multi-registrar pricing when enabled:

```bash
# Generate names and check domains with price comparison
python -m domainidom.cli research --idea-file idea.txt --tld com --tld net --out report.json

# CSV output includes price comparison columns
python -m domainidom.cli research --idea-file idea.txt --tld com --out report.csv
```

### API Usage

```python
from domainidom.services.pricing import get_multi_registrar_pricing

# Get pricing from all configured registrars
price_comparison = await get_multi_registrar_pricing("example.com")

print(f"Domain: {price_comparison.domain}")
print(f"Best price: ${price_comparison.best_price.price_usd} from {price_comparison.best_price.registrar}")

for price in price_comparison.prices:
    print(f"{price.registrar}: ${price.price_usd} (available: {price.is_available})")
```

### Domain Checking Integration

The domain checking service automatically includes multi-registrar pricing when enabled:

```python
from domainidom.services.domain_check import check_domains

results = check_domains({"example": ["example.com", "example.net"]})

for name, domains in results.items():
    for domain, result in domains:
        print(f"Domain: {result.domain}")
        print(f"Available: {result.available}")
        print(f"Best price: ${result.registrar_price_usd}")
        
        if result.price_comparison:
            print("Price comparison:")
            for price in result.price_comparison.prices:
                print(f"  {price.registrar}: ${price.price_usd}")
```

## Report Format Changes

### JSON Reports

JSON reports now include a `price_comparison` field for each domain:

```json
{
  "results": [
    {
      "name": "Example",
      "domains": [
        {
          "domain": "example.com",
          "available": true,
          "price_usd": 12.99,
          "price_comparison": {
            "registrar_prices": [
              {
                "registrar": "namecom",
                "price_usd": 15.99,
                "is_available": true,
                "registration_url": "https://www.name.com/..."
              },
              {
                "registrar": "godaddy", 
                "price_usd": 12.99,
                "is_available": true,
                "registration_url": "https://www.godaddy.com/..."
              }
            ],
            "best_price": {
              "registrar": "godaddy",
              "price_usd": 12.99,
              "registration_url": "https://www.godaddy.com/..."
            }
          }
        }
      ]
    }
  ]
}
```

### CSV Reports

CSV reports include additional columns for price comparison:

- `best_price_usd` - Best available price across all registrars
- `best_registrar` - Registrar offering the best price
- `namecom_price` - Price from Name.com
- `godaddy_price` - Price from GoDaddy
- `cloudflare_price` - Price from Cloudflare
- `namecheap_price` - Price from Namecheap
- `registration_urls` - Semicolon-separated list of registration URLs

## Error Handling

The system gracefully handles various error conditions:

- **Missing credentials** - Registrars without API keys return "missing_credentials_or_disabled"
- **API failures** - Network/API errors are logged but don't stop other registrars
- **Rate limiting** - Automatic rate limiting prevents API quota exhaustion
- **Disabled registrars** - Can be selectively disabled via environment variables

## Backward Compatibility

The system maintains full backward compatibility:

- Existing `registrar_price_usd` field continues to work (shows best price)
- Legacy domain checking behavior is preserved when multi-registrar is disabled
- Existing JSON/CSV report formats are enhanced but not broken

## Performance Considerations

- Registrar queries run in parallel for better performance
- Built-in rate limiting respects API terms of service
- Caching prevents duplicate API calls for the same domain
- Configurable timeouts prevent hanging requests

## Best Practices

1. **Start with development APIs** - Use sandbox/development endpoints for testing
2. **Monitor usage** - Track API call counts to avoid exceeding quotas
3. **Configure rate limits** - Set conservative rate limits to respect API terms
4. **Cache results** - Use the built-in caching to minimize API calls
5. **Graceful degradation** - Don't rely on all registrars being available simultaneously