"""
D.R.O.N.A. hardware launch - real camera + real SO-100 arm.

This is the deployment entry point. It runs the SAME node graph as
drona_system.launch.py / the Gazebo sim - only the parameter file changes
(hardware.yaml: use_camera=true, use_hardware=true), which is exactly what
makes behaviour transfer from simulation: no code path is hardware-specific
beyond the arm serial driver and the webcam index.

Usage (on Ubuntu 22.04 with ROS2 Humble, arm connected via USB):
    ros2 launch drona_bringup drona_hardware.launch.py
    ros2 launch drona_bringup drona_hardware.launch.py arm_port:=/dev/ttyUSB1
    ros2 launch drona_bringup drona_hardware.launch.py use_rviz:=true rosbridge:=true

Pre-flight checklist:
    1. SO-100 arm powered and connected via U2D2 USB adapter (check arm_port)
    2. Webcam connected (camera_index in hardware.yaml)
    3. Ollama running: ollama serve
    4. ChromaDB populated: python scripts/ingest_data.py
    5. Policies exported for deployment: python scripts/export_policies.py
       (policy_node then serves ONNX; ACT checkpoints are picked up if present)
    6. Calibrate: verify REST_POSE matches the physical home position
       (see arm_interface.py docstring for the Dynamixel procedure)
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    desc_share = get_package_share_directory("drona_description")
    bringup_share = get_package_share_directory("drona_bringup")
    urdf = os.path.join(desc_share, "urdf", "drona_humanoid.urdf.xacro")
    rviz_config = os.path.join(desc_share, "rviz", "drona.rviz")
    hw_params = os.path.join(bringup_share, "config", "hardware.yaml")

    arm_port = LaunchConfiguration("arm_port")
    log_level = LaunchConfiguration("log_level")
    use_rviz = LaunchConfiguration("use_rviz")
    rosbridge = LaunchConfiguration("rosbridge")

    args = [
        DeclareLaunchArgument("arm_port", default_value="/dev/ttyUSB0",
                              description="Serial port for SO-100 arm "
                                          "(e.g. /dev/ttyUSB0 or COM3)"),
        DeclareLaunchArgument("log_level", default_value="INFO"),
        DeclareLaunchArgument("use_rviz", default_value="false",
                              description="Digital-twin view of the physical robot"),
        DeclareLaunchArgument("rosbridge", default_value="false",
                              description="Websocket on :9090 for the web Robot page"),
    ]

    # TF from the physical robot's joint stream - RViz / web twin mirror reality.
    robot_description = {"robot_description": Command(["xacro ", urdf])}
    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )
    jsp = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        parameters=[{"source_list": ["/drona/joint_states"]}],
        output="screen",
    )

    common = dict(
        package="drona_ros",
        parameters=[hw_params, {"arm_port": arm_port}],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )
    perception = Node(executable="perception_node", name="drona_perception_node", **common)
    policy = Node(executable="policy_node", name="drona_policy_node", **common)
    gesture = Node(executable="gesture_node", name="drona_gesture_node", **common)
    advising = Node(executable="advising_node", name="drona_advising_node", **common)
    orchestrator = Node(executable="orchestrator_node", name="drona_orchestrator_node", **common)
    diagnostics = Node(executable="diagnostics_node", name="drona_diagnostics_node", **common)

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        condition=IfCondition(use_rviz),
        output="screen",
    )
    rosbridge_node = Node(
        package="rosbridge_server",
        executable="rosbridge_websocket",
        name="rosbridge_websocket",
        condition=IfCondition(rosbridge),
        output="screen",
    )

    return LaunchDescription([
        *args,
        LogInfo(msg="Starting D.R.O.N.A. in HARDWARE mode - ensure the arm is "
                    "connected and calibrated (see the pre-flight checklist)."),
        rsp,
        jsp,
        perception,
        policy,
        gesture,
        advising,
        orchestrator,
        diagnostics,
        rviz,
        rosbridge_node,
    ])
