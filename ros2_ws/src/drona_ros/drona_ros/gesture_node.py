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
    gesture_result_to_ros,
    ros_gesture_command_to_action,
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

        self._dispatcher = None  # lazy
        self._arm_interface = None
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

    def _get_dispatcher(self):
        if self._dispatcher is None:
            from drona.interaction.gesture_dispatcher import GestureDispatcher
            from drona.interaction.act_policy import PolicyRouter
            from drona.utils.settings import settings

            ckpt = self._checkpoint_dir or str(settings.data_dir / "checkpoints")
            router = PolicyRouter(checkpoint_base_dir=ckpt, device="cpu")
            self._dispatcher = GestureDispatcher(policy_router=router)
            self.get_logger().info("GestureDispatcher initialised.")
        return self._dispatcher

    def _get_arm(self):
        if self._arm_interface is None:
            if self._use_hardware:
                from drona_ros.arm_interface import SO100ArmInterface
                self._arm_interface = SO100ArmInterface()
                self.get_logger().info("SO-100 arm interface connected.")
            else:
                from drona_ros.arm_interface import SimArmInterface
                self._arm_interface = SimArmInterface()
                self.get_logger().info("Sim arm interface active.")
        return self._arm_interface

    def _publish_joints(self, q: np.ndarray) -> None:
        from drona.interaction.demonstration import JOINT_NAMES
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = JOINT_NAMES
        msg.position = q.tolist()
        self._joint_pub.publish(msg)

    def _execute(self, action) -> GestureResult:
        """Run the gesture, stream joints, send to hardware if enabled."""
        dispatcher = self._get_dispatcher()
        arm = self._get_arm()

        from drona.interaction.act_policy import KeyframePolicy
        from drona.interaction.demonstration import GESTURE_KEYFRAMES

        gesture_label = str(action.gesture)
        policy = dispatcher._router.get_policy(gesture_label)
        policy.reset()

        from drona.interaction.mujoco_env import StubEnv
        env = StubEnv()
        obs = env.reset()

        positions = []
        t_start = time.monotonic()
        dt = 0.05
        frame_interval = 1.0 / self._joint_pub_hz

        last_pub = time.monotonic()
        while not getattr(policy, "is_complete", False):
            action_joints = policy.select_action({"observation.state": obs})
            obs, _ = env.step(action_joints)
            positions.append(obs.copy())

            # Send to hardware
            arm.set_joint_positions(action_joints)

            # Publish joint states at configured rate
            now = time.monotonic()
            if now - last_pub >= frame_interval:
                self._publish_joints(obs)
                last_pub = now

            time.sleep(dt)

        env.close()
        duration = time.monotonic() - t_start

        from drona.contracts import InteractionActionResult
        result_pydantic = InteractionActionResult(
            gesture_label=gesture_label,
            success=True,
            frames_executed=len(positions),
            duration_s=duration,
            policy_used=policy.name,
        )
        return gesture_result_to_ros(result_pydantic, self.get_clock())

    def _on_command(self, msg: GestureCommand) -> None:
        if not self._exec_lock.acquire(blocking=False):
            self.get_logger().warn(
                f"Gesture '{msg.gesture_label}' dropped — previous gesture still running."
            )
            return
        try:
            self.get_logger().info(f"Executing gesture: {msg.gesture_label}")
            action = ros_gesture_command_to_action(msg)
            result = self._execute(action)
            self._result_pub.publish(result)
            self.get_logger().info(
                f"Gesture '{msg.gesture_label}' complete in {result.duration_s:.2f}s "
                f"({result.frames_executed} frames, {result.policy_used})"
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
                result = self._execute(action)
                response.result = result
                response.success = True
            except Exception as exc:
                self.get_logger().error(f"Execute gesture service error: {exc}")
                response.success = False
                response.error = str(exc)
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GestureNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
