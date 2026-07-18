"""
CLI entry point for D.R.O.N.A. advising engine.

Usage:
    python scripts/advise.py "What careers suit a Python developer in Nepal?"
    python scripts/advise.py --year 2 --modules 4001COMP,4002COMP "How do I get into ML?"
    python scripts/advise.py --geography nepal --pathways 4 "What jobs are available locally?"
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

# Run-as-script bootstrap: `python scripts/x.py` puts scripts/ on sys.path, not
# the repo root, so `import drona` fails unless the package is pip-installed.
sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.advising.engine import AdvisingEngine, make_query  # noqa: E402
from drona.utils.logging import setup_logging  # noqa: E402
from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(name="drona-advise", help="Run the D.R.O.N.A. advising engine.")


@app.command()
def main(
    query: str = typer.Argument(..., help="The advising question to answer."),
    year: int | None = typer.Option(None, "--year", "-y", help="Student year of study (1-4)."),
    modules: str | None = typer.Option(
        None, "--modules", "-m", help="Comma-separated completed module codes."
    ),
    skills: str | None = typer.Option(
        None, "--skills", "-s", help="Comma-separated declared skills."
    ),
    geography: str = typer.Option(
        "any", "--geography", "-g",
        help="Aspiration geography: nepal, regional, international, any."
    ),
    pathways: int = typer.Option(3, "--pathways", "-p", help="Number of pathways to return."),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level."),
    json_out: bool = typer.Option(False, "--json", help="Output raw JSON instead of pretty print."),
) -> None:
    setup_logging(log_level)
    settings.ensure_dirs()

    completed = [m.strip() for m in modules.split(",")] if modules else []
    skill_list = [s.strip() for s in skills.split(",")] if skills else []

    advising_query = make_query(
        text=query,
        year=year,
        completed=completed,
        skills=skill_list,
        geography=geography,
        max_pathways=pathways,
    )

    typer.echo(f"\nDRONA Advising Engine\nQuery: {query}\n{'─' * 60}")

    engine = AdvisingEngine()
    response = engine.advise(advising_query)

    if json_out:
        typer.echo(response.model_dump_json(indent=2))
        return

    if response.refusal:
        typer.secho(f"\n[REFUSAL] {response.refusal_reason}", fg=typer.colors.YELLOW)
        return

    typer.secho(f"\nSummary: {response.summary}", fg=typer.colors.GREEN)

    if response.bias_flags:
        typer.secho("\nBias Flags Detected:", fg=typer.colors.CYAN)
        for bf in response.bias_flags:
            typer.echo(f"  • {bf.bias_type}: {bf.detected_signal[:80]}")

    for i, pw in enumerate(response.pathways, 1):
        typer.secho(f"\n[{i}] {pw.pathway_title} - confidence: {pw.confidence}", bold=True)
        typer.echo(f"    {pw.rationale}")
        if pw.local_market_evidence:
            typer.echo(f"    Nepal market: {pw.local_market_evidence[:120]}")
        if pw.next_concrete_steps:
            typer.echo("    Next steps:")
            for step in pw.next_concrete_steps:
                typer.echo(f"      → {step}")

    typer.secho(f"\nRobot says: \"{response.speak_text}\"", fg=typer.colors.BRIGHT_WHITE)

    if response.generation_time_ms is not None:
        typer.echo(f"\n(Generated in {response.generation_time_ms}ms)")


if __name__ == "__main__":
    app()
