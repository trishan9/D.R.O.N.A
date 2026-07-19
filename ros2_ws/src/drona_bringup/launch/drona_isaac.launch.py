"""
D.R.O.N.A. ROS2 side for NVIDIA Isaac Sim integration.

Isaac Sim runs in its OWN Python environment (Omniverse Kit), so it is launched
SEPARATELY - see docs/sim_setup_isaac.md and the standalone stage builder at
drona_bringup/isaac/drona_isaac_stage.py. This launch file starts the ROS2-side
nodes that talk to Isaac over the Isaac ROS2 bridge:

    - robot_state_publisher (so RViz/TF match Isaac's articulation)
    - the four D.R.O.N.A. nodes in sim mode

Isaac publishes /clock and subscribes to joint commands / publishes joint states
through omni.isaac.ros2_bridge; the D.R.O.N.A. /drona/joint_states stream drives
the Isaac articulation via the action graph configured in the stage script.

REQUIRES ≥ 8 GB VRAM (RTX class GPU). On the GTX-1650 (4 GB) use Gazebo
(drona_gazebo.launch.py) instead, or run Isaac on a cloud GPU (guide in docs).

Usage:
    # Terminal 1 (Isaac python):
    ./python.sh <repo>/ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py
    # Terminal 2 (ROS2 Jazzy sourced):
    ros2 launch drona_bringup drona_isaac.launch.py
"""

from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    desc_share = get_package_share_directory("drona_description")
    bringup_share = get_package_share_directory("drona_bringup")
    urdf = os.path.join(desc_share, "urdf", "drona_humanoid.urdf.xacro")
    params_file = os.path.join(bringup_share, "config", "params.yaml")

    log_level = LaunchConfiguration("log_level")
    log_level_arg = DeclareLaunchArgument("log_level", default_value="INFO")

    robot_description = {"robot_description": Command(["xacro ", urdf]), "use_sim_time": True}

    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    common = dict(
        package="drona_ros",
        parameters=[params_file, {"use_sim_time": True}],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )
    perception = Node(executable="perception_node", name="drona_perception_node", **common)
    policy = Node(executable="policy_node", name="drona_policy_node", **common)
    advising = Node(executable="advising_node", name="drona_advising_node", **common)
    orchestrator = Node(executable="orchestrator_node", name="drona_orchestrator_node", **common)

    return LaunchDescription([
        log_level_arg,
        LogInfo(msg="Starting D.R.O.N.A. ROS2 side for Isaac Sim (use_sim_time=true). "
                    "Launch the Isaac stage separately - see docs/sim_setup_isaac.md."),
        rsp,
        perception,
        policy,
        advising,
        orchestrator,
    ])
