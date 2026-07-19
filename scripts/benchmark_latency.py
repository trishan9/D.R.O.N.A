#!/usr/bin/env python3
"""
Measure D.R.O.N.A.'s end-to-end reaction latency in simulation.

Produces the quantitative numbers a distributed-robotics thesis needs: how long
the robot takes to notice a student and start responding, decomposed per tier so
the edge/robot/cloud split can be argued from data rather than assertion.

Measured (all in the running sim; assumes drona_gazebo.launch.py is up):

  perception -> decision : /drona/engagement published -> /drona/gesture_command
                           (orchestrator session machine + dispatch)
  decision -> motion     : /drona/gesture_command -> first /drona/joint_states
                           (gesture policy inference + first setpoint)
  motion -> actuation    : /drona/joint_states -> gz joint actually moves
                           (relay + ros_gz bridge + physics)
  perception -> actuation: the full observable reaction time

Reports mean / p50 / p95 over N trials and writes reports/latency_sim.json.

    python3 scripts/benchmark_latency.py [trials]
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from drona_msgs.msg import EngagementDetection, GestureCommand

GZ_STATE = "/world/drona_advising/model/drona_humanoid/joint_state"
_MOVE_EPS = 0.02  # rad - joint deviation that counts as "the arm actually moved"


class LatencyProbe(Node):
    def __init__(self) -> None:
        super().__init__("drona_latency_probe")
        self._eng = self.create_publisher(EngagementDetection, "/drona/engagement", 10)
        self.create_subscription(GestureCommand, "/drona/gesture_command", self._on_cmd, 10)
        self.create_subscription(JointState, "/drona/joint_states", self._on_js, 10)
        self.create_subscription(JointState, GZ_STATE, self._on_gz, 10)
        self.reset_trial()
        self._gz_rest: np.ndarray | None = None

    def reset_trial(self) -> None:
        self.t_engage = None
        self.t_cmd = None
        self.t_js = None
        self.t_move = None

    def _on_cmd(self, _msg: GestureCommand) -> None:
        if self.t_engage is not None and self.t_cmd is None:
            self.t_cmd = time.perf_counter()

    def _on_js(self, _msg: JointState) -> None:
        if self.t_cmd is not None and self.t_js is None:
            self.t_js = time.perf_counter()

    def _on_gz(self, msg: JointState) -> None:
        if not msg.position:
            return
        arr = np.asarray(msg.position, dtype=float)
        self.gz_last = arr
        if self._gz_rest is None:
            self._gz_rest = arr.copy()
            return
        if self.t_js is not None and self.t_move is None:
            if float(np.max(np.abs(arr - self._gz_rest))) > _MOVE_EPS:
                self.t_move = time.perf_counter()

    def arm_deviation(self) -> float:
        """Current joint deviation from the captured rest baseline (rad)."""
        if getattr(self, "gz_last", None) is None or self._gz_rest is None:
            return 0.0
        return float(np.max(np.abs(self.gz_last - self._gz_rest)))

    def publish_engagement(self, state: str, distance: float = 0.9) -> None:
        m = EngagementDetection()
        m.stamp = self.get_clock().now().to_msg()
        m.state = state          # lowercase enum VALUES travel on the wire
        m.confidence = 0.93
        m.distance_m = distance
        self._eng.publish(m)


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]


def main() -> int:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rclpy.init()
    n = LatencyProbe()

    def spin(sec: float) -> None:
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(n, timeout_sec=0.01)

    # settle: let the gz baseline joint state arrive
    spin(3.0)

    def reset_session() -> None:
        """Hold ABSENT past the orchestrator's session timeout so it returns to
        IDLE, then wait for the arm to physically settle back at rest. Without
        the settle the next trial baselines a still-moving arm and the actuation
        timestamp is meaningless."""
        reset_s = float(os.environ.get("DRONA_SESSION_TIMEOUT_S", "8")) + 3.0
        t_end = time.time() + reset_s
        while time.time() < t_end:
            n.publish_engagement("absent", 0.0)
            spin(0.1)
        # wait (bounded) for the arm to stop moving
        n._gz_rest = None
        spin(0.3)
        still_since = time.time()
        limit = time.time() + 6.0
        while time.time() < limit:
            spin(0.2)
            if n.arm_deviation() > _MOVE_EPS:
                n._gz_rest = None          # re-baseline; still moving
                spin(0.2)
                still_since = time.time()
            elif time.time() - still_since > 1.0:
                break                       # stable for 1 s -> at rest

    def run_trial() -> dict | None:
        n.reset_trial()
        n.t_engage = time.perf_counter()
        deadline = time.time() + 12.0
        while time.time() < deadline and n.t_move is None:
            n.publish_engagement("engaged", 0.9)
            spin(0.1)
        if n.t_cmd is None:
            return None
        return {
            "perception_to_decision_ms": (n.t_cmd - n.t_engage) * 1e3,
            "decision_to_motion_ms": ((n.t_js - n.t_cmd) * 1e3) if n.t_js else None,
            "motion_to_actuation_ms": ((n.t_move - n.t_js) * 1e3) if (n.t_move and n.t_js) else None,
            "perception_to_actuation_ms": ((n.t_move - n.t_engage) * 1e3) if n.t_move else None,
        }

    # Warm-up (not recorded): the first gesture pays a one-time lazy load of the
    # GestureDispatcher/policy (~1.8 s measured), which would otherwise dominate
    # the statistics and misrepresent steady-state reaction time.
    print("  warm-up trial (loads the gesture policy; not recorded) ...")
    reset_session()
    w = run_trial()
    if w:
        print(f"  warm-up: perception_to_actuation="
              f"{(w.get('perception_to_actuation_ms') or 0):.0f}ms (cold-start cost)")

    rows: list[dict] = []
    for i in range(trials):
        reset_session()
        row = run_trial()
        if row is None:
            print(f"  trial {i+1}: no gesture command (skipped)")
            continue
        rows.append(row)
        print(f"  trial {i+1}: "
              + "  ".join(f"{k.replace('_ms','')}={v:.0f}ms"
                          for k, v in row.items() if v is not None))

    n.destroy_node()
    rclpy.shutdown()

    if not rows:
        print("FAIL: no successful trials")
        return 1

    print("\n" + "=" * 72)
    print("D.R.O.N.A. reaction latency in simulation")
    print("=" * 72)
    summary: dict[str, dict] = {}
    for key in ("perception_to_decision_ms", "decision_to_motion_ms",
                "motion_to_actuation_ms", "perception_to_actuation_ms"):
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            continue
        summary[key] = {
            "n": len(vals),
            "mean_ms": round(statistics.fmean(vals), 1),
            "p50_ms": round(_pct(vals, 50), 1),
            "p95_ms": round(_pct(vals, 95), 1),
        }
        s = summary[key]
        print(f"  {key.replace('_ms',''):26} mean={s['mean_ms']:8.1f}  "
              f"p50={s['p50_ms']:8.1f}  p95={s['p95_ms']:8.1f}  (n={s['n']})")

    out = Path("reports/latency_sim.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"trials": rows, "summary": summary}, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
