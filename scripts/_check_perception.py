"""Verify the perception stack: MediaPipe detector initializes + processes a
frame, and the stub detector produces the scripted engagement sequence the
orchestrator loop relies on."""
import numpy as np

print("== MediaPipe detector ==")
try:
    from drona.perception.mediapipe_detector import make_detector
    det = make_detector(prefer_mediapipe=True, open_camera=False)
    print(f"  backend: {type(det).__name__}")
    # feed a blank frame (no face) - should run without error and report ABSENT-ish
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    d = det.detect(frame=frame)
    print(f"  blank-frame detection: state={d.engagement.name} conf={d.confidence:.2f}")
    print("  OK: MediaPipe detector runs on a frame")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"  FAIL: {e}")

print("== Stub detector (drives the sim loop) ==")
try:
    from drona.perception.mediapipe_detector import make_detector
    stub = make_detector(prefer_mediapipe=False, open_camera=False)
    states = [stub.detect().engagement.name for _ in range(6)]
    print(f"  backend: {type(stub).__name__}")
    print(f"  scripted sequence: {states}")
    assert any(s == "ENGAGED" for s in states), "stub should reach ENGAGED"
    print("  OK: stub reaches ENGAGED (loop can trigger a greeting)")
except Exception as e:
    import traceback; traceback.print_exc()
    print(f"  FAIL: {e}")
