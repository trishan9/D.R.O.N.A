#!/usr/bin/env python3
"""
Verify D.R.O.N.A.'s mobile base drives to the student and stops at range.

Assumes drona_gazebo.launch.py mobile:=true is running. Publishes engagement
with a student that starts far away, then checks:

  1. approach_node commands forward /cmd_vel while the student is far,
  2. the robot's odometry actually advances (the wheels move the base),
  3. it STOPS once inside conversation range (does not run the student over),
  4. it stops when the student leaves (fail-safe).

    python3 scripts/verify_locomotion.py
"""
from __future__ import annotations

import sys
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node

from drona_msgs.msg import EngagementDetection


class DriveProbe(Node):
    def __init__(self) -> None:
        super().__init__("drona_drive_probe")
        self._eng = self.create_publisher(EngagementDetection, "/drona/engagement", 10)
        self.cmds: list[float] = []
        self.x0: float | None = None
        self.x: float | None = None
        self.create_subscription(Twist, "/cmd_vel", self._on_cmd, 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        # simulated student range: starts 3 m away, robot should close on it
        self.range_m = 3.0
        self.present = True
        self.create_timer(0.1, self._tick)

    def _on_cmd(self, msg: Twist) -> None:
        self.cmds.append(float(msg.linear.x))

    def _on_odom(self, msg: Odometry) -> None:
        self.x = float(msg.pose.pose.position.x)
        if self.x0 is None:
            self.x0 = self.x

    def _tick(self) -> None:
        m = EngagementDetection()
        m.stamp = self.get_clock().now().to_msg()
        m.state = "engaged" if self.present else "absent"
        m.confidence = 0.9
        m.distance_m = float(self.range_m) if self.present else 0.0
        self._eng.publish(m)


def main() -> int:
    rclpy.init()
    n = DriveProbe()

    def spin(sec: float) -> None:
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(n, timeout_sec=0.05)

    # wait for odom
    t0 = time.time()
    while n.x is None and time.time() - t0 < 20:
        rclpy.spin_once(n, timeout_sec=0.2)
    if n.x is None:
        print("FAIL: no /odom - is mobile:=true and the DiffDrive plugin loaded?")
        n.destroy_node(); rclpy.shutdown(); return 2
    print(f"odom start x = {n.x:+.3f} m")

    # Phase 1: student far away -> robot should drive forward.
    n.range_m = 3.0
    spin(8.0)
    moved = (n.x or 0.0) - (n.x0 or 0.0)
    fwd_cmds = [c for c in n.cmds if c > 0.01]
    print(f"phase 1 (student 3.0 m): forward cmds={len(fwd_cmds)}, "
          f"odom advanced {moved:+.3f} m")

    # Phase 2: student now within conversation range -> robot must STOP.
    n.range_m = 0.9
    n.cmds.clear()
    spin(4.0)
    stopped = all(abs(c) < 0.01 for c in n.cmds) if n.cmds else True
    print(f"phase 2 (student 0.9 m): {len(n.cmds)} cmds, all-zero={stopped}")

    # Phase 3: student leaves -> must stop (fail-safe).
    n.present = False
    n.cmds.clear()
    spin(3.0)
    safe = all(abs(c) < 0.01 for c in n.cmds) if n.cmds else True
    print(f"phase 3 (student absent): {len(n.cmds)} cmds, all-zero={safe}")

    n.destroy_node()
    rclpy.shutdown()

    drove = moved > 0.15 and len(fwd_cmds) > 0
    print("\n=== LOCOMOTION RESULT ===")
    print(f"  drove toward student : {drove} ({moved:+.3f} m)")
    print(f"  stopped at range     : {stopped}")
    print(f"  fail-safe on absent  : {safe}")
    if drove and stopped and safe:
        print("  LOCOMOTION VERIFIED: robot approaches, stops at conversation range, "
              "and halts when the student leaves.")
        return 0
    print("  NOT VERIFIED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
