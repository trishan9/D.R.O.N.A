"""
Student engagement detector for D.R.O.N.A.

Classifies a student's engagement state from a video frame:
  ABSENT       - no person detected
  PASSING_BY   - person detected but transient (low confidence or far away)
  APPROACHING  - person getting closer, not yet engaged
  ENGAGED      - stable face detection, person is attending to the robot
  DISENGAGING  - was engaged, now moving away or looking elsewhere

Two backends with the same BaseDetector interface:

  MediaPipeDetector (optional)
    Uses the MediaPipe Tasks API (vision.FaceDetector, BlazeFace short-range).
    Requires (numpy<2 is mandatory - see requirements-perception.txt):
      pip install 'numpy<2' 'mediapipe>=0.10.9' 'opencv-contrib-python<5'
    Face bounding box area → estimated distance proxy.
    Detection confidence + temporal stability → engagement classification.

  StubDetector (always available)
    Returns a controlled sequence of StudentDetection objects from a script.
    Used in unit tests and in environments without a camera or MediaPipe.
    The script can simulate a full session: ABSENT → APPROACHING → ENGAGED →
    ADVISING → DISENGAGING → ABSENT.

Temporal smoothing:
  Raw detections are noisy. Both backends apply an exponential moving average
  on the detection confidence and a debounce count on state transitions so
  the orchestrator sees stable states, not flickering ones.

Hardware note (GTX 1650):
  MediaPipe Face Detection runs on CPU at ~5ms/frame. With a 640×480 webcam
  at 30fps, this leaves ~28ms headroom per frame - plenty for the advising
  pipeline at its 200ms+ latency.
"""

from __future__ import annotations

import os
import time
import urllib.request
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

import numpy as np
from loguru import logger

from drona.contracts import EngagementState, StudentDetection

# BlazeFace short-range (<2m) face detector for the MediaPipe Tasks API. Modern
# mediapipe (>=0.10.18) removed the legacy mp.solutions API, so the Tasks API is
# the only supported path; it needs this small (~230 KB) model on disk.
_FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
)


def _ensure_face_model() -> Path:
    """Return a local path to the BlazeFace model, downloading it once if needed.

    Cache dir is overridable with DRONA_FACE_MODEL_DIR so an offline robot (e.g.
    a Raspberry Pi with no internet at boot) can ship the model alongside the code.
    """
    cache = Path(os.environ.get("DRONA_FACE_MODEL_DIR",
                                str(Path.home() / ".cache" / "drona")))
    cache.mkdir(parents=True, exist_ok=True)
    model = cache / "blaze_face_short_range.tflite"
    if not model.exists():
        logger.info(f"Downloading BlazeFace model -> {model}")
        urllib.request.urlretrieve(_FACE_MODEL_URL, model)
    return model

# ── Thresholds ────────────────────────────────────────────────────────────────

_ENGAGED_CONFIDENCE_MIN = 0.70
_PASSING_CONFIDENCE_MIN = 0.30
_LARGE_FACE_FRAC = 0.10   # face area / frame area → "close" (< 1.5m away)
_SMALL_FACE_FRAC = 0.02   # face area / frame area → "far" (> 3m away)
_DEBOUNCE_FRAMES = 3       # consecutive frames required before state change
_EMA_ALPHA = 0.4           # exponential moving average weight for confidence


def _classify_engagement(
    confidence: float,
    face_area_frac: float,
    consecutive_detections: int,
) -> tuple[EngagementState, float | None]:
    """Map detection signals to an EngagementState.

    Returns (state, estimated_distance_m).
    distance_m is a rough proxy: 1/sqrt(face_area_frac), calibrated heuristically.
    """
    if confidence < _PASSING_CONFIDENCE_MIN:
        return EngagementState.ABSENT, None

    # Estimate distance from face size (rough inverse-square law approximation)
    if face_area_frac > 0:
        distance_m: float | None = float(0.15 / (face_area_frac ** 0.5))
    else:
        distance_m = None

    if confidence < _ENGAGED_CONFIDENCE_MIN:
        return EngagementState.PASSING_BY, distance_m

    if face_area_frac < _SMALL_FACE_FRAC:
        return EngagementState.APPROACHING, distance_m

    if consecutive_detections >= _DEBOUNCE_FRAMES:
        return EngagementState.ENGAGED, distance_m

    return EngagementState.APPROACHING, distance_m


