# NVIDIA Isaac Sim Setup - D.R.O.N.A.

Isaac Sim is D.R.O.N.A.'s **high-fidelity** simulator, used for photorealistic
rendering and accurate articulation dynamics in the evaluation chapter. It is
**optional**: everything in the thesis can be demonstrated in Gazebo Harmonic
(see `sim_setup_gazebo.md`), which is the recommended path on modest hardware.

> ⚠️ **Hardware requirement: an RTX-class GPU with ≥ 8 GB VRAM.**
> Isaac Sim uses the Omniverse **RTX renderer**, so it needs RTX ray-tracing
> cores - a **GTX** 1650 (4 GB, no RTX cores) **cannot** run it, with or without
> WSL2. So on this machine Isaac Sim is **cloud-only** (recipe in §4); the local
> embodied demo is **Gazebo Harmonic in WSL2** (`sim_setup_gazebo.md`) plus the
> in-browser **Robot Control** page in the Next.js app (faithful 6-DOF twin).
>
> **About WSL2:** NVIDIA *does* officially support Isaac Sim on WSL2 (Ubuntu
> 24.04) - so if you later get an RTX card (≥8 GB), you can run §3 inside WSL2
> exactly as written. The blocker here is the GPU class (GTX vs RTX), not WSL.

---

## 1. Install Isaac Sim 4.x

Follow NVIDIA's official installer (Omniverse Launcher or the container). Isaac
Sim ships its **own Python** (`python.sh`) - this is separate from the ROS2
Python environment.

```bash
# Typical local install path
cd ~/.local/share/ov/pkg/isaac-sim-4.*
./python.sh -c "import isaacsim; print('Isaac OK')"
```

Enable the ROS2 bridge extension (`omni.isaac.ros2_bridge`) - the stage script
does this automatically, but it must be available in your Isaac install.

---

## 2. Architecture: two processes, one bridge

Isaac runs in its own Python; the D.R.O.N.A. nodes run in ROS2 Jazzy. They talk
over the **Isaac ROS2 bridge**:

```
┌────────────────────────┐         ROS2 (DDS)          ┌────────────────────────┐
│  Isaac Sim (python.sh) │  /clock, /isaac/joint_state │   ROS2 Jazzy world     │
│  drona_isaac_stage.py  │ ──────────────────────────▶ │  drona_isaac.launch.py  │
│  • URDF articulation   │ ◀────────────────────────── │  • policy/advising/...  │
│  • OmniGraph ROS2 nodes │    /drona/joint_states      │  • robot_state_publisher│
└────────────────────────┘                             └────────────────────────┘
```

---

## 3. Run (local RTX GPU)

```bash
# Pre-expand xacro → plain URDF (Isaac importer wants URDF, not xacro):
xacro <repo>/ros2_ws/src/drona_description/urdf/drona_humanoid.urdf.xacro \
  > /tmp/drona_humanoid.urdf

# Terminal 1 - Isaac stage (Isaac python):
cd ~/.local/share/ov/pkg/isaac-sim-4.*
./python.sh <repo>/ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py \
  --urdf /tmp/drona_humanoid.urdf

# Terminal 2 - D.R.O.N.A. ROS2 side (ROS2 sourced):
cd <repo>/ros2_ws && source install/setup.bash
ros2 launch drona_bringup drona_isaac.launch.py
```

`use_sim_time:=true` is set for all nodes so they follow Isaac's `/clock`.

Send a gesture exactly as in Gazebo:

```bash
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

---

## 4. Cloud GPU recipe (no local RTX)

For machines without a capable GPU (incl. the GTX-1650):

1. **Provision** a cloud GPU VM with ≥ 16 GB VRAM (e.g. an `L4`/`A10G`/`T4` is
   borderline; prefer `A10`/`L4`). Options: AWS `g5.xlarge`, GCP `g2-standard`,
   Lambda Cloud, or **Isaac Sim on Omniverse Cloud**.
2. **Use the Isaac Sim container**:
   ```bash
   docker pull nvcr.io/nvidia/isaac-sim:4.5.0
   docker run --gpus all -it --rm \
     -v <repo>:/workspace/drona \
     nvcr.io/nvidia/isaac-sim:4.5.0 \
     ./python.sh /workspace/drona/ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py \
       --urdf /workspace/drona/.../drona_humanoid.urdf --headless
   ```
3. **Bridge ROS2** either inside the same container (install ros-jazzy) or via a
   second container on the same Docker network with `ROS_DOMAIN_ID` matched.
4. **Record** the session as a rosbag (see `ros2_topics_actions.md`) and pull it
   back to the laptop for offline analysis - no local GPU needed for the writeup.

> Colab note: Colab does not expose a full desktop GPU context suitable for
> Isaac's renderer; prefer a proper cloud VM or the NGC container above.

---

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `omni/isaacsim not found` | you ran with the wrong python - use Isaac's `python.sh` |
| URDF import fails on xacro | pre-expand with `xacro` first (see §3) |
| No `/clock` in ROS2 | confirm `omni.isaac.ros2_bridge` enabled + `ROS_DOMAIN_ID` matches |
| Out of memory | reduce viewport/render settings or run `--headless` |
