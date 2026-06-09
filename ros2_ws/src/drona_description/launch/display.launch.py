"""
Display the D.R.O.N.A. humanoid in RViz with robot_state_publisher.

Usage:
    ros2 launch drona_description display.launch.py
    ros2 launch drona_description display.launch.py gui:=true   # joint sliders

By default the model is driven by the live /drona/joint_states topic published
by the gesture/policy nodes (remapped onto /joint_states). Set gui:=true to use
the joint_state_publisher_gui sliders instead (no backend needed).
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    pkg = get_package_share_directory("drona_description")
    urdf = os.path.join(pkg, "urdf", "drona_humanoid.urdf.xacro")
    rviz_config = os.path.join(pkg, "rviz", "drona.rviz")

    gui = LaunchConfiguration("gui")
    gui_arg = DeclareLaunchArgument(
        "gui", default_value="false",
        description="Use joint_state_publisher_gui sliders instead of /drona/joint_states",
    )

    robot_description = {"robot_description": Command(["xacro ", urdf])}

    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    # When NOT using the GUI, relay the robot's live joint stream to /joint_states.
    jsp_relay = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        parameters=[{"source_list": ["/drona/joint_states"]}],
        condition=UnlessCondition(gui),
        output="screen",
    )

    jsp_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        condition=IfCondition(gui),
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        output="screen",
    )

    return LaunchDescription([gui_arg, rsp, jsp_relay, jsp_gui, rviz])