# ── Base interface ─────────────────────────────────────────────────────────────

class BaseDetector(ABC):
    """Shared interface for all student detectors."""

    @abstractmethod
    def detect(self, frame: np.ndarray | None = None) -> StudentDetection:
        """Process one frame and return a StudentDetection.

        Args:
            frame: RGB image array (H, W, 3) or None for stub detectors.

        Returns:
            StudentDetection with current engagement state.
        """

    @abstractmethod
    def close(self) -> None:
        """Release resources (camera, model)."""

    def stream(
        self,
        interval_s: float = 0.1,
        max_frames: int | None = None,
    ) -> Iterator[StudentDetection]:
        """Continuously yield StudentDetection at the given interval.

        For MediaPipeDetector, this reads from the webcam.
        For StubDetector, this advances through the scripted sequence.

        Args:
            interval_s: Seconds to wait between detections.
            max_frames: Stop after this many detections (None = run forever).
        """
        count = 0
        while max_frames is None or count < max_frames:
            yield self.detect()
            time.sleep(interval_s)
            count += 1


# ── MediaPipe backend ──────────────────────────────────────────────────────────

class MediaPipeDetector(BaseDetector):
    """Face-detection-based engagement classifier using MediaPipe.

    Reads from a webcam by default (camera_index=0).
    The webcam capture is lazy - it opens on first detect() call.
    """

    def __init__(self, camera_index: int = 0, min_confidence: float = 0.5,
                 open_camera: bool = True) -> None:
        self._camera_index = camera_index
        self._min_confidence = min_confidence
        self._open_camera = open_camera  # False = frames injected via detect(frame=...)
        self._cap = None          # cv2.VideoCapture, lazy
        self._detector = None     # mp face_detection, lazy
        self._ema_conf = 0.0
        self._consecutive = 0
        self._last_state = EngagementState.ABSENT

    def _ensure_init(self) -> None:
        if self._detector is not None:
            return
        try:
            import cv2  # type: ignore[import]
            import mediapipe as mp  # type: ignore[import]
            from mediapipe.tasks import python as mp_python  # type: ignore[import]
            from mediapipe.tasks.python import vision as mp_vision  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "MediaPipe and OpenCV are required: "
                "pip install 'numpy<2' 'mediapipe>=0.10.9' 'opencv-contrib-python<5'"
            ) from exc

        # Tasks API FaceDetector (the modern replacement for mp.solutions).
        options = mp_vision.FaceDetectorOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=str(_ensure_face_model())
            ),
            running_mode=mp_vision.RunningMode.IMAGE,
            min_detection_confidence=self._min_confidence,
        )
        self._detector = mp_vision.FaceDetector.create_from_options(options)
        self._mp = mp
        if self._open_camera:
            self._cap = cv2.VideoCapture(self._camera_index)
            if not self._cap.isOpened():
                raise RuntimeError(f"Could not open camera {self._camera_index}")
        logger.info(
            "MediaPipeDetector ready (Tasks API) "
            + (f"(camera {self._camera_index})" if self._open_camera else "(injected frames)")
        )

    def detect(self, frame: np.ndarray | None = None) -> StudentDetection:
        self._ensure_init()
        import cv2  # type: ignore[import]

        if frame is None:
            if self._cap is None:  # injected-frame mode with no frame yet
                return self._make_detection(EngagementState.ABSENT, None, 0.0)
            ret, frame = self._cap.read()
            if not ret or frame is None:
                return self._make_detection(EngagementState.ABSENT, None, 0.0)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w = frame.shape[:2]
        # Tasks API takes an mp.Image (SRGB, contiguous uint8).
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(frame, dtype=np.uint8),
        )
        results = self._detector.detect(mp_image)

        if not results.detections:
            self._ema_conf = self._ema_conf * (1 - _EMA_ALPHA)
            self._consecutive = 0
            return self._make_detection(EngagementState.ABSENT, None, self._ema_conf)

        # Use the highest-confidence detection
        best = max(results.detections, key=lambda d: d.categories[0].score)
        raw_conf = float(best.categories[0].score)
        self._ema_conf = _EMA_ALPHA * raw_conf + (1 - _EMA_ALPHA) * self._ema_conf
        self._consecutive += 1

        # Tasks API bounding_box is in PIXELS; normalise to a frame-area fraction
        # so the engagement thresholds (_LARGE_FACE_FRAC etc.) stay resolution-independent.
        bb = best.bounding_box
        area_frac = float(bb.width * bb.height) / float(max(1, w * h))

        state, distance_m = _classify_engagement(
            self._ema_conf, area_frac, self._consecutive
        )
        return self._make_detection(state, distance_m, self._ema_conf)

    def _make_detection(
        self,
        state: EngagementState,
        distance_m: float | None,
        confidence: float,
    ) -> StudentDetection:
        return StudentDetection(
            detection_id=str(uuid.uuid4()),
            engagement=state,
            estimated_distance_m=distance_m,
            gaze_on_robot=None,
            confidence=max(0.0, min(1.0, confidence)),
        )

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        if self._detector is not None:
            self._detector.close()
        logger.info("MediaPipeDetector closed")


