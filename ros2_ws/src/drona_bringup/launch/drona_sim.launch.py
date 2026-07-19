"""
D.R.O.N.A. simulation launch - all four nodes in stub/sim mode.

Usage (on Ubuntu with ROS2 Jazzy sourced):
    ros2 launch drona_bringup drona_sim.launch.py

All nodes use stub/sim implementations:
    - StubDetector (scripted engagement sequence) for perception
    - SimArmInterface (StubEnv physics) for gesture execution
    - KeyframePolicy for gestures (ACT if checkpoint exists)
    - AdvisingEngine with whatever ChromaDB data is available

Topic graph:
    perception_node → /drona/engagement → orchestrator_node
    orchestrator_node → /drona/gesture_command → gesture_node
    orchestrator_node → /drona/student_query → advising_node
    advising_node → /drona/advising_response → orchestrator_node
    gesture_node → /drona/gesture_result → orchestrator_node
    gesture_node → /drona/joint_states  (for rviz / visualization)
"""

from __future__ import annotations

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("drona_bringup")
    params_file = os.path.join(pkg_share, "config", "params.yaml")

    log_level_arg = DeclareLaunchArgument(
        "log_level", default_value="INFO",
        description="Log level for all D.R.O.N.A. nodes"
    )
    log_level = LaunchConfiguration("log_level")

    perception_node = Node(
        package="drona_ros",
        executable="perception_node",
        name="drona_perception_node",
        parameters=[params_file],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    gesture_node = Node(
        package="drona_ros",
        executable="gesture_node",
        name="drona_gesture_node",
        parameters=[params_file],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    advising_node = Node(
        package="drona_ros",
        executable="advising_node",
        name="drona_advising_node",
        parameters=[params_file],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    orchestrator_node = Node(
        package="drona_ros",
        executable="orchestrator_node",
        name="drona_orchestrator_node",
        parameters=[params_file],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    return LaunchDescription([
        log_level_arg,
        LogInfo(msg="Starting D.R.O.N.A. in SIMULATION mode"),
        perception_node,
        gesture_node,
        advising_node,
        orchestrator_node,
    ])
