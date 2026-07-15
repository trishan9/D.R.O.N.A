"""
SmolVLA inference seam for D.R.O.N.A. (Vision-Language-Action).

SmolVLA (HuggingFace LeRobot) is a small pre-trained VLA that maps a language
instruction + visual/state observation to robot actions. We integrate it as a
FORWARD-LOOKING architectural seam (the proposal explicitly does NOT train a VLA
from scratch): the same gesture can be requested by natural language
("greet the student", "point to the screen") and dispatched to a VLA policy.

Design:
  - Uses the SAME `BasePolicy` interface as ACT/Diffusion/Keyframe, so the
    gesture dispatcher and sim-eval harness treat it uniformly.
  - Lazy-imports the pre-trained SmolVLA; if LeRobot/weights are unavailable it
    falls back to the KeyframePolicy for the gesture inferred from the
    instruction. This keeps the system runnable today while leaving a clean
    upgrade path to a real VLA on the robot in Phase 2.

We map free-text instructions to one of our gesture labels via keyword rules
(transparent, falsifiable - same philosophy as the bias detector).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from loguru import logger

from drona.interaction.act_policy import BasePolicy, KeyframePolicy
from drona.interaction.demonstration import GESTURE_KEYFRAMES, clamp_joints

# Instruction → gesture keyword map (first match wins).
_INSTRUCTION_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("greet", ("greet", "hello", "hi", "welcome", "wave")),
    ("farewell", ("farewell", "goodbye", "bye", "see you")),
    ("nod", ("nod", "agree", "yes", "acknowledge")),
    ("point", ("point", "show", "indicate", "look at", "screen")),
    ("listen", ("listen", "attention", "go ahead", "tell me")),
    ("idle", ("idle", "wait", "rest", "stand by")),
]

DEFAULT_PRETRAINED = "lerobot/smolvla_base"


def instruction_to_gesture(instruction: str) -> str:
    """Map a free-text instruction to a known gesture label (default 'idle')."""
    text = instruction.lower()
    for gesture, keywords in _INSTRUCTION_KEYWORDS:
        if any(k in text for k in keywords):
            return gesture
    return "idle"


class SmolVLAPolicy(BasePolicy):
    """Pre-trained SmolVLA policy (lazy), with keyframe fallback.

    Args:
        instruction: Natural-language command (e.g. "greet the student").
        pretrained: HF repo id of the pre-trained SmolVLA checkpoint.
        device: torch device.
        allow_fallback: If True (default), fall back to KeyframePolicy when the
            VLA can't be loaded, so the system stays functional.
    """

    def __init__(
        self,
        instruction: str,
        pretrained: str = DEFAULT_PRETRAINED,
        device: str = "cpu",
        allow_fallback: bool = True,
    ) -> None:
        self._instruction = instruction
        self._gesture = instruction_to_gesture(instruction)
        self._pretrained = pretrained
        self._device = device
        self._policy: Any = None
        self._fallback: KeyframePolicy | None = None
        self._load(allow_fallback)

    def _load(self, allow_fallback: bool) -> None:
        try:
            import torch  # noqa: F401
            try:  # newer lerobot dropped `common`; support both layouts
                from lerobot.policies.smolvla.modeling_smolvla import (  # type: ignore[import]
                    SmolVLAPolicy as _SmolVLA,
                )
            except ImportError:
                from lerobot.common.policies.smolvla.modeling_smolvla import (  # type: ignore[import]
                    SmolVLAPolicy as _SmolVLA,
                )

            logger.info(f"Loading pre-trained SmolVLA '{self._pretrained}' on {self._device}")
            self._policy = _SmolVLA.from_pretrained(self._pretrained)
            self._policy.eval()
            if hasattr(self._policy, "to"):
                self._policy.to(self._device)
        except Exception as exc:
            if not allow_fallback:
                raise RuntimeError(f"SmolVLA unavailable: {exc}") from exc
            logger.warning(
                f"SmolVLA unavailable ({exc}); falling back to KeyframePolicy "
                f"for inferred gesture '{self._gesture}'"
            )
            self._fallback = KeyframePolicy(self._gesture)

    @property
    def using_fallback(self) -> bool:
        return self._fallback is not None

    @property
    def gesture(self) -> str:
        return self._gesture

    def reset(self) -> None:
        if self._fallback is not None:
            self._fallback.reset()
        elif self._policy is not None and hasattr(self._policy, "reset"):
            self._policy.reset()

    def select_action(self, obs_dict: dict[str, Any]) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.select_action(obs_dict)

        import torch

        state = np.asarray(obs_dict["observation.state"], dtype=np.float32)
        batch = {
            "observation.state": torch.tensor(state, dtype=torch.float32).unsqueeze(0),
            "task": [self._instruction],
        }
        # SmolVLA expects an image; sim gestures are state-only, so callers that
        # have a camera should add "observation.image". We pass through whatever
        # is provided in obs_dict.
        if "observation.image" in obs_dict:
            batch["observation.image"] = obs_dict["observation.image"]
        with torch.no_grad():
            action = self._policy.select_action(batch)
        arr = action.squeeze(0).cpu().numpy() if isinstance(action, torch.Tensor) else np.array(action)
        if arr.ndim > 1:
            arr = arr[0]
        return clamp_joints(arr.astype(np.float32))

    @property
    def name(self) -> str:
        if self._fallback is not None:
            return f"SmolVLA-fallback({self._gesture})"
        return f"SmolVLA('{self._instruction}'->{self._gesture})"


def available_gestures() -> list[str]:
    """Gesture labels SmolVLA instructions can resolve to."""
    return list(GESTURE_KEYFRAMES.keys())