# ── Stub backend (always available) ───────────────────────────────────────────

class StubDetector(BaseDetector):
    """Scripted detector that replays a predefined sequence of detections.

    Designed for unit tests and demonstrations without a camera.
    The script is a list of (EngagementState, confidence, distance_m) tuples.
    Once exhausted, the last entry is repeated.
    """

    def __init__(
        self,
        script: list[tuple[EngagementState, float, float | None]] | None = None,
    ) -> None:
        if script is None:
            script = _default_session_script()
        self._script = script
        self._idx = 0

    def detect(self, frame: np.ndarray | None = None) -> StudentDetection:
        entry = self._script[min(self._idx, len(self._script) - 1)]
        self._idx += 1
        state, conf, dist = entry
        return StudentDetection(
            detection_id=str(uuid.uuid4()),
            engagement=state,
            estimated_distance_m=dist,
            gaze_on_robot=(state == EngagementState.ENGAGED),
            confidence=conf,
        )

    def reset(self) -> None:
        self._idx = 0

    @property
    def exhausted(self) -> bool:
        return self._idx >= len(self._script)

    def close(self) -> None:
        pass


def _default_session_script() -> list[tuple[EngagementState, float, float | None]]:
    """A scripted session: absent → approaching → engaged × 5 → disengaging → absent."""
    return [
        (EngagementState.ABSENT,      0.0,  None),
        (EngagementState.ABSENT,      0.0,  None),
        (EngagementState.PASSING_BY,  0.45, 4.0),
        (EngagementState.APPROACHING, 0.65, 2.5),
        (EngagementState.APPROACHING, 0.72, 2.0),
        (EngagementState.ENGAGED,     0.88, 1.2),
        (EngagementState.ENGAGED,     0.91, 1.1),
        (EngagementState.ENGAGED,     0.89, 1.2),
        (EngagementState.ENGAGED,     0.90, 1.1),
        (EngagementState.ENGAGED,     0.87, 1.3),
        (EngagementState.DISENGAGING, 0.55, 2.0),
        (EngagementState.ABSENT,      0.0,  None),
    ]


# ── Factory ────────────────────────────────────────────────────────────────────

def make_detector(
    prefer_mediapipe: bool = True,
    camera_index: int = 0,
    stub_script: list[tuple[EngagementState, float, float | None]] | None = None,
    open_camera: bool = True,
) -> BaseDetector:
    """Create a detector, preferring MediaPipe if available.

    Args:
        prefer_mediapipe: Try MediaPipe/webcam first; fall back to StubDetector.
        camera_index: Webcam device index (MediaPipe only).
        stub_script: Custom detection sequence (StubDetector only).
        open_camera: False = no local webcam; frames are injected via
            detect(frame=...) (used by the ROS2 perception node in image-topic
            mode, where the camera lives in the simulator or on another node).

    Returns:
        A BaseDetector instance.
    """
    if prefer_mediapipe:
        try:
            det = MediaPipeDetector(camera_index=camera_index, open_camera=open_camera)
            det._ensure_init()
            return det
        except (RuntimeError, ImportError) as exc:
            logger.info(f"MediaPipe unavailable ({exc}) - using StubDetector")
    return StubDetector(script=stub_script)
