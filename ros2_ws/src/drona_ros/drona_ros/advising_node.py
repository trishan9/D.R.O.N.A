"""
D.R.O.N.A. Advising Node — ROS2 Humble

Wraps drona.advising.engine.AdvisingEngine as a ROS2 node.
Provides both pub/sub and service interfaces.

Topics:
    sub  /drona/student_query      (drona_msgs/AdvisingQuery)
    pub  /drona/advising_response  (drona_msgs/AdvisingResponse)

Services:
    /drona/advise  (drona_msgs/Advise)

Parameters:
    log_level       : INFO
    max_pathways    : 3
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup

from drona_msgs.msg import AdvisingQuery, AdvisingResponse
from drona_msgs.srv import Advise

from drona_ros.msg_bridge import (
    ros_to_advising_query,
    advising_response_to_ros,
)


class AdvisingNode(Node):
    """ROS2 wrapper around AdvisingEngine.

    The engine is initialised lazily on first query to avoid blocking the
    node startup (ChromaDB and model loading take several seconds).
    """

    def __init__(self) -> None:
        super().__init__("drona_advising_node")

        self.declare_parameter("log_level", "INFO")
        self.declare_parameter("max_pathways", 3)

        self._engine = None  # lazy init
        self._cb_group = ReentrantCallbackGroup()

        # Subscriber: student query arrives from orchestrator
        self._query_sub = self.create_subscription(
            AdvisingQuery,
            "/drona/student_query",
            self._on_query,
            10,
            callback_group=self._cb_group,
        )

        # Publisher: response goes back to orchestrator (and dashboard via bridge)
        self._response_pub = self.create_publisher(
            AdvisingResponse,
            "/drona/advising_response",
            10,
        )

        # Service: synchronous advising for testing / CLI tools
        self._advise_srv = self.create_service(
            Advise,
            "/drona/advise",
            self._handle_advise,
            callback_group=self._cb_group,
        )

        self.get_logger().info("AdvisingNode ready.")

    def _get_engine(self):
        if self._engine is None:
            self.get_logger().info("Initialising AdvisingEngine (first call) ...")
            from drona.advising.engine import AdvisingEngine
            self._engine = AdvisingEngine()
            self.get_logger().info("AdvisingEngine ready.")
        return self._engine

    def _on_query(self, msg: AdvisingQuery) -> None:
        self.get_logger().info(
            f"Query received [{msg.query_id[:8]}]: {msg.query_text[:60]}..."
        )
        try:
            pydantic_query = ros_to_advising_query(msg)
            response = self._get_engine().advise(pydantic_query)
            ros_response = advising_response_to_ros(response)
            self._response_pub.publish(ros_response)
            self.get_logger().info(
                f"Response published [{msg.query_id[:8]}]: "
                f"{len(response.pathways)} pathways, "
                f"{len(response.bias_flags)} bias flags"
            )
        except Exception as exc:
            self.get_logger().error(f"AdvisingEngine error: {exc}")

    def _handle_advise(
        self,
        request: Advise.Request,
        response: Advise.Response,
    ) -> Advise.Response:
        try:
            pydantic_query = ros_to_advising_query(request.query)
            pydantic_response = self._get_engine().advise(pydantic_query)
            response.response = advising_response_to_ros(pydantic_response)
            response.success = True
        except Exception as exc:
            self.get_logger().error(f"Advise service error: {exc}")
            response.success = False
            response.error = str(exc)
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AdvisingNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
