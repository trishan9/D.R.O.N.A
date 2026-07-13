# D.R.O.N.A. ROS 2 workspace

Production ROS 2 (Humble) stack for the embodied advising robot. Everything is
developed and validated **simulation-first**: the identical node graph runs
against the stub environment, Gazebo Harmonic, NVIDIA Isaac Sim, and the
physical robot - only a parameter file changes between them.

Full interface contract (every topic / service / action / message):
[`../docs/ros2_topics_actions.md`](../docs/ros2_topics_actions.md).

## Packages

| Package | Type | Contents |
|---|---|---|
| `drona_msgs` | CMake (rosidl) | 8 messages, 2 services, 1 action (`ExecuteGesture`) - 1:1 mirrors of the Pydantic contracts in `drona/contracts/` |
| `drona_description` | CMake | `drona_humanoid.urdf.xacro` (torso + head + 6-DOF arm + camera frames, gz-sim sensor & PID-controller gates), RViz config, display launch |
| `drona_ros` | ament_python | 7 nodes - thin transport wrappers; all algorithmic logic stays in the `drona` Python package where the 400+ unit tests cover it |
| `drona_bringup` | ament_python | 6 launch files, parameter files (`params.yaml` sim/dev, `hardware.yaml` deployment), the Gazebo world, the Isaac stage script |

## Nodes

| Node | Role | Interface |
|---|---|---|
| `perception_node` | engagement detection | pub `/drona/engagement`; frame source = stub / local webcam / **any `sensor_msgs/Image` topic** (`image_topic` param - this is how it consumes the simulated camera) |
| `policy_node` | gesture **action server** | `/drona/execute_gesture_action` with streaming feedback + preemption; policy tiers: ACT → **exported ONNX** → torch BC → keyframe |
| `gesture_node` | gesture topic + blocking service | `/drona/gesture_command`, `/drona/execute_gesture`; owns the physical arm in hardware mode |
| `advising_node` | RAG advising service | `/drona/advise` (local LLM, no cloud) |
| `orchestrator_node` | session FSM | idle→greet→assess→advise→close, driven by engagement |
| `diagnostics_node` | health monitor | `/diagnostics` (`diagnostic_msgs`) - per-stream liveness at 1 Hz for RViz/rqt/web |
| `gz_joint_relay` | sim only | fans `/drona/joint_states` out to the gz per-joint PID controllers so the simulated robot physically performs every gesture |

## Simulation-first workflow

```
1. stub (any OS, no sim)     ros2 launch drona_bringup drona_system.launch.py use_rviz:=true
2. Gazebo Harmonic (WSL2 ok) ros2 launch drona_bringup drona_gazebo.launch.py
3. Isaac Sim (RTX GPU)       ./python.sh drona_bringup/isaac/drona_isaac_stage.py
                             + ros2 launch drona_bringup drona_isaac.launch.py
4. hardware                  ros2 launch drona_bringup drona_hardware.launch.py
```

The Gazebo stage is a faithful deployment mirror:
- `worlds/drona_advising.sdf` loads the **Sensors** system (ogre2) plus a desk
  and a student-sized figure at conversation distance;
- the robot spawns on the desk and its joints are actuated by gz PID
  controllers fed from the same `/drona/joint_states` stream used everywhere;
- the head camera renders to `/drona/camera/image_raw`, which `perception_node`
  consumes through the same MediaPipe code path as the real webcam;
- all nodes run on `/clock` (`use_sim_time`).

Build + run (Ubuntu 22.04 or WSL2, ROS 2 Humble sourced):

```bash
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true rosbridge:=true
```

## Model deployment

Policies ship in deployment formats - the robot runtime does not need torch:

```bash
python scripts/train_bc_gesture.py          # trains  data/checkpoints/bc/<gesture>/
python scripts/export_policies.py           # exports model.onnx + model.torchscript.pt
                                            # + export_manifest.json (verified parity)
```

`PolicyRouter` (used by `policy_node` and `gesture_node`) selects per gesture:
**ACT checkpoint → ONNX (onnxruntime) → torch BC → keyframe**, logging which
tier is active. The same checkpoints directory travels from Colab (training)
to sim to robot unchanged.

## Deploying to the physical robot

Software is done; connecting hardware is configuration only:

1. Plug in the SO-100 arm (U2D2 USB) and webcam.
2. `python scripts/export_policies.py` (once, after training).
3. Calibrate once: verify `REST_POSE` against the physical home position
   (procedure in `drona_ros/arm_interface.py`).
4. Tune `config/hardware.yaml` if needed (camera index, timeouts). The serial
   port is a launch argument: `arm_port:=/dev/ttyUSB0`.
5. `ros2 launch drona_bringup drona_hardware.launch.py use_rviz:=true`

`/diagnostics` tells you immediately which component (perception / policy /
orchestrator / advising) is silent if anything is mis-wired.

## Scope note

D.R.O.N.A. is a **stationary advising kiosk** (desk-mounted 6-DOF arm + head
camera). There is intentionally no LiDAR/IMU/Nav2/SLAM layer - the robot does
not navigate. The TF tree is `base_link → arm chain + head → camera_link →
camera_optical_frame` (REP-103 optical convention), published by
`robot_state_publisher` from the same URDF in every mode.
