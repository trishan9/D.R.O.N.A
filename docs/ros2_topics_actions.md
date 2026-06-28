# D.R.O.N.A. ROS2 Interface Reference - Topics, Services, Actions

This is the authoritative interface contract for the D.R.O.N.A. ROS2 graph
(`ros2_ws/`). Custom interfaces live in **`drona_msgs`** and mirror the Pydantic
contracts in `drona/contracts/` 1:1, so Phase 1 (Python) and Phase 2 (ROS2)
share one data model.

---

## Nodes

| Node | Package | Wraps | Role |
|---|---|---|---|
| `drona_perception_node` | `drona_ros` | `drona.perception` | Engagement estimation (MediaPipe / stub) |
| `drona_policy_node` | `drona_ros` | `drona.interaction` | Gesture **action server** (LeRobot/keyframe, streaming feedback) |
| `drona_gesture_node` | `drona_ros` | `drona.interaction.gesture_dispatcher` | Gesture topic + **service** (blocking) |
| `drona_advising_node` | `drona_ros` | `drona.advising` | Advising **service** (local LLM RAG) |
| `drona_orchestrator_node` | `drona_ros` | `drona.orchestrator` | Session state machine: idle→greet→assess→advise→close |
| `robot_state_publisher` | (upstream) | `drona_description` URDF | Publishes TF for RViz / sim |

---

## Topic graph

```
 perception_node ──/drona/engagement──▶ orchestrator_node
                                            │
            ┌───────────────────────────────┼─────────────────────────────┐
            │                               │                             │
   /drona/gesture_command         /drona/student_query          /drona/session_state
            │                               │                             │
            ▼                               ▼                             ▼
      gesture_node                    advising_node                   (monitors)
            │                               │
   /drona/joint_states            /drona/advising_response
            │                               │
            ▼                               ▼
   robot_state_publisher            orchestrator_node
   (→ /tf, RViz, sim)              (delivers + queues farewell)

   policy_node ──/drona/joint_states──▶ robot_state_publisher
   (action server; same joint stream during action rollouts)
```

---

## Topics

| Topic | Type | Publisher → Subscriber |
|---|---|---|
| `/drona/engagement` | `drona_msgs/EngagementDetection` | perception → orchestrator |
| `/drona/gesture_command` | `drona_msgs/GestureCommand` | orchestrator → gesture |
| `/drona/gesture_result` | `drona_msgs/GestureResult` | gesture → orchestrator |
| `/drona/student_query` | `drona_msgs/AdvisingQuery` | orchestrator → advising |
| `/drona/advising_response` | `drona_msgs/AdvisingResponse` | advising → orchestrator |
| `/drona/session_state` | `drona_msgs/SessionState` | orchestrator → (monitors) |
| `/drona/joint_states` | `sensor_msgs/JointState` | policy/gesture → robot_state_publisher |
| `/tf`, `/tf_static` | `tf2_msgs/TFMessage` | robot_state_publisher |
| `/robot_description` | `std_msgs/String` | robot_state_publisher |

---

## Services

| Service | Type | Server | Behaviour |
|---|---|---|---|
| `/drona/advise` | `drona_msgs/Advise` | advising_node | Run the advising pipeline, return `AdvisingResponse` |
| `/drona/execute_gesture` | `drona_msgs/ExecuteGesture` | gesture_node | Execute a gesture **blocking**, return `GestureResult` |

---

## Actions

| Action | Type | Server | Notes |
|---|---|---|---|
| `/drona/execute_gesture_action` | `drona_msgs/action/ExecuteGesture` | policy_node | Long-running gesture rollout with **feedback** + **cancellation** |

### `ExecuteGesture.action`

```
# Goal
string gesture_label      # greet | nod | point | idle | listen | farewell
float32 target_x          # optional POINT target (m)
float32 target_y
float32 target_z
string policy_hint        # "" | keyframe | act | diffusion
---
# Result
GestureResult result
bool success
string error
---
# Feedback (per control step)
float32 progress          # 0.0 .. 1.0
int32 current_frame
int32 total_frames
float32[] joint_positions # 6-DOF, radians
```

Send a goal with live feedback:

```bash
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

Cancel preempts the rollout; the server returns `success=false, error="cancelled"`.

---

## Joint convention

The 6-DOF arm joint names are shared across the URDF, the policies, and the
joint-state stream (`drona.interaction.demonstration.JOINT_NAMES`):

| Index | Joint | URDF type | Range |
|---|---|---|---|
| 0 | `j0_base_yaw` | revolute (z) | ±π |
| 1 | `j1_shoulder` | revolute (y) | ±π/2 |
| 2 | `j2_elbow` | revolute (y) | ±π |
| 3 | `j3_wrist_pitch` | revolute (y) | ±π/2 |
| 4 | `j4_wrist_roll` | revolute (z) | ±π |
| 5 | `j5_gripper` | prismatic (x) | 0 .. 1 |

---

## Launch files

| Launch | Package | Purpose |
|---|---|---|
| `drona_system.launch.py` | `drona_bringup` | **Full stack** + optional RViz + optional rosbag |
| `drona_sim.launch.py` | `drona_bringup` | Four nodes, stub/sim mode |
| `drona_gazebo.launch.py` | `drona_bringup` | Stack in Gazebo Harmonic |
| `drona_isaac.launch.py` | `drona_bringup` | ROS2 side for Isaac Sim (`use_sim_time`) |
| `drona_hardware.launch.py` | `drona_bringup` | Real SO-100 arm + camera |
| `drona_evaluation.launch.py` | `drona_bringup` | Evaluation harness wiring |
| `display.launch.py` | `drona_description` | RViz + robot_state_publisher (`gui:=true` for sliders) |

---

## Recording an end-to-end interaction (rosbag)

The full-system launch can capture every D.R.O.N.A. topic for replay / viva:

```bash
ros2 launch drona_bringup drona_system.launch.py record:=true bag_path:=demo_run
# … run an interaction (engagement → greet → advise → farewell) …
# Ctrl-C stops recording; replay with:
ros2 bag play demo_run
```

Recorded topics: `/drona/engagement`, `/drona/gesture_command`,
`/drona/gesture_result`, `/drona/student_query`, `/drona/advising_response`,
`/drona/session_state`, `/drona/joint_states`, `/tf`, `/tf_static`,
`/robot_description`.

Equivalently, record manually:

```bash
ros2 bag record -o demo_run \
  /drona/engagement /drona/gesture_command /drona/gesture_result \
  /drona/student_query /drona/advising_response /drona/session_state \
  /drona/joint_states /tf /tf_static /robot_description
```
