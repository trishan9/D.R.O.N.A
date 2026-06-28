"""
D.R.O.N.A. in Gazebo Harmonic (gz sim) - locally-runnable simulation.

This is the low-VRAM alternative to Isaac Sim: Gazebo Harmonic runs on CPU/iGPU
and is the recommended sim for the student's GTX-1650 dev box.

Brings up:
    - robot_state_publisher (D.R.O.N.A. humanoid URDF)
    - gz sim with an empty world
    - the model spawned from /robot_description
    - ros_gz_bridge for /clock and joint states
    - the four D.R.O.N.A. nodes in sim mode (perception/policy/advising/orchestrator)

Prerequisites (Ubuntu 22.04 + ROS2 Humble):
    sudo apt install ros-humble-ros-gz gz-harmonic
See docs/sim_setup_gazebo.md for the full guide.

On Windows with no dual-boot: run this inside WSL2 (Ubuntu 22.04); Windows 11's
WSLg renders the GUI window. If GL fails under WSL, `export LIBGL_ALWAYS_SOFTWARE=1`
or pass headless:=true. Full WSL guide: docs/wsl_setup.md.

Usage:
    ros2 launch drona_bringup drona_gazebo.launch.py
    ros2 launch drona_bringup drona_gazebo.launch.py headless:=true
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    desc_share = get_package_share_directory("drona_description")
    bringup_share = get_package_share_directory("drona_bringup")
    urdf = os.path.join(desc_share, "urdf", "drona_humanoid.urdf.xacro")
    params_file = os.path.join(bringup_share, "config", "params.yaml")

    headless = LaunchConfiguration("headless")
    headless_arg = DeclareLaunchArgument(
        "headless", default_value="false",
        description="Run gz sim without the GUI (server only)",
    )

    robot_description = {"robot_description": Command(["xacro ", urdf])}

    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    # gz sim via ros_gz_sim; -r runs immediately, -s is server-only (headless).
    gz_args = PythonExpression(
        ["'-r -s empty.sdf' if '", headless, "' == 'true' else '-r empty.sdf'"]
    )
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": gz_args}.items(),
    )

    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=["-topic", "robot_description", "-name", "drona_humanoid", "-z", "0.0"],
        output="screen",
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/world/empty/model/drona_humanoid/joint_state@sensor_msgs/msg/JointState[gz.msgs.Model",
        ],
        output="screen",
    )

    # D.R.O.N.A. cognition + interaction nodes (sim mode).
    common = dict(package="drona_ros", parameters=[params_file], output="screen")
    perception = Node(executable="perception_node", name="drona_perception_node", **common)
    policy = Node(executable="policy_node", name="drona_policy_node", **common)
    advising = Node(executable="advising_node", name="drona_advising_node", **common)
    orchestrator = Node(executable="orchestrator_node", name="drona_orchestrator_node", **common)

    return LaunchDescription([
        headless_arg,
        LogInfo(msg="Starting D.R.O.N.A. in Gazebo Harmonic"),
        rsp,
        gz_sim,
        spawn,
        bridge,
        perception,
        policy,
        advising,
        orchestrator,
    ])
