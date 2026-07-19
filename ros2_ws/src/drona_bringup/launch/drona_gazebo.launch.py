"""
D.R.O.N.A. in Gazebo Harmonic (gz sim) - locally-runnable simulation.

This is the low-VRAM alternative to Isaac Sim: Gazebo Harmonic runs on CPU/iGPU
and is the recommended sim for the student's GTX-1650 dev box.

Brings up the full simulation mirror of the deployment stack:
    - robot_state_publisher (D.R.O.N.A. humanoid URDF, camera + gz control on)
    - gz sim with the drona_advising world (physics + sensors systems, desk,
      student figure at conversation distance)
    - the model spawned on the desk from /robot_description
    - ros_gz_bridge: /clock, gz joint states, head-camera image + camera_info,
      and the six per-joint position commands
    - gz_joint_relay: /drona/joint_states -> per-joint gz commands, so the gz
      model performs exactly what the policy publishes
    - the D.R.O.N.A. nodes in sim mode (use_sim_time), with perception consuming
      the SIMULATED camera via image_topic
    - diagnostics_node -> /diagnostics

Prerequisites (Ubuntu 24.04 + ROS2 Jazzy):
    sudo apt install ros-jazzy-ros-gz gz-harmonic
See docs/sim_setup_gazebo.md for the full guide.

On Windows with no dual-boot: run this inside WSL2 (Ubuntu 24.04); Windows 11's
WSLg renders the GUI window. If GL fails under WSL, `export LIBGL_ALWAYS_SOFTWARE=1`
or pass headless:=true. Full WSL guide: docs/wsl_setup.md.

Usage:
    ros2 launch drona_bringup drona_gazebo.launch.py
    ros2 launch drona_bringup drona_gazebo.launch.py headless:=true
    ros2 launch drona_bringup drona_gazebo.launch.py use_rviz:=true
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
from launch_ros.parameter_descriptions import ParameterValue

_JOINTS = ["j0_base_yaw", "j1_shoulder", "j2_elbow",
           "j3_wrist_pitch", "j4_wrist_roll", "j5_gripper"]


def generate_launch_description() -> LaunchDescription:
    desc_share = get_package_share_directory("drona_description")
    bringup_share = get_package_share_directory("drona_bringup")
    urdf = os.path.join(desc_share, "urdf", "drona_humanoid.urdf.xacro")
    rviz_config = os.path.join(desc_share, "rviz", "drona.rviz")
    params_file = os.path.join(bringup_share, "config", "params.yaml")
    world = os.path.join(bringup_share, "worlds", "drona_advising.sdf")

    headless = LaunchConfiguration("headless")
    use_rviz = LaunchConfiguration("use_rviz")
    advisor_remote_url = LaunchConfiguration("advisor_remote_url")
    mobile = LaunchConfiguration("mobile")
    args = [
        DeclareLaunchArgument("headless", default_value="false",
                              description="Run gz sim without the GUI (server only)"),
        DeclareLaunchArgument("use_rviz", default_value="false",
                              description="Also open RViz2 (TF + camera view)"),
        DeclareLaunchArgument(
            "advisor_remote_url", default_value="",
            description="GPU-served advising API URL (e.g. the Colab T4 tunnel). "
                        "Empty = run the advising engine in-process."),
        DeclareLaunchArgument(
            "mobile", default_value="false",
            description="Wheeled mobile base: the robot spawns on the floor and "
                        "drives to the student (approach_node -> /cmd_vel) instead "
                        "of sitting on the desk."),
    ]

    sim_time = {"use_sim_time": True}
    robot_description = {
        # ROS2 Jazzy parses parameter values as YAML; the xacro-generated URDF
        # is a plain string, so it must be declared with value_type=str or the
        # launch aborts with "Unable to parse the value of parameter
        # robot_description as yaml".
        "robot_description": ParameterValue(
            Command(["xacro ", urdf,
                     " use_gz_camera:=true use_gz_control:=true",
                     " use_mobile_base:=", mobile]),
            value_type=str,
        ),
        **sim_time,
    }

    rsp = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[robot_description],
        output="screen",
    )

    # Drive TF from the policy's joint stream (same source as deployment).
    jsp = Node(
        package="joint_state_publisher",
        executable="joint_state_publisher",
        parameters=[{"source_list": ["/drona/joint_states"]}, sim_time],
        output="screen",
    )

    # gz sim via ros_gz_sim; -r runs immediately, -s is server-only (headless).
    gz_args = PythonExpression(
        ["('-r -s ' if '", headless, "' == 'true' else '-r ') + '", world, "'"]
    )
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
        ),
        launch_arguments={"gz_args": gz_args}.items(),
    )

    # Desk mode spawns on the desk top (z = 0.72) so the head camera clears the
    # desk; the mobile base stands on the floor and drives (z = 0.08, wheel
    # radius clearance) - spawning it at desk height would drop it onto the desk.
    spawn_z = PythonExpression(["'0.08' if '", mobile, "' == 'true' else '0.72'"])
    spawn = Node(
        package="ros_gz_sim",
        executable="create",
        arguments=["-topic", "robot_description", "-name", "drona_humanoid",
                   "-z", spawn_z],
        output="screen",
    )

    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
            "/world/drona_advising/model/drona_humanoid/joint_state"
            "@sensor_msgs/msg/JointState[gz.msgs.Model",
            "/drona/camera/image_raw@sensor_msgs/msg/Image[gz.msgs.Image",
            "/drona/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo",
            # ROS -> GZ per-joint position commands (gz_joint_relay output).
            *[f"/drona/gz/{j}_cmd@std_msgs/msg/Float64]gz.msgs.Double" for j in _JOINTS],
            # Mobile base: ROS -> GZ velocity commands, GZ -> ROS odometry.
            # Inert when mobile:=false (no DiffDrive plugin is loaded), so these
            # can be bridged unconditionally.
            "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist",
            "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry",
        ],
        parameters=[sim_time],
        output="screen",
    )

    relay = Node(
        package="drona_ros",
        executable="gz_joint_relay",
        name="drona_gz_joint_relay",
        parameters=[sim_time],
        output="screen",
    )

    # D.R.O.N.A. cognition + interaction nodes (sim mode, sim clock).
    common = dict(package="drona_ros", parameters=[params_file, sim_time], output="screen")
    perception = Node(
        executable="perception_node", name="drona_perception_node",
        package="drona_ros",
        # Consume the SIMULATED camera - same MediaPipe pipeline as hardware.
        parameters=[params_file, sim_time, {"image_topic": "/drona/camera/image_raw"}],
        output="screen",
    )
    policy = Node(executable="policy_node", name="drona_policy_node", **common)
    advising = Node(
        package="drona_ros", executable="advising_node", name="drona_advising_node",
        parameters=[params_file, sim_time,
                    {"advisor_remote_url": advisor_remote_url}],
        output="screen",
    )
    orchestrator = Node(executable="orchestrator_node", name="drona_orchestrator_node", **common)
    diagnostics = Node(executable="diagnostics_node", name="drona_diagnostics_node", **common)
    # gesture_node consumes /drona/gesture_command (what the orchestrator emits)
    # and streams /drona/joint_states -> gz_joint_relay -> the arm. In sim it uses
    # the SimArmInterface (use_hardware:=false), so no hardware is touched. Without
    # this node the orchestrator's greet/nod commands would go unconsumed.
    gesture = Node(
        package="drona_ros", executable="gesture_node", name="drona_gesture_node",
        parameters=[params_file, sim_time, {"use_hardware": False}],
        output="screen",
    )
    # Mobile-base locomotion: drives toward the student on /cmd_vel and stops at
    # conversation range. Only launched with mobile:=true (no base otherwise).
    approach = Node(
        package="drona_ros", executable="approach_node", name="drona_approach_node",
        parameters=[params_file, sim_time],
        condition=IfCondition(mobile),
        output="screen",
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        arguments=["-d", rviz_config],
        parameters=[sim_time],
        condition=IfCondition(use_rviz),
        output="screen",
    )

    return LaunchDescription([
        *args,
        LogInfo(msg="Starting D.R.O.N.A. in Gazebo Harmonic (drona_advising world)"),
        rsp,
        jsp,
        gz_sim,
        spawn,
        bridge,
        relay,
        perception,
        policy,
        gesture,
        approach,
        advising,
        orchestrator,
        diagnostics,
        rviz,
    ])
