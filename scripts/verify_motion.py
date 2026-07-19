#!/usr/bin/env python3
"""
Verify the D.R.O.N.A. sim MOTION pipeline end to end.

Assumes drona_gazebo.launch.py is already running (headless is fine). Publishes a
target pose on /drona/joint_states (what the policy/gesture nodes emit) and reads
the robot's ACTUAL joint state back from the gz->ROS bridge, proving the command
travels: /drona/joint_states -> gz_joint_relay -> /drona/gz/<joint>_cmd -> bridge
-> gz PID -> the arm moves.

    python3 scripts/verify_motion.py

Exit 0 (MOTION VERIFIED) if the commanded joint measurably approaches its target.
"""
from __future__ import annotations

import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

TARGET_JOINT = "j1_shoulder"
TARGET_POS = 0.8  # rad - a clearly visible shoulder lift
GZ_STATE_TOPIC = "/world/drona_advising/model/drona_humanoid/joint_state"
JOINTS = ["j0_base_yaw", "j1_shoulder", "j2_elbow",
          "j3_wrist_pitch", "j4_wrist_roll", "j5_gripper"]


class MotionProbe(Node):
    def __init__(self) -> None:
        super().__init__("drona_motion_probe")
        self._pub = self.create_publisher(JointState, "/drona/joint_states", 10)
        self._latest: dict[str, float] = {}
        self.create_subscription(JointState, GZ_STATE_TOPIC, self._on_state, 10)
        self.create_timer(0.05, self._tick)  # 20 Hz command stream

    def _on_state(self, msg: JointState) -> None:
        for n, p in zip(msg.name, msg.position):
            self._latest[n] = p

    def _tick(self) -> None:
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINTS
        msg.position = [TARGET_POS if n == TARGET_JOINT else 0.0 for n in JOINTS]
        self._pub.publish(msg)

    def current(self) -> float | None:
        return self._latest.get(TARGET_JOINT)


def main() -> int:
    rclpy.init()
    node = MotionProbe()
    deadline = time.time() + 25.0

    # wait for the first gz joint_state
    while node.current() is None and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
    start = node.current()
    if start is None:
        print("FAIL: no joint_state from gz bridge - is the sim running?")
        node.destroy_node(); rclpy.shutdown(); return 2
    print(f"initial {TARGET_JOINT} = {start:+.3f} rad; commanding -> {TARGET_POS:+.3f}")

    # drive for a few seconds and watch it approach the target
    end = time.time() + 8.0
    while time.time() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    final = node.current()
    moved = abs(final - start)
    closed = abs(final - TARGET_POS) < abs(start - TARGET_POS)
    print(f"final   {TARGET_JOINT} = {final:+.3f} rad  (moved {moved:.3f} rad, "
          f"{'closer to' if closed else 'not toward'} target)")

    node.destroy_node()
    rclpy.shutdown()
    if moved > 0.05 and closed:
        print("MOTION VERIFIED: the arm followed the commanded pose in sim.")
        return 0
    print("MOTION NOT VERIFIED: joint did not track the command "
          "(check gz PID controllers / use_gz_control).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
