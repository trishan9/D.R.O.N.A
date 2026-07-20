# How you actually interact with D.R.O.N.A.

Three ways in, one way out. This is what to do once the sim is running
(see [RUN_THE_DASHBOARD.md](RUN_THE_DASHBOARD.md)).

---

## 1. The interaction loop

```
  camera  ──▶ perception_node ──▶ /drona/engagement
                                        │
                                        ▼
                              orchestrator_node  (IDLE → GREETING →
                                        │         NEEDS_ASSESSMENT →
                                        │         ADVISING → CLOSURE)
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
      /drona/gesture_command    /drona/student_query        /drona/say
              │                         │                         │
        gesture_node             advising_node              speech_node
       (arm moves)          (RAG + bias + LLM)            (robot talks)
                                        │
                                        ▼
                            /drona/advising_response
```

The robot **starts the conversation itself**: when perception sees a face and
engagement crosses the threshold, the orchestrator greets and gestures without
anyone typing anything. You do not have to drive it manually — but you can.

---

## 2. Three ways to talk to it

### a. The web console (easiest)

`/control` in the dashboard. Type into **Ask** and press send — this publishes to
`/drona/ask`, the orchestrator routes it through retrieval → bias detection →
LLM, and the answer comes back on `/drona/advising_response` and appears under
*Last advice from the robot*. **Say** publishes straight to `/drona/say` to make
it speak a fixed line.

### b. ROS2 command line

```bash
source /opt/ros/jazzy/setup.bash && source ~/drona_ws/install/setup.bash

# Ask a real question (full RAG + bias pipeline)
ros2 topic pub --once /drona/ask std_msgs/msg/String \
  "{data: 'Which modules prepare me for data engineering?'}"

# Make it speak a line directly
ros2 topic pub --once /drona/say std_msgs/msg/String "{data: 'Namaste!'}"

# Play a gesture
ros2 topic pub --once /drona/gesture_command drona_msgs/msg/GestureCommand \
  "{gesture_label: 'greet', policy_hint: ''}"

# Watch what it answers
ros2 topic echo /drona/advising_response
```

Ask in Nepali and it answers in Nepali — language is detected from the question,
and the Nepali path uses the same retrieved curriculum context:

```bash
ros2 topic pub --once /drona/ask std_msgs/msg/String \
  "{data: 'Data science पढ्नको लागि कुन modules राम्रो छ?'}"
```

### c. Walk up to it in the sim

In Gazebo, drag the `student_figure` model closer to the robot. Perception picks
up the change, engagement rises, and the orchestrator greets you unprompted —
which is the behaviour the thesis is actually about.

---

## 3. How the robot speaks

`speech_node` subscribes to `/drona/say` and has several backends, chosen with
the `tts_backend` parameter:

| Backend | Voice quality | Needs | Good for |
|---|---|---|---|
| `log` | none — prints text | nothing | headless CI, no-audio machines |
| `espeak` | robotic but clear | `espeak-ng` | always-works fallback, Raspberry Pi |
| `piper` | natural, offline neural | a piper model | the Pi, offline demos |
| `elevenlabs` | most natural, good Nepali | API key + network | the live demo |

### Audio in WSL2 — verified state on this machine

WSL2 has **no `/dev/snd` sound card**, which is why audio looks impossible at
first glance. It is not: WSLg exposes a PulseAudio socket, and it is already
wired up here —

```
/mnt/wslg/PulseServer          exists
PULSE_SERVER=unix:/mnt/wslg/PulseServer
```

So sound will come out of your Windows speakers. What is missing is the software:
`espeak-ng`, `ffplay`, `aplay` and `paplay` are all **not installed**.

**To give the robot a voice:**

```bash
sudo apt install -y espeak-ng pulseaudio-utils
```

Then launch with the espeak backend:

```bash
ros2 launch drona_bringup drona_gazebo.launch.py rosbridge:=true \
  tts_backend:=espeak
```

Test it immediately:

```bash
espeak-ng "Namaste, I am Drona"      # should come out of your Windows speakers
```

**For the natural voice** (recommended for the actual demo), the key is read from
the environment and never written into a params file:

```bash
export ELEVENLABS_API_KEY=...
ros2 launch drona_bringup drona_gazebo.launch.py tts_backend:=elevenlabs voice:=<voice_id>
```

**If you do not want audio at all**, `tts_backend:=log` prints exactly what the
robot would have said. Everything else — perception, gestures, driving, advising
— works identically without sound.

---

## 4. What the robot looks like and why

The sim robot is built from primitives with no downloaded meshes, so it starts
offline and adds no asset dependency. The visual design was rebuilt to read as a
service robot rather than a debug render:

- **A clear front.** A dark visor and two emissive eyes mean a student can tell at
  a glance whether the robot is facing them. This matters for an approach-and-greet
  robot — the earlier flesh-toned sphere had no orientation cue at all.
- **One coherent palette** — light shell, graphite joints, crimson accent. The
  arm segments used to be green / red / yellow / blue, which is useful debug
  colouring for spotting a mis-parented joint but reads as a toy.
- **A chest display and a rounded base skirt**, which is what mass-market service
  robots (Pepper, Temi) look like.

The room is a Softwarica advising space: whiteboard, notice board, desk rows,
seating, bookshelf and plants, with indoor fill lighting because a single
directional "sun" lights an outdoor scene and leaves an interior dark.

**All of this is visual only.** The joints, collisions, inertials and the whole
TF tree are byte-identical to before — verified by diffing the generated URDF, so
perception, the gesture policies and the controllers are provably unaffected.
