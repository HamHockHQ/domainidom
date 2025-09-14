from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer
from .config import load_env

from .brainstorm import brainstorm_names
from .research import check_domains
from .analyze import score_candidates
from .package import write_reports

app = typer.Typer(add_completion=False)


@app.command()
def brainstorm(
    idea: str = typer.Option(..., help="Business idea overview"),
    tlds: List[str] = typer.Option(["com", "io", "ai"], "--tld", "-t", help="Repeatable TLDs to consider"),
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
    tlds: List[str] = typer.Option(["com", "io", "ai"], "--tld", "-t", help="Repeatable TLDs to consider"),
    max: int = typer.Option(50, help="Max candidates"),
    out: Optional[Path] = typer.Option(None, help="Output report path (JSON if endswith .json else CSV)"),
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


if __name__ == "__main__":
    load_env()
    app()
