"""
D.R.O.N.A. full-system simulation runner - no ROS2 required.

Runs the complete Phase 1 pipeline in a single process:
  - StubDetector generates a scripted engagement sequence
  - SessionMachine drives the session lifecycle
  - GestureDispatcher executes arm gestures in StubEnv
  - AdvisingEngine answers a test query (if Ollama is running)
  - Visualizer shows arm motion (MuJoCo or Matplotlib)

This script is the primary demo tool for Phase 1. For Phase 2 (ROS2),
use the launch files in ros2_ws/src/drona_bringup/launch/.

Usage:
    python scripts/run_simulation.py
    python scripts/run_simulation.py --query "What jobs suit a Python developer in Nepal?"
    python scripts/run_simulation.py --no-advising  # gestures only, no LLM
    python scripts/run_simulation.py --no-viz       # headless, for CI
    python scripts/run_simulation.py --gestures greet,nod,farewell
"""

from __future__ import annotations

import time

import typer

app = typer.Typer(name="drona-sim", help="Run D.R.O.N.A. full simulation.")


@app.command()
def main(
    query: str = typer.Option(
        "What career paths are available for BSc Computing graduates in Nepal?",
        "--query", "-q",
        help="Student query to submit during advising phase.",
    ),
    no_advising: bool = typer.Option(False, "--no-advising", help="Skip LLM advising."),
    no_viz: bool = typer.Option(False, "--no-viz", help="Run headless (no visualizer window)."),
    gestures: str = typer.Option(
        "all", "--gestures",
        help="Comma-separated gesture sequence, or 'all' for full session.",
    ),
    save_frames: str | None = typer.Option(
        None, "--save-frames", help="Save visualizer frames to this directory."
    ),
    checkpoint_dir: str | None = typer.Option(
        None, "--checkpoint-dir", help="ACT checkpoint directory (auto-detected if omitted)."
    ),
    dt: float = typer.Option(0.05, "--dt", help="Simulation timestep (seconds)."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    from drona.utils.logging import setup_logging
    from drona.utils.settings import settings
    setup_logging(log_level)
    settings.ensure_dirs()

    typer.secho("\nD.R.O.N.A. Simulation", bold=True)
    typer.echo("─" * 50)

    # ── Visualizer ─────────────────────────────────────────────────────────────
    viz = None
    if not no_viz:
        try:
            from drona.interaction.visualizer import make_visualizer
            viz = make_visualizer(
                prefer_mujoco=True,
                output_dir=save_frames,
                show=not save_frames,
            )
            typer.echo("Visualizer: ready")
        except Exception as exc:
            typer.secho(f"Visualizer unavailable ({exc}) - running headless.", fg=typer.colors.YELLOW)

    # ── Policy router ──────────────────────────────────────────────────────────
    # The PolicyRouter auto-loads a trained ACT/Diffusion checkpoint per gesture
    # from checkpoint_base_dir when present, else falls back to the keyframe
    # policy. The viz loop below drives it frame-by-frame (GestureDispatcher wraps
    # the same router for the headless InteractionAction path).
    from drona.interaction.act_policy import PolicyRouter

    ckpt = checkpoint_dir or str(settings.data_dir / "checkpoints")
    router = PolicyRouter(checkpoint_base_dir=ckpt, device="cpu")

    def run_gesture(label: str, target=None) -> None:
        from drona.interaction.mujoco_env import StubEnv

        policy = router.get_policy(label)
        policy.reset()
        env = StubEnv(dt=dt)
        obs = env.reset()

        typer.echo(f"  → {label} ({policy.name})")
        while not getattr(policy, "is_complete", False):
            action = policy.select_action({"observation.state": obs})
            obs, _ = env.step(action)
            if viz:
                viz.update(obs, label=f"{label} | {policy.name}")
            time.sleep(dt)
        env.close()

    # ── Gesture-only mode ──────────────────────────────────────────────────────
    if gestures.strip().lower() != "all":
        typer.secho("\nGesture playback mode:", bold=True)
        for label in [g.strip() for g in gestures.split(",")]:
            typer.echo(f"\nGesture: {label}")
            run_gesture(label)
        if viz:
            viz.close()
        return

    # ── Full session simulation ────────────────────────────────────────────────
    from drona.orchestrator.session_machine import SessionMachine
    from drona.orchestrator.session_machine import SessionState as SessState
    from drona.perception.mediapipe_detector import make_detector

    machine = SessionMachine()
    detector = make_detector(prefer_mediapipe=False)  # StubDetector

    typer.secho("\nRunning full session simulation ...", bold=True)
    typer.echo("Engagement sequence: ABSENT → APPROACHING → ENGAGED → DISENGAGING → ABSENT")
    typer.echo()

    # State-driven loop with idempotent guards. The StubDetector drives
    # IDLE→GREETING (on ENGAGED); the lifecycle hooks below then walk the FSM
    # GREETING→NEEDS_ASSESSMENT→ADVISING→CLOSURE→IDLE deterministically.
    greeted = advised = closed = False
    summary = machine.session_summary()

    for step in range(120):
        detection = detector.detect()

        old = machine.state
        machine.feed_detection(detection)
        state = machine.state

        if state != old:
            typer.secho(f"  [{step:3d}] {old.value:20s} → {state.value}", fg=typer.colors.CYAN)

        if state == SessState.GREETING and not greeted:
            typer.echo("  → Executing: GREET")
            run_gesture("greet")
            machine.mark_greeted()
            greeted = True

        elif state == SessState.NEEDS_ASSESSMENT and not advised:
            typer.echo(f"  → Advising query: {query[:60]}")
            _do_advising(query, machine, run_gesture, no_advising)
            advised = True

        elif state == SessState.CLOSURE and not closed:
            typer.echo("  → Executing: FAREWELL")
            run_gesture("farewell")
            # Capture the summary BEFORE closing - returning to IDLE starts a
            # fresh session and resets the per-session query counter.
            summary = machine.session_summary()
            machine.mark_session_closed()
            closed = True
            break  # session complete

        time.sleep(0.05)

    if viz:
        viz.close()

    typer.secho("\nSimulation complete.", fg=typer.colors.GREEN)
    typer.echo(f"Session queries answered: {summary['query_count']}")
    typer.echo(f"State transitions:        {summary['event_count']}")


def _do_advising(
    query_text: str,
    machine,
    run_gesture_fn,
    no_advising: bool,
) -> None:
    run_gesture_fn("listen")
    # NEEDS_ASSESSMENT → ADVISING (must happen before mark_response_delivered,
    # which advances ADVISING → CLOSURE).
    machine.submit_query(query_text)

    if no_advising:
        typer.echo("  [advising skipped - --no-advising]")
        machine.mark_response_delivered()
        return

    try:
        from drona.advising.engine import AdvisingEngine, make_query
        engine = AdvisingEngine()
        q = make_query(query_text)

        typer.secho("  Calling AdvisingEngine ...", fg=typer.colors.YELLOW)
        t0 = time.monotonic()
        response = engine.advise(q)
        elapsed = (time.monotonic() - t0) * 1000

        if response.refusal:
            typer.secho(f"  REFUSAL: {response.refusal_reason}", fg=typer.colors.YELLOW)
        else:
            typer.secho(f"  {len(response.pathways)} pathways in {elapsed:.0f}ms", fg=typer.colors.GREEN)
            for i, pw in enumerate(response.pathways, 1):
                typer.echo(f"    [{i}] {pw.pathway_title} ({pw.confidence})")
            if response.bias_flags:
                typer.secho(f"  Bias flags: {[b.bias_type for b in response.bias_flags]}", fg=typer.colors.CYAN)

        run_gesture_fn("nod")
        machine.mark_response_delivered()

    except Exception as exc:
        typer.secho(f"  AdvisingEngine error: {exc}", fg=typer.colors.RED)
        typer.echo("  (Is Ollama running? Is ChromaDB populated?)")
        machine.mark_response_delivered()


if __name__ == "__main__":
    app()
