"""
D.R.O.N.A. evaluation runner - measures all four research contributions.

Usage:
    python scripts/run_evaluation.py              # run C2 + C3 (no ChromaDB/Ollama)
    python scripts/run_evaluation.py --all        # run C1–C4 (needs ChromaDB populated)
    python scripts/run_evaluation.py --c2 --c3    # specific contributions
    python scripts/run_evaluation.py --all --llm  # include Ollama latency (needs Ollama)
    python scripts/run_evaluation.py --out results/eval_$(date).json

The report is saved as JSON for reproducibility and inclusion in the thesis appendix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

# Run-as-script bootstrap: `python scripts/x.py` puts scripts/ on sys.path, not
# the repo root, so `import drona` fails unless the package is pip-installed.
sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.evaluation.harness import EvaluationHarness  # noqa: E402
from drona.utils.logging import setup_logging  # noqa: E402
from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(name="drona-eval", help="Run D.R.O.N.A. evaluation harness.")


@app.command()
def main(
    all_: bool = typer.Option(False, "--all", help="Run all evaluations (C1–C4)."),
    c1: bool = typer.Option(False, "--c1", help="Evaluate retrieval quality (needs ChromaDB)."),
    c2: bool = typer.Option(False, "--c2", help="Evaluate bias detection."),
    c3: bool = typer.Option(False, "--c3", help="Evaluate gesture smoothness."),
    c4: bool = typer.Option(False, "--c4", help="Evaluate stack/provenance metrics."),
    llm: bool = typer.Option(False, "--llm", help="Include Ollama latency in C4 (needs Ollama)."),
    out: str | None = typer.Option(None, "--out", help="Output JSON path."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(log_level)
    settings.ensure_dirs()

    if not any([all_, c1, c2, c3, c4]):
        typer.echo("No evaluation selected. Defaulting to --c2 --c3 (no external deps).")
        c2 = c3 = True

    run_c1 = all_ or c1
    run_c2 = all_ or c2
    run_c3 = all_ or c3
    run_c4 = all_ or c4

    typer.secho("\nD.R.O.N.A. Evaluation Harness", bold=True)
    typer.echo("─" * 50)
    active = [f"C{i}" for i, flag in enumerate([run_c1, run_c2, run_c3, run_c4], 1) if flag]
    typer.echo(f"Running: {', '.join(active)}")
    if llm:
        typer.echo("Ollama latency measurement: ENABLED")
    typer.echo()

    harness = EvaluationHarness()
    report = harness.run_all(
        run_c1=run_c1,
        run_c2=run_c2,
        run_c3=run_c3,
        run_c4=run_c4,
        c4_with_llm=llm,
    )

    # ── Print summary ──────────────────────────────────────────────────────────

    if report.c1:
        typer.secho("\n[C1] Retrieval Quality", bold=True)
        if report.c1.skipped:
            typer.secho(f"  SKIPPED: {report.c1.skip_reason}", fg=typer.colors.YELLOW)
        else:
            h = report.c1.hybrid_metrics
            d = report.c1.dense_only_metrics
            imp = report.c1.improvement
            for key in sorted(h):
                arrow = "▲" if imp.get(key, 0) >= 0 else "▼"
                typer.echo(
                    f"  {key}: hybrid={h[key]:.4f}  dense={d.get(key, 0):.4f}  "
                    f"{arrow}{abs(imp.get(key, 0)):.4f}"
                )
            typer.echo(f"  Queries processed: {report.c1.n_queries}")

    if report.c2:
        typer.secho("\n[C2] Bias Detection", bold=True)
        m = report.c2.macro_avg
        typer.echo(
            f"  Macro:  P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}"
        )
        typer.echo(f"  Queries: {report.c2.n_queries} ({report.c2.n_with_bias} biased, {report.c2.n_clean} clean)")
        for bias_type, bm in report.c2.per_bias_metrics.items():
            if bm.get("tp", 0) + bm.get("fn", 0) > 0:
                typer.echo(f"    {bias_type:<28} P={bm['precision']:.3f} R={bm['recall']:.3f} F1={bm['f1']:.3f}")

    if report.c3:
        typer.secho("\n[C3] Gesture Smoothness (Keyframe Baseline)", bold=True)
        typer.echo(f"  Mean jerk:        {report.c3.mean_jerk:.4f} rad/s³")
        typer.echo(f"  Mean path length: {report.c3.mean_path_length:.3f} rad")
        for gesture, gm in report.c3.per_gesture.items():
            typer.echo(
                f"    {gesture:<10} frames={int(gm['n_frames'])}  "
                f"jerk={gm['jerk']:.4f}  path={gm['path_length']:.3f}"
            )
        if report.c3.all_within_spec:
            typer.secho("  All gestures within spec.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"  Spec failures: {len(report.c3.spec_failures)}", fg=typer.colors.RED)
            for f in report.c3.spec_failures:
                typer.echo(f"    ✗ {f}")

    if report.c4:
        typer.secho("\n[C4] Stack / Provenance", bold=True)
        ratio = report.c4.nepal_citation_ratio
        src = getattr(report.c4, "ratio_source", "response")
        colour = typer.colors.GREEN if report.c4.target_met else typer.colors.YELLOW
        typer.secho(
            f"  Nepal citation ratio ({src}): {ratio:.1%} "
            f"({'✓ target met' if report.c4.target_met else '✗ below 40% target'})",
            fg=colour,
        )
        if src == "retrieval":
            typer.echo("    (measured over retrieved citations; run with --llm for response-level)")
        if report.c4.latency:
            lat = report.c4.latency
            note = "(retrieval-only)" if report.c4.latency_skipped else "(full pipeline)"
            typer.echo(
                f"  Latency {note}: mean={lat.get('mean_ms', 0):.0f}ms  "
                f"p95={lat.get('p95_ms', 0):.0f}ms"
            )

    if report.notes:
        typer.secho("\nNotes:", bold=True)
        for note in report.notes:
            typer.echo(f"  • {note}")

    # ── Save report ────────────────────────────────────────────────────────────

    if out:
        out_path = Path(out)
    else:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = settings.data_dir / "evaluation" / f"report_{ts}.json"

    report.save(out_path)
    typer.secho(f"\nReport saved: {out_path}", fg=typer.colors.CYAN)


if __name__ == "__main__":
    app()
