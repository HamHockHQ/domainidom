# Multi-Agent Domain Research System

## Overview

The domainidom multi-agent system orchestrates specialized AI agents to perform comprehensive domain name research and brainstorming. Each agent has a specific role in the pipeline, working together to generate creative names, research availability, analyze quality, and package results.

## Architecture

### Agent Roles

1. **Brainstormer Agent** - Generates diverse, creative domain name ideas
   - Implements SCAMPER methodology (Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse)
   - Uses role-storming from different user perspectives
   - Focuses on rhyme/phoneme patterns and memorability
   - Applies multiple creative methodologies in parallel

2. **Researcher Agent** - Expands names and checks domain availability
   - Generates domain variants (shortened, prefixed, vowel-modified versions)
   - Checks availability across multiple TLDs
   - Integrates with domain registrar APIs for pricing
   - Handles caching to avoid duplicate API calls

3. **Analyzer Agent** - Scores names for business value
   - Evaluates memorability and pronounceability
   - Analyzes SEO potential and keyword relevance
   - Performs brand safety and trademark risk assessment
   - Checks cultural appropriateness and global appeal
   - Provides enhanced scoring beyond basic metrics

4. **Packager Agent** - Creates comprehensive final reports
   - Ranks results based on multiple scoring factors
   - Generates detailed rationale for each recommendation
   - Provides alternative suggestions and backup options
   - Creates executive summary and business insights
   - Outputs in multiple formats (JSON, CSV, Markdown)

### Workflow

```
IdeaInput → Brainstormer → Researcher → Analyzer → Packager → Final Report
```

The agents work in sequence, with each agent receiving the output of the previous agent as input. The orchestrator manages the workflow and handles error scenarios.

## Usage

### CLI Commands

#### Basic Multi-Agent Command
```bash
python -m domainidom.cli multi-agent --idea "AI travel planner for families" --enable-multi-agent
```

#### With Custom Parameters
```bash
python -m domainidom.cli multi-agent \
  --idea "AI startup for small businesses" \
  --tld com --tld io --tld ai \
  --max-candidates 20 \
  --enable-multi-agent \
  --out reports/my-research.json
```

#### Using Environment Variable
```bash
# Enable multi-agent mode globally
export USE_MULTI_AGENT=1

python -m domainidom.cli multi-agent --idea "Fintech app"
```

### Python API

```python
import asyncio
from domainidom.multi_agent import run_multi_agent_research

async def main():
    result = await run_multi_agent_research(
        idea="AI-powered fitness coaching app",
        tlds=["com", "io", "app", "ai"],
        max_candidates=30
    )
    
    print("Top recommendation:", result["recommendations"][0]["name"])
    print("Score:", result["recommendations"][0]["score"])
    print("Rationale:", result["recommendations"][0]["rationale"])

asyncio.run(main())
```

## Configuration

### Environment Variables

