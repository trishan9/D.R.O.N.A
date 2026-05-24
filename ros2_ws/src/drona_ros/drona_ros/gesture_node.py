"""
D.R.O.N.A. Gesture Node — ROS2 Humble

Wraps drona.interaction.gesture_dispatcher.GestureDispatcher.
Publishes joint states during execution so visualizers / hardware drivers
can track the arm position in real time.

Topics:
    sub  /drona/gesture_command  (drona_msgs/GestureCommand)
    pub  /drona/gesture_result   (drona_msgs/GestureResult)
    pub  /drona/joint_states     (sensor_msgs/JointState)  — 20 Hz during gesture

Services:
    /drona/execute_gesture  (drona_msgs/ExecuteGesture)  — blocking until complete

Parameters:
    use_hardware   : false  (true = connect to SO-100 arm via arm_interface)
    checkpoint_dir : ""     (path to ACT checkpoint directory)
    joint_pub_hz   : 20.0
"""

from __future__ import annotations

import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup

from drona_msgs.msg import GestureCommand, GestureResult
from drona_msgs.srv import ExecuteGesture
from sensor_msgs.msg import JointState

from drona_ros.msg_bridge import (
    ros_gesture_command_to_action,
    gesture_result_to_ros,
)


class GestureNode(Node):
    """Executes robot gestures and streams joint states to ROS2."""

    def __init__(self) -> None:
        super().__init__("drona_gesture_node")

        self.declare_parameter("use_hardware", False)
        self.declare_parameter("checkpoint_dir", "")
        self.declare_parameter("joint_pub_hz", 20.0)

        self._use_hardware = self.get_parameter("use_hardware").value
        self._checkpoint_dir = self.get_parameter("checkpoint_dir").value or None
        self._joint_pub_hz = float(self.get_parameter("joint_pub_hz").value)

        self._dispatcher = None  # lazy init
        self._arm = None         # lazy init
        self._exec_lock = threading.Lock()

        self._cmd_cb_group = MutuallyExclusiveCallbackGroup()
        self._svc_cb_group = ReentrantCallbackGroup()

        self._cmd_sub = self.create_subscription(
            GestureCommand,
            "/drona/gesture_command",
            self._on_command,
            10,
            callback_group=self._cmd_cb_group,
        )
        self._result_pub = self.create_publisher(GestureResult, "/drona/gesture_result", 10)
        self._joint_pub = self.create_publisher(JointState, "/drona/joint_states", 10)

        self._execute_svc = self.create_service(
            ExecuteGesture,
            "/drona/execute_gesture",
            self._handle_execute,
            callback_group=self._svc_cb_group,
        )

        self.get_logger().info(
            f"GestureNode ready. hardware={'YES' if self._use_hardware else 'sim'} "
            f"checkpoint_dir={self._checkpoint_dir or 'none (keyframe fallback)'}"
        )

    # ── Lazy initialisers ─────────────────────────────────────────────────────

    def _get_dispatcher(self):
        if self._dispatcher is None:
            from drona.interaction.gesture_dispatcher import GestureDispatcher
            from drona.utils.settings import settings
            ckpt = self._checkpoint_dir or str(settings.data_dir / "checkpoints")
            self._dispatcher = GestureDispatcher(
                checkpoint_base_dir=ckpt,
                device="cpu",
            )
            self.get_logger().info("GestureDispatcher initialised.")
        return self._dispatcher

    def _get_arm(self):
        if self._arm is None:
            if self._use_hardware:
                from drona_ros.arm_interface import SO100ArmInterface
                self._arm = SO100ArmInterface()
                self._arm.connect()
                self.get_logger().info("SO-100 arm connected.")
            else:
                from drona_ros.arm_interface import SimArmInterface
                self._arm = SimArmInterface()
                self._arm.connect()
                self.get_logger().info("Sim arm interface active.")
        return self._arm

    # ── Joint state publisher ─────────────────────────────────────────────────

    def _publish_joints(self, q: np.ndarray) -> None:
        from drona.interaction.demonstration import JOINT_NAMES
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = list(JOINT_NAMES)
        msg.position = q.tolist()
        self._joint_pub.publish(msg)

    # ── Gesture execution ─────────────────────────────────────────────────────

    def _execute_gesture(self, action) -> GestureResult:
        """Run gesture via GestureDispatcher and build a RosGestureResult.

        Streams joint positions to /drona/joint_states while executing.
        Sends commands to hardware arm if use_hardware=true.
        """
        dispatcher = self._get_dispatcher()
        arm = self._get_arm()
        gesture_label = action.gesture.value if hasattr(action.gesture, "value") else str(action.gesture)

        # Use dispatcher's internal router to stream joints in real time
        policy = dispatcher._router.get_policy(gesture_label)
        policy.reset()

        from drona.interaction.mujoco_env import StubEnv
        env = StubEnv(dt=0.05)
        obs = env.reset()

        frames = 0
        frame_interval = 1.0 / self._joint_pub_hz
        last_pub = 0.0
        t_start = time.monotonic()

        try:
            while not getattr(policy, "is_complete", False):
                action_joints = policy.select_action({"observation.state": obs})
                obs, _ = env.step(action_joints)
                frames += 1

                # Send to hardware arm
                arm.set_joint_positions(action_joints)

                # Publish joint states at the configured rate
                now = time.monotonic()
                if now - last_pub >= frame_interval:
                    self._publish_joints(obs)
                    last_pub = now

            duration = time.monotonic() - t_start
        finally:
            env.close()

        from drona.contracts import InteractionActionResult
        pydantic_result = InteractionActionResult(
            action_id=action.action_id,
            success=True,
            actual_duration_seconds=time.monotonic() - t_start,
        )
        return gesture_result_to_ros(
            pydantic_result,
            self.get_clock(),
            gesture_label=gesture_label,
            frames_executed=frames,
            policy_used=getattr(policy, "name", ""),
        )

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_command(self, msg: GestureCommand) -> None:
        if not self._exec_lock.acquire(blocking=False):
            self.get_logger().warn(
                f"Gesture '{msg.gesture_label}' dropped — previous gesture still running."
            )
            return
        try:
            self.get_logger().info(f"Executing gesture: {msg.gesture_label}")
            action = ros_gesture_command_to_action(msg)
            result = self._execute_gesture(action)
            self._result_pub.publish(result)
            self.get_logger().info(
                f"Gesture '{msg.gesture_label}' complete — "
                f"{result.frames_executed} frames, {result.duration_s:.2f}s, "
                f"policy={result.policy_used}"
            )
        except Exception as exc:
            self.get_logger().error(f"Gesture execution error: {exc}")
            err_msg = GestureResult()
            err_msg.stamp = self.get_clock().now().to_msg()
            err_msg.gesture_label = msg.gesture_label
            err_msg.success = False
            err_msg.error_message = str(exc)
            self._result_pub.publish(err_msg)
        finally:
            self._exec_lock.release()

    def _handle_execute(
        self, request: ExecuteGesture.Request, response: ExecuteGesture.Response
    ) -> ExecuteGesture.Response:
        with self._exec_lock:
            try:
                action = ros_gesture_command_to_action(request.command)
                result = self._execute_gesture(action)
                response.result = result
                response.success = True
            except Exception as exc:
                self.get_logger().error(f"Execute gesture service error: {exc}")
                response.success = False
                response.error = str(exc)
        return response

    def destroy_node(self) -> None:
        if self._arm is not None:
            self._arm.disconnect()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GestureNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
