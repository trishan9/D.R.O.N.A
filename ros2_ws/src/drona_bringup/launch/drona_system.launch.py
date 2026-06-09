"""
D.R.O.N.A. full-system launch — the single entry point for an end-to-end demo.

Brings up the complete embodied advising stack:
    - robot_state_publisher (humanoid URDF)  → TF for RViz / sim
    - perception_node    (engagement)
    - policy_node        (gesture ACTION server, streaming feedback)
    - advising_node      (advising service)
    - orchestrator_node  (session state machine: idle→greet→assess→advise→close)
    - optional RViz visualisation
    - optional rosbag recording of the whole interaction

Usage:
    ros2 launch drona_bringup drona_system.launch.py
    ros2 launch drona_bringup drona_system.launch.py use_rviz:=true
    ros2 launch drona_bringup drona_system.launch.py record:=true
    ros2 launch drona_bringup drona_system.launch.py record:=true bag_path:=demo_run

The recorded bag (see docs/ros2_topics_actions.md) captures every D.R.O.N.A.
topic so an end-to-end session can be replayed for the viva / evaluation.
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node

# Topics captured when record:=true.
_RECORD_TOPICS = [
    "/drona/engagement",
    "/drona/gesture_command",
    "/drona/gesture_result",
    "/drona/student_query",
    "/drona/advising_response",
    "/drona/session_state",
    "/drona/joint_states",
    "/tf",
    "/tf_static",
    "/robot_description",
]


def generate_launch_description() -> LaunchDescription:
    desc_share = get_package_share_directory("drona_description")
    bringup_share = get_package_share_directory("drona_bringup")
    urdf = os.path.join(desc_share, "urdf", "drona_humanoid.urdf.xacro")
    rviz_config = os.path.join(desc_share, "rviz", "drona.rviz")
    params_file = os.path.join(bringup_share, "config", "params.yaml")

    use_rviz = LaunchConfiguration("use_rviz")
    record = LaunchConfiguration("record")
    bag_path = LaunchConfiguration("bag_path")
    log_level = LaunchConfiguration("log_level")

    args = [
        DeclareLaunchArgument("use_rviz", default_value="false",
                              description="Launch RViz with the D.R.O.N.A. model"),
        DeclareLaunchArgument("record", default_value="false",
                              description="Record all D.R.O.N.A. topics to a rosbag"),
        DeclareLaunchArgument("bag_path", default_value="drona_interaction",
                              description="Output directory for the rosbag"),
        DeclareLaunchArgument("log_level", default_value="INFO"),
    ]

    robot_description = {"robot_description": Command(["xacro ", urdf])}

    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    # Relay the robot's live joint stream onto /joint_states for robot_state_publisher.
    jsp = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        parameters=[{"source_list": ["/drona/joint_states"]}],
        output="screen",
    )

    common = dict(
        package="drona_ros",
        parameters=[params_file],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )
    perception = Node(executable="perception_node", name="drona_perception_node", **common)
    policy = Node(executable="policy_node", name="drona_policy_node", **common)
    advising = Node(executable="advising_node", name="drona_advising_node", **common)
    orchestrator = Node(executable="orchestrator_node", name="drona_orchestrator_node", **common)

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        condition=IfCondition(use_rviz),
        output="screen",
    )

    rosbag = ExecuteProcess(
        cmd=["ros2", "bag", "record", "-o", bag_path, *_RECORD_TOPICS],
        condition=IfCondition(record),
        output="screen",
    )

    return LaunchDescription([
        *args,
        LogInfo(msg="Starting the full D.R.O.N.A. system (perception + policy action "
                    "server + advising + orchestrator)."),
        rsp,
        jsp,
        perception,
        policy,
        advising,
        orchestrator,
        rviz,
        rosbag,
    ])
