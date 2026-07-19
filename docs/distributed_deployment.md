# D.R.O.N.A. — Distributed Deployment, Edge Computing & Hardware-in-the-Loop

This document describes how D.R.O.N.A. is deployed as a **three-tier distributed
robotic system**, why that architecture is the defensible engineering choice for
this project, and exactly how to demonstrate it with a single Raspberry Pi.

It is written to be citable from the dissertation: every claim below is backed by
a script in `scripts/` that reproduces it.

---

## 1. Why distributed, and why it matters

A bias-aware advising robot has three workloads with incompatible resource
profiles:

| Workload | Needs | Cannot live on |
|---|---|---|
| **Perception** (face → engagement) | a camera, ~5 ms/frame CPU | a GPU server (no camera in the room) |
| **Embodiment** (gestures, locomotion, safety) | real-time-ish control loop, low latency | a cloud VM (network jitter breaks control) |
| **Advising brain** (RAG + 4B LLM) | ~8 GB VRAM, 2.3 GB reranker, ChromaDB | a Raspberry Pi or a 4 GB robot SBC |

Forcing all three onto one machine is what makes student robotics projects fail:
either the brain is too weak to be interesting, or the robot is too expensive to
build. D.R.O.N.A. splits them across tiers connected by ROS 2 and one HTTP call:

```
  TIER 1: EDGE                TIER 2: ROBOT                TIER 3: BRAIN
  Raspberry Pi + USB cam      dev box / robot SBC          Colab T4 / any GPU
  ──────────────────────      ─────────────────────        ──────────────────
  perception_node             orchestrator_node            FastAPI /advise
  MediaPipe BlazeFace         gesture_node                 Qwen3-4B + LoRA
  ~230 KB model, CPU          approach_node (/cmd_vel)     hybrid RAG + rerank
  publishes                   policy_node                  bias detection
  /drona/engagement           gz sim or real hardware
          │                            │                            │
          └──────── ROS 2 DDS ─────────┴─────── HTTPS /advise ──────┘
                  (same LAN, ROS_DOMAIN_ID)      (RemoteAdvisor)
```

**The thesis claim this supports:** the system is *hardware-agnostic* and
*deployment-flexible* — the same code runs entirely in simulation, entirely on
one laptop, or split across an edge device, a robot, and a cloud GPU, with no
source changes. Only launch arguments differ.

---

## 2. What makes it genuinely hardware-agnostic

This is demonstrated, not asserted. Three abstraction seams do the work:

### 2.1 Locomotion: `geometry_msgs/Twist` on `/cmd_vel`
`approach_node` publishes the universal ROS 2 mobile-base command. Anything that
consumes `/cmd_vel` is drivable by it unchanged: the Gazebo `DiffDrive` plugin,
a TurtleBot, a TIAGo, a Pepper via `naoqi_driver`. The robot never knows what
base it is on.

### 2.2 Manipulation: `sensor_msgs/JointState` + an arm interface
`gesture_node` streams `/drona/joint_states`. Downstream, either:
- `gz_joint_relay` → Gazebo joint controllers (simulation), or
- `SO100ArmInterface` → a real serial servo arm (hardware),

selected by `use_hardware:=true|false`. `SimArmInterface` and
`SO100ArmInterface` implement the same interface, so the gesture policy is
identical in both paths — this is the digital-twin property.

### 2.3 Cognition: `RemoteAdvisor` over HTTP
`drona/advising/remote.py` makes the brain a network dependency rather than a
hardware requirement. `make_advisor(url)` returns a thin HTTP client when a URL
is configured and the in-process engine otherwise — one decision point, no
conditional logic scattered through the nodes.

---

## 3. Hardware-in-the-loop: the Raspberry Pi demonstration

**The point:** rather than build a full physical robot (high cost, high risk,
and if it half-works it weakens the dissertation), run the robot in
high-fidelity simulation and make **one tier genuinely physical**. A real camera
watching a real person drives a simulated robot in real time. This proves the
distribution is real — the tiers are separate processes on separate machines
exchanging real messages — while keeping the demo reliable.

### 3.1 Pi setup (once) — one command

```bash
# On the Raspberry Pi (64-bit Pi OS Bookworm, Pi 4/5), USB camera plugged in
git clone https://github.com/trishan9/D.R.O.N.A.git && cd D.R.O.N.A
sudo bash scripts/setup_pi_edge.sh
```

That installs `ros-jazzy-ros-base` (no Gazebo — the Pi never simulates), the
perception Python deps, builds the workspace, wires `~/.bashrc`, adds you to the
`video` group, and reports which `/dev/video*` devices it can see.

> `numpy<2` is mandatory and the script pins it: ROS 2 Jazzy ships numpy 1.26 and
> MediaPipe's matplotlib dependency is compiled against numpy 1.x. numpy 2 fails
> with `numpy.core.multiarray failed to import`.

**Camera support.** A **USB webcam** (the normal case) is opened with OpenCV. A Pi
Camera Module on the **CSI ribbon** is *not* reachable through OpenCV on Bookworm
(it moved to libcamera), so `CameraSource` falls back to **picamera2** for that.
`camera_backend:=auto` tries USB first; force it with `opencv` or `picamera2`.

### 3.2 Put both machines on the same ROS 2 graph

ROS 2 discovers peers over DDS multicast on the LAN. Both machines need the
**same domain ID** and no firewall between them:

