"""
D.R.O.N.A. EDGE tier - perception only, for a Raspberry Pi with a USB camera.

This is the hardware-in-the-loop entry point: the Pi watches a real student with
a real camera and publishes engagement onto the ROS2 graph, while the robot
(Gazebo or hardware) and the advising brain run on other machines. Nothing else
runs here, so it stays light enough for a Pi.

    Pi (this launch)            dev box                     GPU
    perception_node       ->    orchestrator/gestures  ->   /advise brain
    USB cam + MediaPipe        (drona_gazebo.launch.py)     (Colab T4)

Usage on the Pi:
    # same ROS_DOMAIN_ID on BOTH machines, and no firewall between them
    export ROS_DOMAIN_ID=42
    ros2 launch drona_bringup drona_edge.launch.py

    # pick a specific camera / force the backend
    ros2 launch drona_bringup drona_edge.launch.py camera_index:=1 camera_backend:=opencv

Arguments:
    camera_index   : 0        /dev/videoN index of the USB camera
    camera_backend : auto     auto | opencv (USB) | picamera2 (Pi CSI ribbon)
    detection_hz   : 10.0     detection rate (10 Hz is plenty and keeps the Pi cool)
    log_level      : info

IMPORTANT: do not also run a perception_node on the dev box at the same time -
two publishers on /drona/engagement will fight. Run the Pi's node, or the sim's
camera node, not both.
"""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    camera_index = LaunchConfiguration("camera_index")
    camera_backend = LaunchConfiguration("camera_backend")
    detection_hz = LaunchConfiguration("detection_hz")
    log_level = LaunchConfiguration("log_level")

    args = [
        DeclareLaunchArgument("camera_index", default_value="0",
                              description="/dev/videoN index of the USB camera"),
        DeclareLaunchArgument("camera_backend", default_value="auto",
                              description="auto | opencv (USB) | picamera2 (Pi CSI)"),
        DeclareLaunchArgument("detection_hz", default_value="10.0",
                              description="Face-detection rate in Hz"),
        DeclareLaunchArgument("log_level", default_value="info"),
    ]

    perception = Node(
        package="drona_ros",
        executable="perception_node",
        name="drona_perception_node",
        # use_camera:=true and NO image_topic -> open the local camera.
        parameters=[{
            "use_camera": True,
            "image_topic": "",
            "camera_index": camera_index,
            "camera_backend": camera_backend,
            "detection_hz": detection_hz,
        }],
        arguments=["--ros-args", "--log-level", log_level],
        output="screen",
    )

    return LaunchDescription([
        *args,
        LogInfo(msg="D.R.O.N.A. EDGE: perception on a real camera -> /drona/engagement"),
        LogInfo(msg="Ensure ROS_DOMAIN_ID matches the robot machine."),
        perception,
    ])
