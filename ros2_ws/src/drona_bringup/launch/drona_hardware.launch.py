"""
D.R.O.N.A. hardware launch — real camera + real SO-100 arm.

Usage (on Ubuntu 22.04 with ROS2 Humble, arm connected via USB):
    ros2 launch drona_bringup drona_hardware.launch.py
    ros2 launch drona_bringup drona_hardware.launch.py arm_port:=/dev/ttyUSB0

Pre-flight checklist:
    1. SO-100 arm powered and connected via U2D2 USB adapter
    2. Webcam connected (camera_index=0 default)
    3. Ollama running: ollama serve
    4. ChromaDB populated: python scripts/ingest_data.py
    5. ACT checkpoint present: python scripts/train_act.py (or use keyframe fallback)
"""

from __future__ import annotations

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("drona_bringup")
    hw_params = os.path.join(pkg_share, "config", "hardware.yaml")

    arm_port_arg = DeclareLaunchArgument(
        "arm_port", default_value="/dev/ttyUSB0",
        description="Serial port for SO-100 arm (e.g. /dev/ttyUSB0 or COM3)"
    )
    log_level_arg = DeclareLaunchArgument(
        "log_level", default_value="INFO"
    )
    log_level = LaunchConfiguration("log_level")

    perception_node = Node(
        package="drona_ros",
        executable="perception_node",
        name="drona_perception_node",
        parameters=[hw_params],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    gesture_node = Node(
        package="drona_ros",
        executable="gesture_node",
        name="drona_gesture_node",
        parameters=[
            hw_params,
            {"use_hardware": True},
        ],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    advising_node = Node(
        package="drona_ros",
        executable="advising_node",
        name="drona_advising_node",
        parameters=[hw_params],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    orchestrator_node = Node(
        package="drona_ros",
        executable="orchestrator_node",
        name="drona_orchestrator_node",
        parameters=[hw_params],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    return LaunchDescription([
        arm_port_arg,
        log_level_arg,
        LogInfo(msg="Starting D.R.O.N.A. in HARDWARE mode — ensure arm is connected"),
        perception_node,
        gesture_node,
        advising_node,
        orchestrator_node,
    ])
