# ROS2 Setup Guide

D.R.O.N.A. Phase 2 uses **ROS2 Humble** on **Ubuntu 22.04 LTS** (the officially supported combination). This guide covers installing ROS2, building the workspace, and running the nodes.

> **Windows users:** Phase 1 simulation (`scripts/run_simulation.py`) runs natively on Windows. For Phase 2, use WSL2 with Ubuntu 22.04 or a dedicated Ubuntu machine.

---

## Prerequisites

- Ubuntu 22.04 LTS (bare-metal or WSL2 with USB passthrough)
- Python 3.10 (ships with Ubuntu 22.04)
- The D.R.O.N.A. repository cloned and Python dependencies installed

---

## 1. Install ROS2 Humble

Follow the official Humble installation guide exactly. The quick path:

```bash
# Locale
sudo apt update && sudo apt install -y locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Add ROS2 apt repository
sudo apt install -y software-properties-common curl
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc \
  | sudo apt-key add -
sudo sh -c 'echo "deb [arch=$(dpkg --print-architecture)] http://packages.ros.org/ros2/ubuntu \
  $(. /etc/os-release && echo $UBUNTU_CODENAME) main" > /etc/apt/sources.list.d/ros2.list'

# Install
sudo apt update
sudo apt install -y ros-humble-desktop ros-humble-ros-base \
  ros-dev-tools python3-colcon-common-extensions python3-rosdep

# Init rosdep
sudo rosdep init
rosdep update

# Source in every shell (add to ~/.bashrc)
source /opt/ros/humble/setup.bash
```

---

## 2. Build the D.R.O.N.A. Workspace

```bash
cd ~/D.R.O.N.A/ros2_ws

# Install ROS2 package dependencies
rosdep install --from-paths src --ignore-src -r -y

# Build
colcon build --symlink-install --packages-select drona_msgs drona_ros drona_bringup

# Source the workspace (add to ~/.bashrc)
source ~/D.R.O.N.A/ros2_ws/install/setup.bash
```

Verify the build:

```bash
ros2 pkg list | grep drona
# drona_bringup
# drona_msgs
# drona_ros
```

---

## 3. Run the Simulation Launch

The simulation launch starts all four nodes in software-only mode (no camera, no physical arm):

```bash
ros2 launch drona_bringup drona_sim.launch.py
```

You should see all four nodes start:
- `drona_advising_node`
- `drona_gesture_node`
- `drona_perception_node`
- `drona_orchestrator_node`

Check topics are active:

```bash
ros2 topic list
# /drona/engagement
# /drona/student_query
# /drona/advising_response
# /drona/gesture_command
# /drona/gesture_result
# /drona/joint_states
# /drona/session_state
```

---

## 4. Send a Test Query

While the nodes are running, in a second terminal:

```bash
source /opt/ros/humble/setup.bash
source ~/D.R.O.N.A/ros2_ws/install/setup.bash

ros2 topic pub --once /drona/student_query std_msgs/msg/String \
  '{data: "What career paths suit a Python developer in Nepal?"}'
```

Watch the advising node respond on `/drona/advising_response`:

```bash
ros2 topic echo /drona/advising_response drona_msgs/msg/AdvisingResponse
```

---

## 5. Run the Evaluation Launch

```bash
ros2 launch drona_bringup drona_evaluation.launch.py contributions:=c2,c3
```

This starts all four nodes then runs the evaluation harness. Results are saved to `data/evaluation/`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `package 'drona_msgs' not found` | Workspace not sourced | `source ros2_ws/install/setup.bash` |
| `rosidl_typesupport` errors | Colcon built with old cache | `rm -rf ros2_ws/build ros2_ws/install` and rebuild |
| Advising node slow to start | Embedding model downloading | Wait; model is cached after first run |
| Gesture node crashes | Missing checkpoint dir | Run `python scripts/train_act.py` or the KeyframePolicy fallback activates automatically |
| `No module named drona` | Python path | Install: `pip install -e .` from the repo root |

---

## Node Parameters

All node parameters are in `ros2_ws/src/drona_bringup/config/params.yaml` (sim) and `hardware.yaml` (real hardware). Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `use_camera` | `false` | Enable real MediaPipe webcam detector |
| `use_hardware` | `false` | Send commands to physical SO-100 arm |
| `arm_port` | `/dev/ttyUSB0` | Serial port for Dynamixel U2D2 adapter |
| `session_timeout_s` | `30.0` | Seconds before session times out |
| `perception_hz` | `10.0` | Detection frequency |
| `joint_state_hz` | `20.0` | Joint state publish frequency |
