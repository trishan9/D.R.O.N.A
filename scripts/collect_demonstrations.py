"""
Demonstration data collection script for D.R.O.N.A. ACT training.

Generates a bootstrap demonstration dataset from the pre-programmed keyframe
trajectories. In production, this script would be replaced (or supplemented)
by teleoperation recording - but for initial ACT training, keyframe-derived
demonstrations provide a reasonable starting point.

Usage:
    python scripts/collect_demonstrations.py
    python scripts/collect_demonstrations.py --episodes 20 --out-dir data/demonstrations
    python scripts/collect_demonstrations.py --gestures greet,nod,farewell
"""

from __future__ import annotations

from pathlib import Path

import typer

from drona.interaction.demonstration import (
    GESTURE_KEYFRAMES,
    DemonstrationDataset,
    record_keyframe_episode,
)
from drona.utils.logging import setup_logging
from drona.utils.settings import settings

app = typer.Typer(name="collect-demonstrations", help="Generate ACT training demonstrations.")


@app.command()
def main(
    episodes: int = typer.Option(10, "--episodes", "-n", help="Episodes per gesture."),
    out_dir: str | None = typer.Option(
        None, "--out-dir", help="Output directory for demonstration data."
    ),
    gestures: str = typer.Option(
        "all", "--gestures", help="Comma-separated gesture names, or 'all'."
    ),
    dt: float = typer.Option(0.05, "--dt", help="Timestep between frames (seconds)."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    setup_logging(log_level)
    settings.ensure_dirs()

    dest = Path(out_dir) if out_dir else settings.data_dir / "demonstrations"
    dest.mkdir(parents=True, exist_ok=True)

    gesture_list = (
        list(GESTURE_KEYFRAMES.keys())
        if gestures.strip().lower() == "all"
        else [g.strip() for g in gestures.split(",")]
    )

    unknown = [g for g in gesture_list if g not in GESTURE_KEYFRAMES]
    if unknown:
        typer.secho(
            f"Unknown gestures: {unknown}. Known: {list(GESTURE_KEYFRAMES)}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    dataset = DemonstrationDataset(name="drona_gestures_bootstrap")
    episode_counter = 0

    for gesture_label in gesture_list:
        typer.echo(f"Recording {episodes} episodes for gesture: {gesture_label}")
        for _ in range(episodes):
            episode = record_keyframe_episode(
                gesture_label=gesture_label,
                episode_index=episode_counter,
                dt=dt,
            )
            dataset.add_episode(episode)
            episode_counter += 1
        typer.echo(f"  → {episodes} episodes recorded ({episode.n_frames} frames each)")

    # Save JSONL (always)
    jsonl_path = dest / "demonstrations.jsonl"
    dataset.save_jsonl(jsonl_path)

    # Save HuggingFace format (if available)
    hf_path = dest / "hf_dataset"
    hf_saved = dataset.save_hf(hf_path)

    typer.secho("\nDemonstration dataset summary:", bold=True)
    typer.echo(f"  Total episodes : {len(dataset.episodes)}")
    typer.echo(f"  Total frames   : {dataset.total_frames}")
    typer.echo(f"  Gestures       : {dataset.gesture_counts}")
    typer.echo(f"  JSONL output   : {jsonl_path}")
    if hf_saved:
        typer.echo(f"  HF dataset     : {hf_path}")
    typer.secho("\nRun ACT training with: python scripts/train_act.py", fg=typer.colors.CYAN)


if __name__ == "__main__":
    app()
