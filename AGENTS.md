# AGENTS.md

A dedicated guide for autonomous coding agents (e.g., GitHub Copilot coding agent) to work effectively on this repository.

## Project Overview

- Goal: Build an app that ingests a project scope (by scanning repo files or a provided business overview) and outputs:
  - Brainstormed brand and business names
  - Candidate domain names across selected TLDs
  - Verified domain availability (+ pricing when possible)
  - Market and business insights
  - Ranked recommendations with rationale and alternatives
- Core qualities: Memorable, pronounceable, rhyming/clever where appropriate, brand-safe, SEO-aware.

## Architecture Plan (Phased)

- MVP (v0.1)
  - Python 3.11 project scaffold with CLI + FastAPI service skeleton
  - Single-run pipeline: ingest scope → generate name ideas → check availability for a short TLD list → basic scores → CSV/JSON report
  - Caching layer (SQLite) to avoid duplicate domain checks; simple rate limiting
- v0.2 Multi-Agent
  - Integrate Agency Swarm for orchestrated agents (Brainstormer → Researcher → Analyzer → Packager)
  - Add MCP FastDomainCheck for bulk availability; Name.com pricing
  - Add scoring modules: phonetic (Double Metaphone), memorability, SEO (basic keyword heuristics), basic trademark risk heuristic
- v1.0 Production
  - Add Strands Agents planning for complex jobs
  - Parallel querying, retry and backoff; persistent job runs; observability
  - Extended datasets (more TLDs), registrar comparisons, richer insights, UI (Streamlit/Next.js) if requested

## Agents (Target Design)

- Brainstormer: Generates diverse, on-brief name ideas using multiple methods (SCAMPER, role-storming, rhyme/phoneme patterns).
- Researcher: Expands to domain variants, checks availability via MCP/registrar APIs, fetches pricing.
- Analyzer: Scores for memorability, pronounceability, SEO potential, brand safety, cultural checks.
- Packager: Ranks and compiles a report (CSV/JSON + optional Markdown summary).

## Tech Stack (initial)

- Python 3.11, FastAPI, Typer (CLI), Pydantic, SQLite (cache), pytest
- Optional libs: agency-swarm, python-whois, python-Levenshtein, metaphone, pytrends
- Model provider: OpenAI-compatible via `OPENAI_API_KEY` (and optional `OPENAI_BASE_URL`)

## Setup Commands (Local Dev)

- Windows PowerShell:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

- Run API (dev):

```powershell
uvicorn domainidom.api:app --reload
```

- Run CLI examples:

```powershell
python -m domainidom.cli brainstorm --idea "AI travel planner for families" --tlds com io ai
python -m domainidom.cli research --idea-file scope.md --tlds com net io --max 50 --out report.json
```

- Run tests:

```powershell
pytest -q
```

## Build & Test Expectations

- Provide `pyproject.toml` with dependencies; include `pytest` and minimal unit tests.
- CI: Add GitHub Actions workflow to run lint and tests on PRs.
- All new features include tests for core scoring functions and domain-check caching.

## Secrets & Config

- Place secrets in environment variables (never commit):
  - `OPENAI_API_KEY` (required for LLM-based generation)
  - `NAME_COM_API_KEY` (pricing & availability if used)
  - `WHOISXML_API_KEY` (WHOIS intelligence if used)
  - `DOMAINR_API_KEY` (optional alternative availability API)
- Optional LLM endpoint override: `OPENAI_BASE_URL`
- Local `.env` supported; ensure `.gitignore` excludes it.

## External Services (planned)

- MCP: FastDomainCheck (bulk domain availability)
- Registrars/APIs: Name.com, Domainr; optional GoDaddy/Cloudflare registrars later
- WHOIS/Intelligence: WhoisXML (optional)
- SEO/Trends (optional): pytrends, public signals; avoid paid APIs unless keys are provided

## Coding Conventions

- Python: type hints required, Pydantic models for I/O, black/ruff formatting
- Functions should be pure where possible; side effects isolated
- Avoid over-engineering; keep modules cohesive with focused responsibilities

## Security & Safety

- Respect API rate limits and terms of service
- Never log secrets; use environment variables
- Avoid scraping sites with restrictive ToS; prefer official APIs
- Implement input sanitization and guardrails for prompt injection in LLM calls

## Rate Limits & Guardrails

- Default to dev/test providers and local LLM to avoid quota burn.
- Name.com: use `https://api.dev.name.com/v4` by default; enable prod only via env overrides.
- WHOISXML: disabled by default for availability checks. Enable explicitly with `USE_WHOISXML_FOR_AVAIL=1`.
- Token bucket rate limiting in `services/domain_check.py`:
  - `DOMAIN_CHECK_RPS` (default 3 RPS), `DOMAIN_CHECK_BURST` (default 5)
  - Global cap: `DOMAIN_CHECK_MAX_CALLS` (default 80 per run)
  - Exponential backoff: 0.5s, 1.0s, 2.0s
- Respect per-provider usage limits; batch with MCP when configured.

## Current Status (September 2025)

**✅ MVP (v0.1) COMPLETED**

- Full Python project scaffold with `pyproject.toml`, dependencies, tests
- Complete package structure: `api.py`, `cli.py`, `brainstorm.py`, `research.py`, `analyze.py`, `package.py`, `models.py`
- Services: `domain_check.py` (Name.com, Domainr), `pricing.py`, caching layer
- Utils: `phonetics.py` (Double Metaphone), scoring algorithms  
- Tests: Comprehensive coverage, all passing (`pytest -q`)
- GitHub repository: <https://github.com/HamHockHQ/domainidom>

**✅ Validation Checklist**

- `pytest -q` passes ✅
- `uvicorn domainidom.api:app --reload` starts and serves `/healthz` ✅
- CLI commands work: `python -m domainidom.cli brainstorm` ✅
- Domain research pipeline functional ✅
- Reports generated in `./reports/` ✅

## Tasks for Copilot Coding Agent (Next Phase)

**Current GitHub Issues (Ready for Assignment):**

1. **Issue #2**: Add GitHub Actions CI workflow for automated testing and linting
   - Priority: HIGH (enables validation for all future PRs)  
   - Complexity: LOW (standard CI setup)
   - Dependencies: None

2. **Issue #4**: Add multi-registrar pricing comparison system  
   - Priority: MEDIUM (enhances pricing coverage)
   - Complexity: MEDIUM (API integrations)
   - Dependencies: None (extends existing pricing service)

3. **Issue #1**: Add MCP FastDomainCheck integration for bulk domain availability
   - Priority: MEDIUM (performance enhancement)  
   - Complexity: MEDIUM (new MCP client integration)
   - Dependencies: None (pluggable provider model)

4. **Issue #3**: Implement Agency Swarm multi-agent orchestration system
   - Priority: LOW (v0.2 feature, major enhancement)
   - Complexity: HIGH (multi-agent coordination)  
   - Dependencies: Issues #1 (MCP integration provides foundation)

**Recommended Assignment Order:**

- Issues #2 + #4 in parallel (independent)
- Issue #1 after #2/#4 complete  
- Issue #3 last (depends on #1 for optimal agent coordination)

## PR Instructions

- Branches must start with `copilot/` when opened by GitHub Copilot
- Ensure `pytest -q` is green; format with black; lint with ruff
- Keep changes focused and minimal; update tests as needed

## Notes for Agents

- If dependencies or commands are missing, create them as part of the task
- Ask for missing API keys by commenting on the PR with the exact `ENV_VAR` names needed
- Prefer small, iterative PRs
