"""
D.R.O.N.A. Policy Node — ROS2 Humble (Research Contribution C3)

Wraps LeRobot gesture-policy inference (drona.interaction) as a ROS2 **action
server**. This is the action-based counterpart to gesture_node's blocking
service: it streams per-frame feedback and supports cancellation (preemption),
which the orchestrator/dashboard use to play a gesture out visibly and abort it
if the student disengages mid-motion.

Action:
    /drona/execute_gesture_action  (drona_msgs/action/ExecuteGesture)
        goal:     gesture_label, target_xyz, policy_hint
        feedback: progress, current_frame, total_frames, joint_positions
        result:   GestureResult, success, error

Topics:
    pub  /drona/joint_states  (sensor_msgs/JointState)  — streamed during motion

Parameters:
    checkpoint_dir : ""     path to ACT/Diffusion checkpoints (auto-detect if "")
    device         : cpu    torch device for learned policies
    control_hz     : 20.0   control + joint-publish rate
    use_hardware   : false  also command the physical arm via arm_interface

Policy selection mirrors drona.interaction.act_policy.PolicyRouter: a trained
LeRobot checkpoint is used when present, otherwise the keyframe baseline — so
this node runs with or without LeRobot installed.
"""

from __future__ import annotations

import time

import numpy as np
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from drona_msgs.action import ExecuteGesture
from drona_msgs.msg import GestureResult
from sensor_msgs.msg import JointState

_VALID_GESTURES = {"greet", "nod", "point", "idle", "listen", "farewell"}


class PolicyNode(Node):
    """Action server that rolls out a gesture policy with streaming feedback."""

    def __init__(self) -> None:
        super().__init__("drona_policy_node")

        self.declare_parameter("checkpoint_dir", "")
        self.declare_parameter("device", "cpu")
        self.declare_parameter("control_hz", 20.0)
        self.declare_parameter("use_hardware", False)

        self._checkpoint_dir = self.get_parameter("checkpoint_dir").value or None
        self._device = self.get_parameter("device").value or "cpu"
        self._control_hz = float(self.get_parameter("control_hz").value)
        self._use_hardware = bool(self.get_parameter("use_hardware").value)

        self._router = None  # lazy
        self._arm = None     # lazy
        self._cb = ReentrantCallbackGroup()

        self._joint_pub = self.create_publisher(JointState, "/drona/joint_states", 10)

        self._action_server = ActionServer(
            self,
            ExecuteGesture,
            "/drona/execute_gesture_action",
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            cancel_callback=self._on_cancel,
            callback_group=self._cb,
        )

        self.get_logger().info(
            f"PolicyNode ready. device={self._device} "
            f"checkpoint_dir={self._checkpoint_dir or 'auto (keyframe fallback)'}"
        )

    # ── Lazy initialisers ─────────────────────────────────────────────────────

    def _get_router(self):
        if self._router is None:
            from drona.interaction.act_policy import PolicyRouter
            from drona.utils.settings import settings

            ckpt = self._checkpoint_dir or str(settings.data_dir / "checkpoints")
            self._router = PolicyRouter(checkpoint_base_dir=ckpt, device=self._device)
            self.get_logger().info("PolicyRouter initialised.")
        return self._router

    def _get_arm(self):
        if self._arm is None and self._use_hardware:
            from drona_ros.arm_interface import SO100ArmInterface

            self._arm = SO100ArmInterface()
            self._arm.connect()
            self.get_logger().info("SO-100 arm connected.")
        return self._arm

    # ── Goal / cancel policy ──────────────────────────────────────────────────

    def _on_goal(self, goal_request) -> GoalResponse:
        label = goal_request.gesture_label
        if label not in _VALID_GESTURES:
            self.get_logger().warn(f"Rejecting unknown gesture '{label}'")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle) -> CancelResponse:
        self.get_logger().info("Gesture cancel requested — accepting.")
        return CancelResponse.ACCEPT

    # ── Execution ──────────────────────────────────────────────────────────────

    def _execute(self, goal_handle):
        from drona.interaction.mujoco_env import StubEnv

        label = goal_handle.request.gesture_label
        policy = self._get_router().get_policy(label)
        policy.reset()
        arm = self._get_arm()

        env = StubEnv(dt=1.0 / self._control_hz)
        obs = env.reset()
        total = getattr(policy, "total_frames", 0)
        interval = 1.0 / self._control_hz

        feedback = ExecuteGesture.Feedback()
        result = ExecuteGesture.Result()

        frames = 0
        t_start = time.monotonic()

        while not getattr(policy, "is_complete", False):
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.success = False
                result.error = "cancelled"
                result.result = self._build_result_msg(label, False, frames, t_start,
                                                        policy, error="cancelled")
                env.close()
                self.get_logger().info(f"Gesture '{label}' cancelled at frame {frames}.")
                return result

            action = policy.select_action({"observation.state": obs})
            obs, _ = env.step(action)
            frames += 1

            if arm is not None:
                arm.set_joint_positions(action)

            self._publish_joints(obs)

            feedback.progress = float(frames / total) if total else 0.0
            feedback.current_frame = frames
            feedback.total_frames = int(total)
            feedback.joint_positions = obs.astype(float).tolist()
            goal_handle.publish_feedback(feedback)

            time.sleep(interval)

        env.close()
        goal_handle.succeed()

        result.success = True
        result.error = ""
        result.result = self._build_result_msg(label, True, frames, t_start, policy)
        self.get_logger().info(
            f"Gesture '{label}' complete — {frames} frames, "
            f"{result.result.duration_s:.2f}s, policy={result.result.policy_used}"
        )
        return result

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _build_result_msg(
        self, label, success, frames, t_start, policy, error: str = ""
    ) -> GestureResult:
        msg = GestureResult()
        msg.stamp = self.get_clock().now().to_msg()
        msg.gesture_label = label
        msg.success = success
        msg.frames_executed = frames
        msg.duration_s = float(time.monotonic() - t_start)
        msg.policy_used = getattr(policy, "name", "")
        msg.error_message = error
        return msg

    def _publish_joints(self, q: np.ndarray) -> None:
        from drona.interaction.demonstration import JOINT_NAMES

        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = list(JOINT_NAMES)
        msg.position = q.astype(float).tolist()
        self._joint_pub.publish(msg)

    def destroy_node(self) -> None:
        if self._arm is not None:
            self._arm.disconnect()
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PolicyNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
