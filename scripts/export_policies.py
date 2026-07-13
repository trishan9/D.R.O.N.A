"""Export trained gesture policies to deployment formats (ONNX + TorchScript).

Converts every trained BC checkpoint under data/checkpoints/bc/<gesture>/ into:

    model.onnx            - opset 17, dynamic batch axis (onnxruntime, any HW)
    model.torchscript.pt  - torch.jit.trace alternative (libtorch deployments)
    export_manifest.json  - provenance: shapes, opset, file hashes, parity error

The ONNX file is what the ROS2 policy_node serves in production (via
PolicyRouter -> OnnxBCPolicy); torch is then not needed on the robot.
Each export is verified against the torch model on a sweep of gesture phases
(max |delta| must stay below --tolerance).

Usage:
    python scripts/export_policies.py                 # export all trained gestures
    python scripts/export_policies.py --gestures greet,nod
    python scripts/export_policies.py --no-verify     # skip the parity check
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import typer

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = typer.Typer(help=__doc__)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _export_one(gesture: str, ckpt_dir: Path, verify: bool, tolerance: float) -> dict:
    import torch

    from drona.interaction.bc_policy import BCGesturePolicy

    policy = BCGesturePolicy(gesture, checkpoint_dir=ckpt_dir)
    if not policy.is_trained:
        raise FileNotFoundError(f"no trained BC checkpoint for '{gesture}'")

    model = policy._model
    input_dim = policy._input_dim
    gdir = ckpt_dir / gesture
    example = torch.zeros(1, input_dim, dtype=torch.float32)

    # TorchScript (libtorch / C++ deployments)
    ts_path = gdir / "model.torchscript.pt"
    torch.jit.trace(model, example).save(str(ts_path))

    # ONNX (onnxruntime - the ROS2 inference-node format). dynamo=False pins the
    # stable TorchScript exporter: no onnxscript dependency, dynamic_axes support.
    onnx_path = gdir / "model.onnx"
    export_kwargs = dict(
        input_names=["input"], output_names=["action"],
        dynamic_axes={"input": {0: "batch"}, "action": {0: "batch"}},
        opset_version=17,
    )
    try:
        torch.onnx.export(model, example, str(onnx_path), dynamo=False, **export_kwargs)
    except TypeError:  # torch < 2.5 has no dynamo kwarg
        torch.onnx.export(model, example, str(onnx_path), **export_kwargs)

    max_err = None
    if verify:
        import onnxruntime as ort

        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        phases = np.linspace(0.0, 1.0, 21, dtype=np.float32)
        errs = []
        for ph in phases:
            x = np.zeros((1, input_dim), dtype=np.float32)
            x[0, -1] = ph  # phase is the last input in both layouts
            with torch.no_grad():
                ref = model(torch.from_numpy(x)).numpy()
            (out,) = session.run(None, {"input": x})
            errs.append(float(np.max(np.abs(ref - out))))
        max_err = max(errs)
        if max_err > tolerance:
            raise RuntimeError(f"ONNX parity check failed for '{gesture}': "
                               f"max|delta|={max_err:.2e} > {tolerance:.0e}")

    return {
        "gesture": gesture,
        "input_dim": input_dim,
        "horizon": policy._horizon,
        "onnx": {"file": onnx_path.name, "sha256": _sha256(onnx_path), "opset": 17},
        "torchscript": {"file": ts_path.name, "sha256": _sha256(ts_path)},
        "parity_max_abs_err": max_err,
    }


@app.command()
def main(
    checkpoint_dir: Path = typer.Option(
        Path("data/checkpoints/bc"), "--checkpoint-dir",
        help="BC checkpoint root (one sub-dir per gesture)"),
    gestures: str = typer.Option("all", "--gestures", help="Comma list or 'all'"),
    verify: bool = typer.Option(True, "--verify/--no-verify",
                                help="Check ONNX output parity vs torch"),
    tolerance: float = typer.Option(1e-5, "--tolerance"),
) -> None:
    from drona.interaction.bc_policy import checkpoint_exists
    from drona.interaction.demonstration import GESTURE_KEYFRAMES

    wanted = (list(GESTURE_KEYFRAMES) if gestures == "all"
              else [g.strip() for g in gestures.split(",") if g.strip()])
    trained = [g for g in wanted if checkpoint_exists(g, checkpoint_dir)]
    skipped = [g for g in wanted if g not in trained]
    if skipped:
        typer.secho(f"no trained checkpoint (skipped): {', '.join(skipped)}",
                    fg=typer.colors.YELLOW)
    if not trained:
        typer.secho("nothing to export - train first: python scripts/train_bc_gesture.py",
                    fg=typer.colors.RED)
        raise typer.Exit(1)

    entries = []
    for g in trained:
        entry = _export_one(g, checkpoint_dir, verify, tolerance)
        entries.append(entry)
        err = entry["parity_max_abs_err"]
        typer.echo(f"  {g:10s} -> model.onnx + model.torchscript.pt"
                   + (f"  (parity max|delta| {err:.1e})" if err is not None else ""))

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checkpoint_dir": str(checkpoint_dir),
        "opset": 17,
        "entries": entries,
    }
    out = checkpoint_dir / "export_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    typer.secho(f"\n{len(entries)} gesture(s) exported; manifest -> {out}",
                fg=typer.colors.GREEN, bold=True)
    typer.echo("The ROS2 policy_node now serves these ONNX models automatically "
               "(PolicyRouter prefers ONNX when onnxruntime is installed).")


if __name__ == "__main__":
    app()