- `USE_MULTI_AGENT=1` - Enable multi-agent mode globally
- `OPENAI_API_KEY` - API key for LLM-based name generation
- `OPENAI_BASE_URL` - Custom LLM endpoint (default: http://127.0.0.1:1234/v1)
- `OPENAI_MODEL` - Model name (default: qwen3-coder-30b-a3b-instruct)
- `DOMAIN_CHECK_RPS=3` - Rate limit for domain checking
- `DOMAIN_CHECK_MAX_CALLS=80` - Maximum API calls per workflow run
- `DOMAIN_CACHE_PATH=domain_cache.sqlite3` - Cache file location

### Agent Configuration

Each agent can be customized by modifying their instructions and parameters:

```python
from domainidom.multi_agent import MultiAgentOrchestrator

orchestrator = MultiAgentOrchestrator()

# Customize brainstormer instructions
orchestrator.brainstormer.instructions = """
Generate highly technical, developer-focused brand names using:
- Technical terminology and abbreviations
- Code-inspired naming patterns
- Developer tool conventions
"""

# Run workflow
result = await orchestrator.execute_workflow(idea_input)
```

## Output Format

The multi-agent system generates comprehensive JSON reports with the following structure:

```json
{
  "candidates": [
    {
      "name": "TechFlow",
      "score": 0.853,
      "details": {
        "length": 1.0,
        "balance": 0.9,
        "availability": 0.8,
        "seo": 0.85,
        "brand_safety": 0.9,
        "cultural": 1.0
      },
      "domains": [
        {
          "domain": "techflow.com",
          "available": true,
          "registrar_price_usd": 12.99,
          "provider": "namecom"
        }
      ]
    }
  ],
  "summary": {
    "total_candidates": 25,
    "available_domains": 45,
    "average_score": 0.74,
    "top_score": 0.92,
    "generated_at": "2024-09-15T09:09:39"
  },
  "recommendations": [
    {
      "rank": 1,
      "name": "TechFlow",
      "score": 0.853,
      "available_domains": 3,
      "best_domain": "techflow.com",
      "rationale": [
        "Optimal length for memorability",
        "Strong SEO potential",
        "High brand safety score"
      ]
    }
  ],
  "alternatives": ["FlowTech", "TechStream", "CodeFlow"],
  "insights": {
    "avg_length_score": 0.82,
    "avg_balance_score": 0.78,
    "high_scoring_names": 8,
    "available_premium_domains": 12
  },
  "execution_log": [
    {
      "agent_name": "Brainstormer",
      "success": true,
      "execution_time": 2.34
    }
  ],
  "total_execution_time": 8.76,
  "workflow_version": "multi-agent-v1.0"
}
```

## Error Handling

The multi-agent system includes comprehensive error handling:

### Fallback Mechanisms
- If LLM is unavailable, brainstormer uses predefined creative names
- If domain APIs fail, cached results are used when available
- If one agent fails, the workflow can continue with reduced functionality

### Rate Limiting
- Built-in rate limiting prevents API quota exhaustion
- Configurable limits per provider
- Exponential backoff for failed requests

### Backward Compatibility
- System falls back to single-agent mode if multi-agent is disabled
- All existing CLI commands continue to work unchanged
- Reports are compatible with existing analysis tools

## Performance

### Execution Times
- Typical workflow: 5-15 seconds for 50 candidates
- Brainstorming: 1-3 seconds (depends on LLM response time)
- Research: 2-8 seconds (depends on domain API response times)
- Analysis: 1-2 seconds (local computation)
- Packaging: <1 second (local computation)

### Optimization
- Parallel processing within agents where possible
- Caching to avoid duplicate API calls
- Batch processing for domain availability checks
- Configurable limits to prevent runaway costs

## Development

### Adding New Agents

To add a new agent to the workflow:

1. Create a new agent class inheriting from `BaseAgent`:

```python
class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="CustomAgent",
            instructions="Custom agent instructions"
        )
    
    async def execute(self, input_data):
        # Implementation here
        return AgentResult(...)
```

2. Add the agent to the orchestrator:

```python
class MultiAgentOrchestrator:
    def __init__(self):
        # ... existing agents
        self.custom_agent = CustomAgent()
    
    async def execute_workflow(self, idea_input):
        # ... existing workflow
        custom_result = await self.custom_agent.execute(analysis_result.data)
```

### Testing

The multi-agent system includes comprehensive tests:

```bash
# Run multi-agent specific tests
python -m pytest tests/test_multi_agent.py -v

# Run all tests
python -m pytest -q
```

### Debugging

Enable debug logging to trace agent execution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Agents will log their execution steps
result = await run_multi_agent_research("test idea")
```

## Comparison with Single-Agent Mode

| Feature | Single-Agent | Multi-Agent |
|---------|-------------|-------------|
| Creative Methods | Basic LLM prompting | SCAMPER + Role-storming + Multiple techniques |
| Domain Variants | Simple TLD variations | Generated variants + prefixes + modifications |
| Scoring | Basic metrics | Enhanced scoring + SEO + Brand safety + Cultural analysis |
| Output | Simple CSV/JSON | Comprehensive package + recommendations + insights |
| Execution Time | 3-8 seconds | 5-15 seconds |
| Complexity | Low | Medium |
| Customization | Limited | High |

## Future Enhancements

### Planned Features
- Integration with Agency Swarm framework for advanced orchestration
- MCP FastDomainCheck integration for bulk availability checking
- Advanced trademark and legal analysis
- Market trend analysis and competitive intelligence
- Multi-language support and localization
- Real-time collaboration between agents
- Learning from user feedback and preferences

### Extensibility
The system is designed to be easily extensible:
- Plugin architecture for new creative methodologies
- Configurable scoring algorithms
- Custom output formats
- Integration with external APIs and services
- Custom agent implementations