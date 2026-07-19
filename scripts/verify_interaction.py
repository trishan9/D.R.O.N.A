#!/usr/bin/env python3
"""
Verify the D.R.O.N.A. interaction loop end to end, in sim.

Injects an engagement sequence on /drona/engagement (exactly what perception_node
emits when a real face approaches - the sim camera can't see a real face, so we
stand in for it) and checks the whole chain reacts:

  /drona/engagement -> orchestrator (session machine) -> /drona/gesture_command
    -> gesture_node -> /drona/joint_states -> gz_joint_relay -> the arm moves

Assumes drona_gazebo.launch.py is already running. Exit 0 if the orchestrator
commands a greeting AND the arm measurably moves.
"""
from __future__ import annotations

import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node

from drona_msgs.msg import EngagementDetection, GestureCommand
from sensor_msgs.msg import JointState

GZ_STATE = "/world/drona_advising/model/drona_humanoid/joint_state"


class LoopProbe(Node):
    def __init__(self) -> None:
        super().__init__("drona_loop_probe")
        self._eng_pub = self.create_publisher(EngagementDetection, "/drona/engagement", 10)
        self.gestures: list[str] = []
        self.sessions: list[str] = []
        self._rest: np.ndarray | None = None
        self.max_dev = 0.0
        self.create_subscription(GestureCommand, "/drona/gesture_command", self._on_gesture, 10)
        self.create_subscription(JointState, GZ_STATE, self._on_joint, 10)
        self._t0 = time.time()
        self.create_timer(0.2, self._tick)  # 5 Hz engagement stream

    def _on_gesture(self, msg: GestureCommand) -> None:
        self.gestures.append(msg.gesture_label)
        self.get_logger().info(f"orchestrator commanded gesture: {msg.gesture_label}")

    def _on_joint(self, msg: JointState) -> None:
        if not msg.position:
            return
        arr = np.asarray(msg.position, dtype=float)
        if self._rest is None:
            self._rest = arr.copy()
        self.max_dev = max(self.max_dev, float(np.max(np.abs(arr - self._rest))))

    def _tick(self) -> None:
        # ramp APPROACHING -> ENGAGED to drive the session machine. NOTE: the
        # EngagementState enum values are lowercase ("engaged"), and the
        # orchestrator does EngagementState(msg.state) - so the wire value MUST be
        # lowercase or it silently falls back to ABSENT.
        el = time.time() - self._t0
        state = "approaching" if el < 2.5 else "engaged"
        m = EngagementDetection()
        m.stamp = self.get_clock().now().to_msg()
        m.state = state
        m.confidence = 0.92
        m.distance_m = 1.6 if el < 2.5 else 0.9
        self._eng_pub.publish(m)


def main() -> int:
    rclpy.init()
    node = LoopProbe()
    end = time.time() + 20.0
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.1)

    greeted = "greet" in node.gestures
    moved = node.max_dev > 0.05
    print("\n=== INTERACTION LOOP RESULT ===")
    print(f"  gestures commanded by orchestrator : {node.gestures or '(none)'}")
    print(f"  greeting commanded                 : {greeted}")
    print(f"  arm moved (max joint dev)          : {node.max_dev:.3f} rad -> {moved}")
    node.destroy_node()
    rclpy.shutdown()

    if greeted and moved:
        print("  LOOP VERIFIED: student engaged -> robot greeted -> arm moved.")
        return 0
    if greeted and not moved:
        print("  PARTIAL: greeting commanded but arm did not move "
              "(is gesture_node in the launch?).")
        return 1
    print("  NOT VERIFIED: orchestrator did not command a greeting.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
