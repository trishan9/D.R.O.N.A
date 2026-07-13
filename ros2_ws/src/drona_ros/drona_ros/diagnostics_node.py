"""
D.R.O.N.A. Diagnostics Node - ROS2 Humble

System health monitor: watches the liveness of every core D.R.O.N.A. stream and
publishes standard diagnostics that RViz's diagnostics panel, rqt_runtime_monitor,
and the web platform (via rosbridge) can all consume.

Topics:
    sub  /drona/engagement        (drona_msgs/EngagementDetection)
    sub  /drona/joint_states      (sensor_msgs/JointState)
    sub  /drona/session_state     (drona_msgs/SessionState)
    sub  /drona/advising_response (drona_msgs/AdvisingResponse)
    pub  /diagnostics             (diagnostic_msgs/DiagnosticArray)

Status semantics per component:
    OK    - a message arrived within stale_after_s
    WARN  - stream silent for > stale_after_s (component may be idle)
    ERROR - never seen since node start (component missing / crashed)

`advising` never goes WARN: responses are event-driven, so silence is normal;
it reports OK once the first response proves the pipeline works.

Parameters:
    publish_hz    : 1.0
    stale_after_s : 5.0
"""

from __future__ import annotations

import time

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from drona_msgs.msg import AdvisingResponse, EngagementDetection, SessionState
from rclpy.node import Node
from sensor_msgs.msg import JointState

_HARDWARE_ID = "drona"


class DiagnosticsNode(Node):
    """Aggregates per-stream liveness into /diagnostics."""

    # component -> (topic, msg type, warn-when-stale)
    _WATCHES = {
        "perception": ("/drona/engagement", EngagementDetection, True),
        "policy": ("/drona/joint_states", JointState, True),
        "orchestrator": ("/drona/session_state", SessionState, True),
        "advising": ("/drona/advising_response", AdvisingResponse, False),
    }

    def __init__(self) -> None:
        super().__init__("drona_diagnostics_node")

        self.declare_parameter("publish_hz", 1.0)
        self.declare_parameter("stale_after_s", 5.0)

        hz = float(self.get_parameter("publish_hz").value)
        self._stale_after = float(self.get_parameter("stale_after_s").value)

        self._start = time.monotonic()
        self._last_seen: dict[str, float | None] = {}
        self._count: dict[str, int] = {}

        for component, (topic, msg_type, _) in self._WATCHES.items():
            self._last_seen[component] = None
            self._count[component] = 0
            self.create_subscription(
                msg_type, topic, self._make_callback(component), 10
            )

        self._pub = self.create_publisher(DiagnosticArray, "/diagnostics", 10)
        self._timer = self.create_timer(1.0 / hz, self._publish)
        self.get_logger().info(
            f"DiagnosticsNode ready - watching {len(self._WATCHES)} streams, "
            f"stale after {self._stale_after:.1f}s"
        )

    def _make_callback(self, component: str):
        def _cb(_msg) -> None:
            self._last_seen[component] = time.monotonic()
            self._count[component] += 1
        return _cb

    def _publish(self) -> None:
        now = time.monotonic()
        arr = DiagnosticArray()
        arr.header.stamp = self.get_clock().now().to_msg()

        for component, (topic, _, warn_when_stale) in self._WATCHES.items():
            last = self._last_seen[component]
            status = DiagnosticStatus()
            status.name = f"drona/{component}"
            status.hardware_id = _HARDWARE_ID

            if last is None:
                status.level = DiagnosticStatus.ERROR
                status.message = f"no messages on {topic} since start"
                age = -1.0
            else:
                age = now - last
                if warn_when_stale and age > self._stale_after:
                    status.level = DiagnosticStatus.WARN
                    status.message = f"stale: last message {age:.1f}s ago"
                else:
                    status.level = DiagnosticStatus.OK
                    status.message = "ok"

            status.values = [
                KeyValue(key="topic", value=topic),
                KeyValue(key="messages_received", value=str(self._count[component])),
                KeyValue(key="last_message_age_s", value=f"{age:.2f}"),
            ]
            arr.status.append(status)

        uptime = DiagnosticStatus()
        uptime.name = "drona/system"
        uptime.hardware_id = _HARDWARE_ID
        uptime.level = DiagnosticStatus.OK
        uptime.message = "running"
        uptime.values = [KeyValue(key="uptime_s", value=f"{now - self._start:.0f}")]
        arr.status.append(uptime)

        self._pub.publish(arr)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DiagnosticsNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
