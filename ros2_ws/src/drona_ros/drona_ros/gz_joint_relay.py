"""
D.R.O.N.A. Gazebo Joint Relay - ROS2 Jazzy

Bridges the policy's joint stream into Gazebo's per-joint position controllers
so the simulated robot performs exactly the motion the policy commands - the
sim mirrors deployment with zero policy-side changes.

    /drona/joint_states (sensor_msgs/JointState)
        -> /drona/gz/<joint>_cmd (std_msgs/Float64, one per joint)
        -> ros_gz_bridge -> gz.msgs.Double
        -> gz::sim::systems::JointPositionController (per joint, in the URDF)

Only used by drona_gazebo.launch.py; every other mode (RViz, Isaac, hardware)
consumes /drona/joint_states directly.

Parameters:
    joint_states_topic : /drona/joint_states
    command_prefix     : /drona/gz/    (command topic = <prefix><joint>_cmd)
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64


class GzJointRelay(Node):
    """Fan a JointState stream out to per-joint Float64 command topics."""

    def __init__(self) -> None:
        super().__init__("drona_gz_joint_relay")

        self.declare_parameter("joint_states_topic", "/drona/joint_states")
        self.declare_parameter("command_prefix", "/drona/gz/")

        self._prefix = self.get_parameter("command_prefix").value
        topic = self.get_parameter("joint_states_topic").value

        self._pubs: dict[str, rclpy.publisher.Publisher] = {}
        self._sub = self.create_subscription(JointState, topic, self._on_joints, 10)
        self.get_logger().info(f"GzJointRelay ready: {topic} -> {self._prefix}<joint>_cmd")

    def _on_joints(self, msg: JointState) -> None:
        for name, position in zip(msg.name, msg.position, strict=False):
            pub = self._pubs.get(name)
            if pub is None:
                pub = self.create_publisher(Float64, f"{self._prefix}{name}_cmd", 10)
                self._pubs[name] = pub
            out = Float64()
            out.data = float(position)
            pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GzJointRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
