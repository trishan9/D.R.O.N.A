"""
D.R.O.N.A. evaluation launch - runs all four nodes then triggers evaluation.

Usage:
    ros2 launch drona_bringup drona_evaluation.launch.py
    ros2 launch drona_bringup drona_evaluation.launch.py contributions:=c2,c3

Contributions:
    c1 - retrieval quality (needs populated ChromaDB)
    c2 - bias detection
    c3 - gesture smoothness
    c4 - Nepal citation ratio (needs Ollama)
"""

from __future__ import annotations

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("drona_bringup")
    params_file = os.path.join(pkg_share, "config", "params.yaml")

    contributions_arg = DeclareLaunchArgument(
        "contributions", default_value="c2,c3",
        description="Comma-separated evaluation contributions to run"
    )

    eval_process = ExecuteProcess(
        cmd=[
            "python3", "-m", "scripts.run_evaluation",
            "--c2", "--c3",
        ],
        output="screen",
    )

    return LaunchDescription([
        contributions_arg,
        LogInfo(msg="D.R.O.N.A. Evaluation Launch"),
        Node(
            package="drona_ros", executable="advising_node",
            name="drona_advising_node", parameters=[params_file], output="screen",
        ),
        Node(
            package="drona_ros", executable="gesture_node",
            name="drona_gesture_node", parameters=[params_file], output="screen",
        ),
        Node(
            package="drona_ros", executable="perception_node",
            name="drona_perception_node", parameters=[params_file], output="screen",
        ),
        Node(
            package="drona_ros", executable="orchestrator_node",
            name="drona_orchestrator_node", parameters=[params_file], output="screen",
        ),
    ])
