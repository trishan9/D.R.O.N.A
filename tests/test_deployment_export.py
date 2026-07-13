"""Deployment-format export path: ONNX/TorchScript export + OnnxBCPolicy + router tiers.

Covers the production inference chain the ROS2 policy_node relies on:
    scripts/export_policies.py -> model.onnx -> OnnxBCPolicy -> PolicyRouter.

All heavy deps are optional: tests skip cleanly where torch / onnx /
onnxruntime are unavailable (e.g. minimal CI), and never touch the repo's real
checkpoints - everything runs in tmp_path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from drona.interaction.act_policy import KeyframePolicy, PolicyRouter  # noqa: E402
from drona.interaction.demonstration import DOF  # noqa: E402
from drona.interaction.exported_policy import OnnxBCPolicy, onnx_exists  # noqa: E402

GESTURE = "greet"


def _make_bc_checkpoint(base: Path, gesture: str = GESTURE, input_dim: int = 1,
                        horizon: int = 12) -> Path:
    """Write a tiny trained-looking BC checkpoint into base/<gesture>/."""
    torch = pytest.importorskip("torch")
    from drona.interaction.bc_policy import _build_mlp

    gdir = base / gesture
    gdir.mkdir(parents=True, exist_ok=True)
    model = _build_mlp(input_dim, 16, DOF)
    torch.save(model.state_dict(), gdir / "pytorch_model.bin")
    (gdir / "config.json").write_text(json.dumps(
        {"hidden": 16, "horizon": horizon, "dof": DOF, "input_dim": input_dim}))
    return gdir


def _export(gesture: str, base: Path) -> dict:
    pytest.importorskip("torch")
    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from export_policies import _export_one

    return _export_one(gesture, base, verify=True, tolerance=1e-5)


# ── onnx_exists gating ─────────────────────────────────────────────────────────

def test_onnx_exists_false_without_artifacts(tmp_path):
    assert not onnx_exists(GESTURE, tmp_path)


def test_onnx_policy_requires_artifact(tmp_path):
    with pytest.raises(RuntimeError):
        OnnxBCPolicy(GESTURE, checkpoint_dir=tmp_path)


# ── export roundtrip ───────────────────────────────────────────────────────────

def test_export_writes_all_deployment_artifacts(tmp_path):
    _make_bc_checkpoint(tmp_path)
    entry = _export(GESTURE, tmp_path)

    gdir = tmp_path / GESTURE
    assert (gdir / "model.onnx").exists()
    assert (gdir / "model.torchscript.pt").exists()
    assert entry["parity_max_abs_err"] < 1e-5
    assert onnx_exists(GESTURE, tmp_path)


def test_onnx_policy_matches_torch_policy(tmp_path):
    from drona.interaction.bc_policy import BCGesturePolicy

    _make_bc_checkpoint(tmp_path, horizon=12)
    _export(GESTURE, tmp_path)

    torch_policy = BCGesturePolicy(GESTURE, checkpoint_dir=tmp_path)
    onnx_policy = OnnxBCPolicy(GESTURE, checkpoint_dir=tmp_path)
    assert torch_policy.is_trained

    obs = {"observation.state": np.zeros(DOF, dtype=np.float32)}
    torch_policy.reset()
    onnx_policy.reset()
    while not onnx_policy.is_complete:
        a_ref = torch_policy.select_action(obs)
        a_onnx = onnx_policy.select_action(obs)
        assert a_onnx.shape == (DOF,)
        np.testing.assert_allclose(a_onnx, a_ref, atol=1e-5)
    assert torch_policy.is_complete


def test_onnx_policy_closed_loop_input(tmp_path):
    """input_dim = DOF+1 (state + phase) exports and runs too."""
    _make_bc_checkpoint(tmp_path, input_dim=DOF + 1, horizon=8)
    _export(GESTURE, tmp_path)

    policy = OnnxBCPolicy(GESTURE, checkpoint_dir=tmp_path)
    action = policy.select_action({"observation.state": np.ones(DOF, dtype=np.float32)})
    assert action.shape == (DOF,) and np.isfinite(action).all()


# ── PolicyRouter tiering ───────────────────────────────────────────────────────

def test_router_prefers_onnx_export(tmp_path):
    base = tmp_path / "checkpoints"
    _make_bc_checkpoint(base / "bc")
    _export(GESTURE, base / "bc")

    policy = PolicyRouter(checkpoint_base_dir=base).get_policy(GESTURE)
    assert isinstance(policy, OnnxBCPolicy)


def test_router_falls_back_to_torch_bc_without_onnx(tmp_path):
    from drona.interaction.bc_policy import BCGesturePolicy

    base = tmp_path / "checkpoints"
    _make_bc_checkpoint(base / "bc")  # torch weights only, no export

    policy = PolicyRouter(checkpoint_base_dir=base).get_policy(GESTURE)
    assert isinstance(policy, BCGesturePolicy)
    assert policy.is_trained


def test_router_keyframe_when_nothing_trained(tmp_path):
    policy = PolicyRouter(checkpoint_base_dir=tmp_path).get_policy(GESTURE)
    assert isinstance(policy, KeyframePolicy)
