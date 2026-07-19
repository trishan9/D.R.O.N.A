"""
D.R.O.N.A. Perception Node - ROS2 Jazzy

Runs the engagement detector at a configurable rate and publishes
EngagementDetection messages. Three interchangeable frame sources:

    stub        (use_camera=false, image_topic="")   scripted detections - CI/dev
    webcam      (use_camera=true,  image_topic="")   local camera + MediaPipe - hardware
    image topic (image_topic set)                    sensor_msgs/Image + MediaPipe -
                                                     Gazebo / Isaac / remote camera

The image-topic mode is what makes the node simulation-first: the same
MediaPipe pipeline that runs on the robot consumes the simulator's rendered
camera stream, so perception behaviour transfers sim-to-real unchanged.

Topics:
    sub  <image_topic>      (sensor_msgs/Image, optional)
    pub  /drona/engagement  (drona_msgs/EngagementDetection)

Parameters:
    use_camera      : false  (true = local webcam + MediaPipe)
    camera_index    : 0
    camera_backend  : "auto"  (auto | opencv [USB] | picamera2 [Pi CSI])
    detection_hz    : 10.0
    image_topic     : ""     (e.g. /drona/camera/image_raw in Gazebo)
    stub_script     : ""     (comma-separated engagement states for stub mode)
"""

from __future__ import annotations

import numpy as np
import rclpy
from drona_msgs.msg import EngagementDetection
from rclpy.node import Node
from sensor_msgs.msg import Image

from drona_ros.msg_bridge import engagement_to_ros


class PerceptionNode(Node):
    """Publishes engagement detections from camera, image topic, or stub script."""

    def __init__(self) -> None:
        super().__init__("drona_perception_node")

        self.declare_parameter("use_camera", False)
        self.declare_parameter("camera_index", 0)
        # auto = USB/OpenCV first, then Pi CSI/picamera2. Force with
        # "opencv" (USB webcam) or "picamera2" (ribbon camera).
        self.declare_parameter("camera_backend", "auto")
        self.declare_parameter("detection_hz", 10.0)
        self.declare_parameter("image_topic", "")
        self.declare_parameter("stub_script", "")

        use_camera = self.get_parameter("use_camera").value
        camera_idx = int(self.get_parameter("camera_index").value)
        camera_backend = str(self.get_parameter("camera_backend").value)
        hz = float(self.get_parameter("detection_hz").value)
        self._image_topic = str(self.get_parameter("image_topic").value or "")

        self._pub = self.create_publisher(EngagementDetection, "/drona/engagement", 10)
        self._latest_frame: np.ndarray | None = None

        from drona.perception.mediapipe_detector import make_detector
        if self._image_topic:
            # Frames come from the simulator / another node - never open a webcam.
            self._detector = make_detector(prefer_mediapipe=True, open_camera=False)
            self._image_sub = self.create_subscription(
                Image, self._image_topic, self._on_image, 10
            )
        else:
            self._detector = make_detector(
                prefer_mediapipe=use_camera,
                camera_index=camera_idx,
                camera_backend=camera_backend,
            )

        period = 1.0 / hz
        self._timer = self.create_timer(period, self._tick)

        mode = (f"image_topic={self._image_topic}" if self._image_topic
                else ("camera" if use_camera else "stub"))
        self.get_logger().info(f"PerceptionNode ready. mode={mode} @ {hz:.1f} Hz")

    # ── Image-topic mode ──────────────────────────────────────────────────────

    def _on_image(self, msg: Image) -> None:
        """Convert an incoming Image to an RGB ndarray (no cv_bridge needed)."""
        try:
            enc = msg.encoding.lower()
            data = np.frombuffer(bytes(msg.data), dtype=np.uint8)
            # step = bytes per row (may include padding beyond width*3)
            frame = data[: msg.height * msg.step].reshape(msg.height, msg.step)
            frame = frame[:, : msg.width * 3].reshape(msg.height, msg.width, 3)
            if enc in ("bgr8",):
                frame = frame[:, :, ::-1]  # BGR -> RGB
            elif enc not in ("rgb8",):
                self.get_logger().warn(
                    f"Unsupported image encoding '{msg.encoding}' - expected rgb8/bgr8",
                    throttle_duration_sec=10.0,
                )
                return
            self._latest_frame = np.ascontiguousarray(frame)
        except Exception as exc:
            self.get_logger().error(f"Image conversion failed: {exc}")

    # ── Detection tick ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        try:
            if self._image_topic:
                if self._latest_frame is None:
                    self.get_logger().info(
                        f"waiting for frames on {self._image_topic} ...",
                        throttle_duration_sec=5.0,
                    )
                    return
                detection = self._detector.detect(frame=self._latest_frame)
            else:
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