```bash
# on BOTH the Pi and the dev box (same value, 0-101)
export ROS_DOMAIN_ID=42
# if multicast is unreliable on your college Wi-Fi, prefer wired or set
# ROS_STATIC_PEERS / a discovery server. Verify with: ros2 topic list
```

### 3.3 Run it

```bash
# Pi (tier 1) - real USB camera, real face detection
ros2 launch drona_bringup drona_edge.launch.py
#   options: camera_index:=1  camera_backend:=opencv  detection_hz:=10.0

# dev box (tier 2) - the robot, in simulation
ros2 launch drona_bringup drona_gazebo.launch.py mobile:=true \
    advisor_remote_url:=https://<your-tunnel>.trycloudflare.com
```

Confirm the Pi is publishing (from either machine):

```bash
ros2 topic echo /drona/engagement
```

If no camera is found, the node logs exactly what it tried and falls back to the
scripted stub detector rather than dying — so the graph stays alive and you can
debug the camera separately.

Now walk in front of the Pi's camera. The simulated robot detects you, **drives
toward you**, stops at conversation distance, greets you, and answers with the
fine-tuned model running on the T4.

**Do not launch `perception_node` on the dev box at the same time** — two
publishers on `/drona/engagement` will fight. Either run the Pi's node, or the
sim's camera node, not both.

---

## 4. Graceful degradation (a systems contribution, not an accident)

A distributed robot must not become a brick when a tier disappears. D.R.O.N.A.
degrades tier by tier, and this is deliberate and tested:

| Failure | Behaviour | Where |
|---|---|---|
| Brain unreachable (tunnel dies, Colab drops) | Returns a **refusal** response and asks the student to see a human advisor; the robot keeps greeting and gesturing | `RemoteAdvisor.advise` — every error path returns a refusal, never raises (`tests/test_remote_advisor.py`) |
| Perception dies / no student | `approach_node` **stops the base** (fail-safe to stationary, never "keep driving") | `ApproachNode._control_tick` |
| No trained policy checkpoint | Falls back down the policy tiers: SmolVLA → ACT → ONNX BC → torch BC → **keyframe** (always available) | `PolicyRouter` |
| No MediaPipe / no camera | `StubDetector` replays a scripted engagement sequence so the loop still demos | `make_detector(prefer_mediapipe=False)` |
| Retrieval coverage too low | Refuses rather than hallucinating | `AdvisingEngine.advise` coverage gate |

This is the "never leave the student stranded, never fabricate advice" property
that an advising robot ethically requires.

---

## 5. Measured performance

Reproduce with `bash scripts/run_latency_benchmark.sh 5` (writes
`reports/latency_sim.json`). Measured on the development box (4 GB WSL 2,
Gazebo Harmonic headless, 5 trials plus an excluded warm-up):

| Stage | Mean | p95 | What it covers |
|---|---|---|---|
| perception → decision | **6.9 ms** | 13.0 ms | engagement received → session machine → gesture dispatched |
| decision → motion | **1.7 ms** | 3.9 ms | gesture command → first joint setpoint (warm) |
| full reaction (cold) | **~737 ms** | — | includes the one-time gesture-policy load |

Interpretation for the dissertation: **the robot's own decision path is
sub-10 ms** — orchestration is nowhere near the bottleneck. The user-perceived
latency is dominated by (a) a one-time policy load, and (b) LLM generation on the
brain tier, which is exactly why the brain is the tier that was moved to a GPU.

The warm-up is excluded from the statistics because the first gesture pays a
lazy-initialisation cost (~0.7–1.8 s) that is not representative of steady state.

---

## 6. Reproducing every claim

| Claim | Command |
|---|---|
| Sim boots, robot spawns, bridges up | `bash scripts/smoke_test_sim.sh` |
| Arm tracks commanded poses | `bash scripts/test_gesture_motion.sh` |
| Engagement → greeting → arm motion | `bash scripts/test_interaction_loop.sh` |
| Robot drives to student, stops, fail-safes | `bash scripts/test_locomotion.sh` |
| Cognitive bias detection (C2) | `python3 scripts/demo_bias_detection.py` |
| Reaction latency | `bash scripts/run_latency_benchmark.sh 5` |
| Remote brain degrades safely | `pytest tests/test_remote_advisor.py` |

---

## 7. Honest scope boundaries

State these in the dissertation rather than letting an examiner find them:

- **Wheeled, not bipedal.** The mobile base is differential-drive. This matches
  every deployed social service robot (Pepper, TIAGo, temi); bipedal locomotion
  is a separate research programme and contributes nothing to bias-aware
  advising.
- **Range-only approach control.** A monocular camera gives a distance proxy, not
  a bearing, so `approach_node` servos on range alone. Full navigation around
  obstacles is Nav2's job — and Nav2 consumes the same `/cmd_vel`, so it drops in
  without touching the behaviour layer.
- **Simulated student.** The Gazebo `student_figure` is geometry, not a
  photorealistic human, so MediaPipe cannot detect a face from the simulated
  camera. This is precisely why the Pi hardware-in-the-loop path exists: real
  faces come from a real camera.
- **Isaac Sim not run locally.** It needs an RTX GPU and ~32 GB RAM; the stage
  builder (`ros2_ws/src/drona_bringup/isaac/`) is written and ready for a machine
  that has them.
