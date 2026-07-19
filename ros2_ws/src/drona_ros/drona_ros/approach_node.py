"""
D.R.O.N.A. Approach Node - ROS2 Jazzy

Closed-loop "come to the student" behaviour for the wheeled mobile base.

The robot should not wait at a desk: when perception reports a student at a
distance, it drives forward until it reaches a comfortable conversation range,
then stops and hands over to the greeting/advising loop. When the student
leaves, it stops (and optionally backs off to its station).

Topics:
    sub  /drona/engagement  (drona_msgs/EngagementDetection)
    pub  /cmd_vel           (geometry_msgs/Twist)   -> gz DiffDrive / real base

Parameters:
    target_distance_m : 1.0   stop this far from the student (conversation range)
    approach_tol_m    : 0.15  deadband so the base does not hunt around target
    max_linear_mps    : 0.35  hard speed cap (social-robot safe, not industrial)
    k_linear          : 0.45  proportional gain on distance error
    control_hz        : 10.0  control loop rate
    enabled           : true  set false to freeze the base

Design notes:
  - Proportional control on range only. The camera gives a distance proxy, not a
    bearing, so there is no meaningful heading error to servo on; a real
    deployment with a depth camera or lidar would add angular control here (or
    delegate to Nav2, which speaks the same /cmd_vel interface).
  - The robot only ever moves toward a *detected* student and stops on ABSENT,
    so loss of perception fails safe to "stationary" rather than "driving".
  - This publishes plain geometry_msgs/Twist on /cmd_vel: the universal ROS2
    mobile-base interface. The same node drives the Gazebo model, a Pepper, a
    TIAGo, or a TurtleBot without modification - that is the hardware-agnostic
    claim, demonstrated rather than asserted.
"""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

from drona_msgs.msg import EngagementDetection

# Engagement states (lowercase enum *values*, as they travel on the wire).
_PRESENT = {"passing_by", "approaching", "engaged"}


class ApproachNode(Node):
    """Drives the mobile base toward a detected student, stopping at range."""

    def __init__(self) -> None:
        super().__init__("drona_approach_node")

        self.declare_parameter("target_distance_m", 1.0)
        self.declare_parameter("approach_tol_m", 0.15)
        self.declare_parameter("max_linear_mps", 0.35)
        self.declare_parameter("k_linear", 0.45)
        self.declare_parameter("control_hz", 10.0)
        self.declare_parameter("enabled", True)

        self._target = float(self.get_parameter("target_distance_m").value)
        self._tol = float(self.get_parameter("approach_tol_m").value)
        self._max_v = float(self.get_parameter("max_linear_mps").value)
        self._k = float(self.get_parameter("k_linear").value)
        hz = float(self.get_parameter("control_hz").value)
        self._enabled = bool(self.get_parameter("enabled").value)

        self._distance: float | None = None
        self._present = False
        self._moving = False

        self.create_subscription(
            EngagementDetection, "/drona/engagement", self._on_engagement, 10
        )
        self._cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_timer(1.0 / max(1.0, hz), self._control_tick)

        self.get_logger().info(
            f"ApproachNode ready. target={self._target}m tol={self._tol}m "
            f"max_v={self._max_v}m/s enabled={self._enabled}"
        )

    # ── Perception ────────────────────────────────────────────────────────────

    def _on_engagement(self, msg: EngagementDetection) -> None:
        self._present = msg.state in _PRESENT
        # distance_m is 0.0 when perception has no range estimate
        self._distance = float(msg.distance_m) if msg.distance_m > 0.0 else None

    # ── Control ───────────────────────────────────────────────────────────────

    def _control_tick(self) -> None:
        if not self._enabled:
            return

        # Fail safe: no student, or no range estimate -> stop.
        if not self._present or self._distance is None:
            self._stop()
            return

        error = self._distance - self._target
        if error <= self._tol:
            # Close enough: hold position so the greeting happens at a
            # comfortable, non-intimidating distance.
            if self._moving:
                self.get_logger().info(
                    f"Reached conversation range ({self._distance:.2f}m) - stopping."
                )
            self._stop()
            return

        v = max(-self._max_v, min(self._max_v, self._k * error))
        cmd = Twist()
        cmd.linear.x = v
        self._cmd_pub.publish(cmd)
        if not self._moving:
            self.get_logger().info(
                f"Student at {self._distance:.2f}m - approaching at {v:.2f} m/s."
            )
        self._moving = True

    def _stop(self) -> None:
        self._cmd_pub.publish(Twist())  # all-zero twist
        self._moving = False


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ApproachNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop()  # never leave the base driving on shutdown
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
