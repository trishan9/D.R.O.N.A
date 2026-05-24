"""
D.R.O.N.A. Orchestrator Node — ROS2 Humble

Central coordinator. Subscribes to engagement detections, drives the session
state machine, and dispatches gesture commands and advising queries.

Topics:
    sub  /drona/engagement          (drona_msgs/EngagementDetection)
    sub  /drona/advising_response   (drona_msgs/AdvisingResponse)
    sub  /drona/gesture_result      (drona_msgs/GestureResult)
    pub  /drona/gesture_command     (drona_msgs/GestureCommand)
    pub  /drona/student_query       (drona_msgs/AdvisingQuery)
    pub  /drona/session_state       (drona_msgs/SessionState)

Parameters:
    session_timeout_s  : 8.0
    tick_hz            : 10.0
    max_pathways       : 3
"""

from __future__ import annotations

import queue
import uuid

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from drona_msgs.msg import (
    AdvisingQuery,
    AdvisingResponse,
    EngagementDetection,
    GestureCommand,
    GestureResult,
    SessionState,
)

from drona_ros.msg_bridge import (
    advising_query_to_ros,
    session_state_to_ros,
)


class OrchestratorNode(Node):
    """ROS2 orchestrator — drives session lifecycle via engagement events."""

    def __init__(self) -> None:
        super().__init__("drona_orchestrator_node")

        self.declare_parameter("session_timeout_s", 8.0)
        self.declare_parameter("tick_hz", 10.0)
        self.declare_parameter("max_pathways", 3)

        timeout = float(self.get_parameter("session_timeout_s").value)
        tick_hz = float(self.get_parameter("tick_hz").value)
        self._max_pathways = int(self.get_parameter("max_pathways").value)

        from drona.orchestrator.session_machine import SessionMachine
        from drona.utils.settings import settings
        self._machine = SessionMachine(
            timeout_s=timeout if timeout is not None else settings.session_timeout_s
        )

        self._pending_query: str | None = None
        self._awaiting_response = False
        self._awaiting_gesture = False
        self._gesture_queue: queue.SimpleQueue = queue.SimpleQueue()

        cb = MutuallyExclusiveCallbackGroup()

        # Subscribers
        self.create_subscription(
            EngagementDetection, "/drona/engagement", self._on_engagement, 10,
            callback_group=cb,
        )
        self.create_subscription(
            AdvisingResponse, "/drona/advising_response", self._on_advising_response, 10,
            callback_group=cb,
        )
        self.create_subscription(
            GestureResult, "/drona/gesture_result", self._on_gesture_result, 10,
            callback_group=cb,
        )

        # Publishers
        self._gesture_pub = self.create_publisher(GestureCommand, "/drona/gesture_command", 10)
        self._query_pub = self.create_publisher(AdvisingQuery, "/drona/student_query", 10)
        self._state_pub = self.create_publisher(SessionState, "/drona/session_state", 10)

        # Main tick timer
        self._timer = self.create_timer(1.0 / tick_hz, self._tick, callback_group=cb)

        self.get_logger().info(
            f"OrchestratorNode ready. timeout={timeout}s tick={tick_hz}Hz"
        )

    # ── Inbound ────────────────────────────────────────────────────────────────

    def _on_engagement(self, msg: EngagementDetection) -> None:
        from drona.perception.mediapipe_detector import DetectionResult, EngagementState
        try:
            state = EngagementState(msg.state)
        except ValueError:
            state = EngagementState.ABSENT

        detection = DetectionResult(
            state=state,
            confidence=msg.confidence,
            distance_m=msg.distance_m,
        )
        prev_state = self._machine.context.state
        self._machine.feed_detection(detection)
        new_state = self._machine.context.state

        if new_state != prev_state:
            self.get_logger().info(f"Session: {prev_state.value} → {new_state.value}")
            self._publish_session_state()
            self._on_state_entry(new_state)

    def _on_advising_response(self, msg: AdvisingResponse) -> None:
        self._awaiting_response = False
        self.get_logger().info(
            f"Advising response received: {len(msg.pathways)} pathways, "
            f"bias={[b.bias_type for b in msg.bias_flags]}"
        )
        # Mark response delivered in state machine
        self._machine.mark_response_delivered()
        self._publish_session_state()
        # Queue farewell gesture
        self._gesture_queue.put("farewell")

    def _on_gesture_result(self, msg: GestureResult) -> None:
        self._awaiting_gesture = False
        if msg.success:
            self.get_logger().info(
                f"Gesture '{msg.gesture_label}' done "
                f"({msg.frames_executed} frames, {msg.policy_used})"
            )
        else:
            self.get_logger().warn(f"Gesture '{msg.gesture_label}' failed: {msg.error_message}")

        # If farewell completed, close session
        if msg.gesture_label == "farewell":
            self._machine.mark_session_closed()
            self._publish_session_state()

    # ── State machine dispatch ─────────────────────────────────────────────────

    def _on_state_entry(self, state) -> None:
        from drona.orchestrator.session_machine import SessionState as SS
        if state == SS.GREETING:
            self._send_gesture("greet")
        elif state == SS.NEEDS_ASSESSMENT:
            self._send_gesture("listen")
        elif state == SS.CLOSURE:
            self._send_gesture("farewell")

    def _tick(self) -> None:
        # Consume pending query if in advising state and not waiting
        if (
            self._pending_query is not None
            and not self._awaiting_response
            and not self._awaiting_gesture
        ):
            self._send_query(self._pending_query)
            self._pending_query = None
            self._awaiting_response = True

        # Drain gesture queue if not currently executing one
        if not self._awaiting_gesture:
            try:
                label = self._gesture_queue.get_nowait()
                self._send_gesture(label)
            except queue.Empty:
                pass

    def _send_gesture(self, label: str) -> None:
        self._awaiting_gesture = True
        msg = GestureCommand()
        msg.stamp = self.get_clock().now().to_msg()
        msg.gesture_label = label
        self._gesture_pub.publish(msg)
        self.get_logger().info(f"Gesture command sent: {label}")

    def _send_query(self, text: str) -> None:
        from drona.contracts import AdvisingQuery as PydanticQuery, StudentProfile
        pydantic_q = PydanticQuery(
            query_id=str(uuid.uuid4()),
            query_text=text,
            profile=StudentProfile(session_id=str(self._machine.context.session_id)),
            max_pathways=self._max_pathways,
        )
        ros_msg = advising_query_to_ros(pydantic_q)
        self._query_pub.publish(ros_msg)
        self.get_logger().info(f"Query published: {text[:60]}")

    def _publish_session_state(self) -> None:
        msg = session_state_to_ros(self._machine.context, self.get_clock())
        self._state_pub.publish(msg)

    # ── External interface (called by dashboard / CLI) ─────────────────────────

    def submit_student_query(self, text: str) -> None:
        """Called externally to inject a student query into the session."""
        self._pending_query = text
        self._machine.submit_query(text)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = OrchestratorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
