# Gazebo Harmonic Setup - D.R.O.N.A.

Gazebo Harmonic (`gz sim`) is D.R.O.N.A.'s **locally-runnable** simulator. Unlike
Isaac Sim it runs comfortably on CPU / integrated graphics, so it is the
recommended sim for the student's **GTX-1650 (4 GB)** dev box and for CI smoke
tests.

> **Platform:** Ubuntu 22.04 LTS + ROS2 Humble. **On Windows with no dual-boot,
> run this inside WSL2** - Windows 11's WSLg shows the Gazebo/RViz windows on your
> desktop with no extra X-server. Do `docs/wsl_setup.md` first, then every command
> below is identical. Phase 1 sim (`scripts/run_simulation.py`) is the
> Windows-native path that needs no ROS2.

---

## 1. Install

```bash
# ROS2 Humble pairs with Gazebo Harmonic via the ros_gz bridge.
sudo apt update
sudo apt install -y ros-humble-ros-gz gz-harmonic \
  ros-humble-robot-state-publisher ros-humble-joint-state-publisher \
  ros-humble-xacro ros-humble-rviz2
```

Verify:

```bash
gz sim --version          # expect Harmonic (8.x)
ros2 pkg list | grep ros_gz
```

---

## 2. Build the workspace

```bash
cd <repo>/ros2_ws
colcon build --symlink-install
source install/setup.bash
```

This builds `drona_msgs` (incl. the `ExecuteGesture` action), `drona_ros`
(nodes), `drona_description` (URDF), and `drona_bringup` (launch).

---

## 3. Launch

```bash
ros2 launch drona_bringup drona_gazebo.launch.py
# headless (server only, no GUI):
ros2 launch drona_bringup drona_gazebo.launch.py headless:=true
```

This starts:

| Component | Role |
|---|---|
| `robot_state_publisher` | publishes TF from the humanoid URDF |
| `gz sim` (empty world) | physics + rendering |
| `ros_gz_sim create` | spawns the model from `/robot_description` |
| `ros_gz_bridge` | bridges `/clock` and joint state |
| `perception/policy/advising/orchestrator` | the D.R.O.N.A. stack (sim mode) |

---

## 4. Drive a gesture

In another sourced terminal, send a gesture **action** goal (streams feedback):

```bash
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

You should see per-frame feedback (`progress`, `joint_positions`) and the arm
move in the Gazebo GUI.

---

## 5. Full actuation (optional)

The URDF ships with valid inertials so it is physically simulable. For Gazebo to
*actuate* the joints from `/drona/joint_states` (rather than just visualise TF),
add a `gz_ros2_control` plugin + a `ros2_control` block to
`drona_humanoid.urdf.xacro` and a controllers YAML. For the thesis demo, the
kinematic visualisation (TF driven by `robot_state_publisher`) is sufficient to
show gesture quality; the trajectory smoothness metric (C3) is measured in the
`StubEnv`/MuJoCo rollouts of `drona.interaction.sim_eval`, not in Gazebo.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `gz sim` opens then closes | GPU/driver issue - try `headless:=true` |
| **WSL2:** black screen / GL3 / Ogre2 error | `export LIBGL_ALWAYS_SOFTWARE=1` (and `export QT_QPA_PLATFORM=xcb`), relaunch. See `wsl_setup.md` §7. |
| **WSL2:** no window appears | `wsl --update` then `wsl --shutdown` (PowerShell), reopen Ubuntu - WSLg must be current. |
| Model not visible | check `ros2 topic echo /robot_description` is non-empty; xacro installed |
| No `/clock` | confirm `ros_gz_bridge` started and world name matches `empty` |
| Joints don't move | expected without `gz_ros2_control`; TF still updates from joint states |
