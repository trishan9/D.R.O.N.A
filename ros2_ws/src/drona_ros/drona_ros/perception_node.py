"""
D.R.O.N.A. Perception Node - ROS2 Humble

Runs the engagement detector at a configurable rate and publishes
EngagementDetection messages.

Topics:
    pub  /drona/engagement  (drona_msgs/EngagementDetection)

Parameters:
    use_camera      : false  (true = MediaPipeDetector; false = StubDetector)
    camera_index    : 0
    detection_hz    : 10.0
    stub_script     : ""    (comma-separated engagement states for stub mode)
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node

from drona_msgs.msg import EngagementDetection

from drona_ros.msg_bridge import engagement_to_ros


class PerceptionNode(Node):
    """Publishes engagement detections from camera or stub script."""

    def __init__(self) -> None:
        super().__init__("drona_perception_node")

        self.declare_parameter("use_camera", False)
        self.declare_parameter("camera_index", 0)
        self.declare_parameter("detection_hz", 10.0)
        self.declare_parameter("stub_script", "")

        use_camera = self.get_parameter("use_camera").value
        camera_idx = int(self.get_parameter("camera_index").value)
        hz = float(self.get_parameter("detection_hz").value)

        self._pub = self.create_publisher(EngagementDetection, "/drona/engagement", 10)

        from drona.perception.mediapipe_detector import make_detector
        self._detector = make_detector(
            prefer_mediapipe=use_camera,
            camera_index=camera_idx,
        )

        period = 1.0 / hz
        self._timer = self.create_timer(period, self._tick)

        self.get_logger().info(
            f"PerceptionNode ready. mode={'camera' if use_camera else 'stub'} "
            f"@ {hz:.1f} Hz"
        )

    def _tick(self) -> None:
        try:
            detection = self._detector.detect()
            msg = engagement_to_ros(detection, self.get_clock())
            self._pub.publish(msg)
        except Exception as exc:
            self.get_logger().error(f"Detection error: {exc}")

    def destroy_node(self) -> None:
        self._detector.close()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PerceptionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
