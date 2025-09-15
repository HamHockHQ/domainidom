from __future__ import annotations

import json
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from .config import load_env

from .brainstorm import brainstorm_names
from .research import check_domains
from .analyze import score_candidates
from .package import write_reports
from .multi_agent import run_multi_agent_research

app = typer.Typer(add_completion=False)


@app.command()
def brainstorm(
    idea: str = typer.Option(..., help="Business idea overview"),
    tlds: List[str] = typer.Option(
        ["com", "io", "ai"], "--tld", "-t", help="Repeatable TLDs to consider"
    ),
    max_candidates: int = typer.Option(50, help="Max number of names to generate"),
    out: Optional[Path] = typer.Option(None, help="Output JSON path (optional)"),
):
    names = brainstorm_names(idea=idea, max_candidates=max_candidates)
    domains_by_name = {n: [f"{n}.{t}" for t in tlds] for n in names}
    if out:
        out.write_text(json.dumps({"names": names, "domains": domains_by_name}, indent=2))
    typer.echo(f"Generated {len(names)} names")


@app.command()
def research(
    idea_file: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False),
    tlds: List[str] = typer.Option(
        ["com", "io", "ai"], "--tld", "-t", help="Repeatable TLDs to consider"
    ),
    max: int = typer.Option(50, help="Max candidates"),
    out: Optional[Path] = typer.Option(
        None, help="Output report path (JSON if endswith .json else CSV)"
    ),
):
    idea = idea_file.read_text(encoding="utf-8").strip()
    names = brainstorm_names(idea=idea, max_candidates=max)
    domain_candidates = {n: [f"{n}.{t}" for t in tlds] for n in names}
    research_results = check_domains(domain_candidates)
    scored = score_candidates(names, research_results)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if out is None:
        out = Path("reports") / f"report-{timestamp}.json"
    write_reports(scored, out)
    typer.echo(f"Report written to {out}")


@app.command()
def multi_agent(
    idea: str = typer.Option(..., help="Business idea overview"),
    tlds: List[str] = typer.Option(
        ["com", "io", "ai"], "--tld", "-t", help="Repeatable TLDs to consider"
    ),
    max_candidates: int = typer.Option(50, help="Max number of names to generate"),
    out: Optional[Path] = typer.Option(
        None, help="Output report path (JSON if endswith .json else CSV)"
    ),
    enable_multi_agent: bool = typer.Option(
        None, help="Enable multi-agent mode (overrides USE_MULTI_AGENT env var)"
    ),
):
    """Run multi-agent domain research workflow with specialized agents"""
    
    # Check if multi-agent mode is enabled
    use_multi_agent = enable_multi_agent
    if use_multi_agent is None:
        use_multi_agent = os.getenv("USE_MULTI_AGENT", "0").lower() in ("1", "true", "yes")
    
    if not use_multi_agent:
        typer.echo("Multi-agent mode is disabled. Use --enable-multi-agent or set USE_MULTI_AGENT=1")
        typer.echo("Falling back to single-agent pipeline...")
        
        # Fall back to existing research command logic
        names = brainstorm_names(idea=idea, max_candidates=max_candidates)
        domain_candidates = {n: [f"{n}.{t}" for t in tlds] for n in names}
        research_results = check_domains(domain_candidates)
        scored = score_candidates(names, research_results)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if out is None:
            out = Path("reports") / f"single-agent-report-{timestamp}.json"
        write_reports(scored, out)
        typer.echo(f"Single-agent report written to {out}")
        return
    
    # Run multi-agent workflow
    typer.echo("🚀 Starting multi-agent domain research workflow...")
    
    def make_json_serializable(obj):
        """Convert objects to JSON serializable format"""
        if hasattr(obj, '__dict__'):
            # Convert dataclass or object to dict
            result = {}
            for key, value in obj.__dict__.items():
                result[key] = make_json_serializable(value)
            return result
        elif isinstance(obj, list):
            return [make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: make_json_serializable(value) for key, value in obj.items()}
        else:
            return obj
    
    async def run_workflow():
        try:
            result = await run_multi_agent_research(
                idea=idea,
                tlds=tlds,
                max_candidates=max_candidates
            )
            
            # Generate output file
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            if out is None:
                out_path = Path("reports") / f"multi-agent-report-{timestamp}.json"
            else:
                out_path = out
                
            # Ensure reports directory exists
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            if str(out_path).endswith('.json'):
                # Write comprehensive JSON report
                # Convert ScoredCandidate objects to dictionaries
                serializable_result = make_json_serializable(result)
                out_path.write_text(json.dumps(serializable_result, indent=2), encoding="utf-8")
            else:
                # Write CSV using existing scored candidates
                scored_candidates = result.get("candidates", [])
                write_reports(scored_candidates, out_path)
                
                # Also write a summary JSON
                summary_path = out_path.with_suffix('.summary.json')
                summary_data = {
                    "summary": result.get("summary", {}),
                    "recommendations": result.get("recommendations", []),
                    "insights": result.get("insights", {}),
                    "execution_log": result.get("execution_log", [])
                }
                summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
                typer.echo(f"Summary written to {summary_path}")
            
            typer.echo(f"✅ Multi-agent report written to {out_path}")
            
            # Display summary
            summary = result.get("summary", {})
            recommendations = result.get("recommendations", [])
            
            typer.echo("\n📊 Executive Summary:")
            typer.echo(f"   Total candidates: {summary.get('total_candidates', 0)}")
            typer.echo(f"   Available domains: {summary.get('available_domains', 0)}")
            typer.echo(f"   Average score: {summary.get('average_score', 0)}")
            typer.echo(f"   Execution time: {result.get('total_execution_time', 0):.2f}s")
            
            if recommendations:
                typer.echo("\n🏆 Top Recommendations:")
                for rec in recommendations[:3]:
                    typer.echo(f"   {rec['rank']}. {rec['name']} (score: {rec['score']:.3f})")
                    if rec.get('best_domain'):
                        typer.echo(f"      Best domain: {rec['best_domain']}")
                    if rec.get('rationale'):
                        typer.echo(f"      Rationale: {', '.join(rec['rationale'])}")
                    typer.echo()
            
        except Exception as e:
            typer.echo(f"❌ Multi-agent workflow failed: {e}")
            raise typer.Exit(1)
    
    # Run the async workflow
    asyncio.run(run_workflow())


if __name__ == "__main__":
    load_env()
    app()
