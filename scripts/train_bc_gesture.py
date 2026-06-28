"""Train phase-conditioned behavior-cloning gesture policies on CPU - C3 baseline.

This is the *runs-anywhere* training path for the demonstration-learned
interaction contribution. It needs no GPU and no LeRobot: it trains one small
MLP per gesture (input = joint_state + gesture_phase, output = target joints) on
the keyframe demonstration dataset produced by ``collect_demonstrations.py``,
saves a checkpoint per gesture, and evaluates the trained policies against the
keyframe baseline with the project's own ``sim_eval`` harness.

The production ACT / Diffusion policies (LeRobot, notebooks 07/08) are the GPU
upgrade; this BC policy is the local baseline that proves the imitation loop
end-to-end on the student's hardware.

Usage:
    python scripts/collect_demonstrations.py --episodes 25      # make data first
    python scripts/train_bc_gesture.py
    python scripts/train_bc_gesture.py --epochs 400 --gestures greet,nod,farewell
    python scripts/train_bc_gesture.py --help
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import typer

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.interaction.bc_policy import (  # noqa: E402
    DEFAULT_BC_DIR,
    DEFAULT_HIDDEN,
    BCGesturePolicy,
    _build_mlp,
)
from drona.interaction.demonstration import (  # noqa: E402
    DOF,
    GESTURE_KEYFRAMES,
    DemonstrationDataset,
)
from drona.utils.logging import setup_logging  # noqa: E402
from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(name="train-bc", help="Train CPU behavior-cloning gesture policies.")


def _gesture_samples(dataset: DemonstrationDataset, gesture: str, closed_loop: bool = False):
    """Build (X, Y=action) arrays + mean horizon for a gesture.

    open-loop  (default): X = [phase]            - a learned movement primitive
    closed-loop          : X = [joint_state, phase]
    """
    xs, ys, lengths = [], [], []
    for ep in dataset.episodes:
        if ep.gesture_label != gesture:
            continue
        frames = ep.frames
        n = len(frames)
        if n < 2:
            continue
        lengths.append(n)
        for i, fr in enumerate(frames):
            phase = i / (n - 1)
            x = (np.concatenate([fr.observation_state[:DOF], [phase]])
                 if closed_loop else np.array([phase], dtype=np.float32))
            xs.append(x)
            ys.append(fr.action[:DOF])
    if not xs:
        return None, None, 0
    horizon = int(round(float(np.mean(lengths))))
    return (
        np.asarray(xs, dtype=np.float32),
        np.asarray(ys, dtype=np.float32),
        horizon,
    )


def _train_one(
    gesture: str,
    feats: np.ndarray,
    acts: np.ndarray,
    horizon: int,
    out_dir: Path,
    *,
    epochs: int,
    hidden: int,
    lr: float,
    batch_size: int,
    val_frac: float,
    seed: int,
) -> dict:
    import torch
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    # train / val split
    idx = rng.permutation(len(feats))
    n_val = max(1, int(len(feats) * val_frac))
    val_idx, tr_idx = idx[:n_val], idx[n_val:]
    x_tr, y_tr = torch.from_numpy(feats[tr_idx]), torch.from_numpy(acts[tr_idx])
    x_val, y_val = torch.from_numpy(feats[val_idx]), torch.from_numpy(acts[val_idx])

    input_dim = feats.shape[1]
    model = _build_mlp(input_dim, hidden, DOF)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = torch.nn.MSELoss()
    loader = DataLoader(TensorDataset(x_tr, y_tr), batch_size=batch_size, shuffle=True)

    best_val = float("inf")
    first_val = None
    for epoch in range(1, epochs + 1):
        model.train()
        for xb, yb in loader:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        if epoch % max(1, epochs // 5) == 0 or epoch == 1 or epoch == epochs:
            model.eval()
            with torch.no_grad():
                vloss = loss_fn(model(x_val), y_val).item()
                tloss = loss_fn(model(x_tr), y_tr).item()
            first_val = first_val if first_val is not None else vloss
            best_val = min(best_val, vloss)
            typer.echo(f"    epoch {epoch:4d}/{epochs}  train_mse={tloss:.5f}  val_mse={vloss:.5f}")

    # save checkpoint
    ckpt = out_dir / gesture
    ckpt.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), ckpt / "pytorch_model.bin")
    (ckpt / "config.json").write_text(
        json.dumps(
            {"model_type": "bc_mlp", "dof": DOF, "hidden": hidden,
             "horizon": horizon, "input_dim": input_dim, "epochs": epochs},
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "gesture": gesture,
        "samples": int(len(feats)),
        "horizon": horizon,
        "first_val_mse": round(float(first_val), 6) if first_val is not None else None,
        "best_val_mse": round(float(best_val), 6),
    }


@app.command()
def main(
    demo_dir: Optional[str] = typer.Option(None, "--demo-dir", help="Demonstrations dir"),
    checkpoint_dir: str = typer.Option(DEFAULT_BC_DIR, "--checkpoint-dir"),
    gestures: str = typer.Option("all", "--gestures", help="Comma list or 'all'"),
    epochs: int = typer.Option(300, "--epochs", "-e"),
    hidden: int = typer.Option(DEFAULT_HIDDEN, "--hidden"),
    lr: float = typer.Option(2e-3, "--lr"),
    batch_size: int = typer.Option(64, "--batch-size", "-b"),
    val_frac: float = typer.Option(0.15, "--val-frac"),
    seed: int = typer.Option(0, "--seed"),
    closed_loop: bool = typer.Option(
        False, "--closed-loop/--open-loop",
        help="Closed-loop conditions on joint state + phase; open-loop (default) "
             "is a phase-indexed movement primitive that reaches the apex reliably."),
    evaluate: bool = typer.Option(True, "--evaluate/--no-evaluate", help="Sim-eval vs keyframe"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    setup_logging(level=log_level, log_file=settings.log_file)

    demo_path = Path(demo_dir) if demo_dir else settings.data_dir / "demonstrations"
    jsonl = demo_path / "demonstrations.jsonl"
    if not jsonl.exists():
        typer.secho(
            f"\nDemonstrations not found: {jsonl}\n"
            "Run first:  python scripts/collect_demonstrations.py\n",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    dataset = DemonstrationDataset.load_jsonl(jsonl)
    typer.echo(f"Loaded {dataset.total_frames} frames / {len(dataset.episodes)} episodes")

    gesture_list = (
        list(GESTURE_KEYFRAMES.keys())
        if gestures.strip().lower() == "all"
        else [g.strip() for g in gestures.split(",")]
    )
    out_dir = Path(checkpoint_dir)

    typer.secho("\nBehavior-cloning training (CPU)", bold=True)
    typer.echo("─" * 60)
    typer.echo(f"mode: {'closed-loop (state+phase)' if closed_loop else 'open-loop (phase primitive)'}")
    results = []
    for g in gesture_list:
        feats, acts, horizon = _gesture_samples(dataset, g, closed_loop=closed_loop)
        if feats is None:
            typer.secho(f"[{g}] no demonstrations - skipping", fg=typer.colors.YELLOW)
            continue
        typer.secho(f"\n[{g}]  {len(feats)} samples, horizon≈{horizon}", bold=True)
        stats = _train_one(
            g, feats, acts, horizon, out_dir,
            epochs=epochs, hidden=hidden, lr=lr,
            batch_size=batch_size, val_frac=val_frac, seed=seed,
        )
        results.append(stats)

    # ── Summary + report ─────────────────────────────────────────────────────
    typer.secho("\n\nTraining summary", bold=True)
    typer.echo("─" * 60)
    for r in results:
        typer.echo(
            f"  {r['gesture']:<10} samples={r['samples']:<5} "
            f"val_mse {r['first_val_mse']} → {r['best_val_mse']}"
        )

    report = {"policy": "bc_mlp", "checkpoint_dir": str(out_dir), "gestures": results}

    # ── Evaluation against the keyframe baseline ─────────────────────────────
    if evaluate:
        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.sim_eval import compare_policies

        trained = [r["gesture"] for r in results]
        typer.secho("\nSim-eval: keyframe baseline vs trained BC policy", bold=True)
        cmp = compare_policies(
            base_factory=lambda g: KeyframePolicy(g),
            other_factory=lambda g: BCGesturePolicy(g, checkpoint_dir=out_dir),
            gestures=trained,
        )
        base, other, delta = cmp["base"], cmp["other"], cmp["delta"]
        typer.echo(
            f"  keyframe : success={base['success_rate']:.0%}  "
            f"mean_jerk={base['mean_jerk']:.4f}"
        )
        typer.echo(
            f"  BC (learned): success={other['success_rate']:.0%}  "
            f"mean_jerk={other['mean_jerk']:.4f}"
        )
        typer.echo(f"  Δ success={delta['success_rate']:+.0%}  Δ jerk={delta['mean_jerk']:+.4f}")
        report["sim_eval"] = cmp

    report_path = out_dir / "bc_training_report.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    typer.secho(f"\nReport → {report_path}", fg=typer.colors.CYAN)
    typer.secho("Checkpoints ready. The PolicyRouter/web-twin can load these per gesture.",
                fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
