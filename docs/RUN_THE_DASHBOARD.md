# Running the D.R.O.N.A. web dashboard against the live robot

End-to-end bring-up: WSL2 → ROS2 Jazzy + Gazebo → rosbridge → FastAPI → Next.js.

Verified against this machine on 2026-07-20:

| Component | State |
|---|---|
| WSL2 distro | `Ubuntu` (WSL version 2), running |
| ROS2 | Jazzy, at `/opt/ros/jazzy` |
| Workspace | `~/drona_ws` — `drona_msgs`, `drona_ros`, `drona_bringup`, `drona_description` all built |
| `ros-jazzy-rosbridge-suite` | **NOT installed** — apt candidate `2.7.0-1noble` |

Only the last row is missing. Everything else is already in place.

---

## Step 0 — install rosbridge (once, needs your password)

This is the one step that cannot be automated: `sudo` on this machine requires a
password. Without rosbridge the browser has nothing to connect to and Mission
Control sits at `LINK DOWN` forever.

From **Windows PowerShell**:

```powershell
wsl -d Ubuntu -e bash -lc "sudo apt update && sudo apt install -y ros-jazzy-rosbridge-suite"
```

Verify it landed:

```powershell
wsl -d Ubuntu -e bash -lc "source /opt/ros/jazzy/setup.bash && ros2 pkg list | grep rosbridge"
```

Expected: `rosbridge_library`, `rosbridge_msgs`, `rosbridge_server`,
`rosapi` (four lines). If you get nothing, the install failed — re-run step 0.

---

## Step 1 — start the robot (terminal 1)

`rosbridge:=true` starts the websocket bridge alongside the sim, so this is one
command rather than two terminals.

```powershell
wsl -d Ubuntu -e bash -lc "source /opt/ros/jazzy/setup.bash && source ~/drona_ws/install/setup.bash && ros2 launch drona_bringup drona_gazebo.launch.py rosbridge:=true"
```

This brings up Gazebo Harmonic plus the full node set the dashboard talks to:
perception, policy, gesture, approach, advising, orchestrator, diagnostics and
speech.

**Low-spec option** — skip the Gazebo GUI (much lighter, everything still
publishes):

```powershell
wsl -d Ubuntu -e bash -lc "source /opt/ros/jazzy/setup.bash && source ~/drona_ws/install/setup.bash && ros2 launch drona_bringup drona_gazebo.launch.py rosbridge:=true headless:=true"
```

**No Gazebo at all** — nodes and rosbridge only, if you just want the dashboard
wired to a live graph:

```powershell
wsl -d Ubuntu -e bash -lc "source /opt/ros/jazzy/setup.bash && source ~/drona_ws/install/setup.bash && ros2 launch drona_bringup drona_system.launch.py rosbridge:=true"
```

Wait for `Rosbridge WebSocket server started on port 9090` in the output.

---

## Step 2 — confirm the bridge is reachable from Windows (terminal 2)

Do this before opening the browser: it separates "the robot is down" from "the
web app is misconfigured", which otherwise look identical.

```powershell
wsl -d Ubuntu -e bash -lc "source /opt/ros/jazzy/setup.bash && source ~/drona_ws/install/setup.bash && ros2 topic list | grep drona"
```

Expected to include `/drona/joint_states`, `/drona/session_state`,
`/drona/engagement`, `/drona/advising_response`, `/drona/gesture_result`, and
`/diagnostics`.

Then check the port is open from the Windows side — WSL2 forwards `localhost`,
so this should succeed without any extra networking setup:

```powershell
Test-NetConnection -ComputerName localhost -Port 9090
```

`TcpTestSucceeded : True` means the browser will be able to connect.

---

## Step 3 — start the API (terminal 3)

From the repo root on Windows:

```powershell
python scripts/run_api.py
```

Serves on `http://localhost:8000`, which is what the frontend expects by
default. Confirm:

```powershell
curl http://localhost:8000/health
```

---

## Step 4 — start the web app (terminal 4)

```powershell
cd frontend
npm run dev
```

Open <http://localhost:3000>.

---

## Step 5 — verify the console is actually live

Go to **Mission control** (`/control`). You should see:

- the status pill flip to **LINK UP**;
- **Topic rates** listing topics with a measured Hz and a green dot
  (`/drona/joint_states` around 10 Hz);
- **Node health** populated from `/diagnostics`;
- **Joint telemetry** bars moving.

Then exercise the command surface:

1. **Drive** — hold an arrow button. The base moves in Gazebo and `/cmd_vel`
   publishes at 10 Hz. Releasing sends a zero Twist.
2. **Gesture** — click `greet`. The arm moves and the command log shows
   `✓ greet via <policy>` from `/drona/gesture_result`.
3. **Ask** — type a question and send. The advice appears under **Last advice
   from the robot**, read from `/drona/advising_response`.
4. **E-STOP** — always reachable, latches zero velocity.

If controls stay greyed out, the console is not connected — every control is
disabled until rosbridge is genuinely up, deliberately, so a button never
silently does nothing.

---

## Troubleshooting

**`LINK DOWN` but step 2 passed.** Check the URL the app is using —
Preferences → rosbridge URL. Default is `ws://localhost:9090`.

**`package 'rosbridge_server' not found` during launch.** Step 0 did not
complete. Re-run it and re-check with the verify command.

**Topics list is empty.** The workspace overlay was not sourced. Both `source`
commands are required, in order: `/opt/ros/jazzy` then `~/drona_ws/install`.

**Gazebo is slow or the window never appears.** Use `headless:=true`, or
`drona_system.launch.py` which skips Gazebo entirely.

**Nodes see each other in WSL but not across terminals.** Make sure every
terminal uses the same `ROS_DOMAIN_ID` (unset is fine, as long as it is
consistent).

**Advising returns nothing.** The advising path needs Ollama running. That is
independent of rosbridge — the robot, telemetry and teleop all work without it;
only `/drona/ask` needs the model.

---

## What is verified vs what is not

The topic names, message type strings and every field the console reads are
checked automatically against the real `.msg` definitions by
`tests/test_ros_web_contract.py`, which runs in CI without needing ROS2. That
proves the *contract* is right.

It does not prove the console works end to end — that needs a live graph, which
needs step 0. Until rosbridge is installed, treat the Mission Control page as
unverified against real hardware.
