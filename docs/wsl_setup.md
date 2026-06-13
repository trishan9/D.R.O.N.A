# Running D.R.O.N.A. ROS2 + Gazebo on Windows via WSL2

**This is the recommended ROS2 path now that there is no Ubuntu dual-boot.**

ROS2 Humble only runs on Ubuntu 22.04 — it does **not** run natively on Windows.
But you do **not** need a dual-boot partition. **WSL2 (Windows Subsystem for Linux
2)** runs a real Ubuntu 22.04 kernel inside Windows 11, and **WSLg** (bundled with
Windows 11, all editions including Home) gives Linux GUI apps a window on your
Windows desktop. That means **RViz2 and the Gazebo GUI just open as normal
windows** — no VcXsrv / X-server fiddling required.

> **Your machine:** Windows 11 Home (build 26200), GTX 1650 4 GB. WSLg + the
> NVIDIA WSL GPU driver cover everything in this guide **except Isaac Sim** (still
> needs ≥ 8 GB VRAM → use the cloud recipe in `docs/sim_setup_isaac.md`). Gazebo
> Harmonic is the simulator you will demo.

---

## 0. What changed vs the old "Ubuntu dual-boot" instructions

| Old (dual-boot) | New (WSL2) |
|---|---|
| Reboot into Ubuntu 22.04 | Stay in Windows; open an **Ubuntu (WSL)** terminal |
| Native GPU + display | **WSLg** provides the display; NVIDIA **WSL driver** provides the GPU |
| Repo on the Ubuntu partition | Repo lives on Windows; access it from WSL (see §3) |
| `colcon build` on bare metal | Identical commands, run **inside** the WSL Ubuntu shell |

Everything in `docs/ros2_setup.md`, `docs/sim_setup_gazebo.md`, and the ROS2
commands in `docs/STUDENT_RUNBOOK.md` Part G works **unchanged** once you are
inside the WSL Ubuntu shell. The only new steps are §1–§3 below.

---

## 1. Install WSL2 + Ubuntu 22.04

Open **PowerShell as Administrator** (Windows side) and run:

```powershell
wsl --install -d Ubuntu-22.04
```

This installs WSL2 and Ubuntu 22.04. Reboot if prompted. On first launch Ubuntu
asks you to create a Linux username + password (this is separate from your
Windows login — remember it; `sudo` needs it).

Confirm you are on WSL **2** (not 1 — ROS2/Gazebo need 2) and that WSLg is present:

```powershell
wsl --list --verbose          # VERSION column must say 2 for Ubuntu-22.04
wsl --update                   # ensures latest WSL + WSLg kernel
```

If `VERSION` shows `1`, convert it:

```powershell
wsl --set-version Ubuntu-22.04 2
```

From here on, **open the "Ubuntu 22.04" app** from the Start menu (or run `wsl` in
any terminal) — that drops you into the Linux shell where all ROS2 commands run.

---

## 2. GPU in WSL2 (one-time check)

WSL2 uses the **Windows** NVIDIA driver — do **not** install a Linux NVIDIA driver
inside Ubuntu (that breaks the WSL GPU bridge). Just keep your Windows GeForce
driver up to date (any recent Game Ready / Studio driver supports WSL).

Verify the GPU is visible from inside WSL:

```bash
nvidia-smi          # should list your GTX 1650
```

WSLg renders OpenGL (RViz, Gazebo) through Mesa's `d3d12` driver on top of your
GPU. If a GUI app complains about GL, see Troubleshooting (§7) for the
`LIBGL_ALWAYS_SOFTWARE=1` fallback.

---

## 3. Get the repo into WSL

Your code is on the Windows drive. From the WSL shell, Windows `C:` is mounted at
`/mnt/c`, so you can use it directly:

```bash
cd /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A/ros2_ws
```

> **Performance note:** building under `/mnt/c` is slower (cross-filesystem) and
> can trip file-watcher limits. For a smoother `colcon build`, clone a copy into
> the native WSL filesystem instead:
>
> ```bash
> cd ~ && git clone <your-repo-or-copy> drona && cd drona/ros2_ws
> ```
>
> Either works. Use `/mnt/c` if you want one shared copy with your Windows editing;
> use `~` (native) if `colcon build` feels slow. The Python/advising side can stay
> on Windows — only the ROS2 workspace needs to build in Linux.

---

## 4. Install ROS2 Humble + Gazebo (inside WSL)

Run these **inside the Ubuntu shell**. This is the same as `docs/ros2_setup.md`
§1 and `docs/sim_setup_gazebo.md` §1, collected here:

```bash
# --- ROS2 Humble ---
sudo apt update && sudo apt install -y locales curl gnupg lsb-release
sudo locale-gen en_US en_US.UTF-8 && sudo update-locale LANG=en_US.UTF-8
sudo add-apt-repository universe -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update
sudo apt install -y ros-humble-desktop ros-dev-tools \
  python3-colcon-common-extensions python3-rosdep

# --- Gazebo Harmonic + ROS2<->Gazebo bridge + viz ---
sudo apt install -y ros-humble-ros-gz gz-harmonic \
  ros-humble-robot-state-publisher ros-humble-joint-state-publisher-gui \
  ros-humble-xacro ros-humble-rviz2

# --- rosdep (once) ---
sudo rosdep init 2>/dev/null; rosdep update

# --- source ROS2 in every shell ---
echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc
source /opt/ros/humble/setup.bash
```

Sanity check:

```bash
ros2 --help            # ROS2 responds
gz sim --version       # Gazebo Harmonic 8.x
```

---

## 5. Build the workspace (inside WSL)

```bash
cd <your ros2_ws path from §3>
rosdep install --from-paths src --ignore-src -r -y    # resolves package deps
colcon build --symlink-install
source install/setup.bash
echo 'source '"$(pwd)"'/install/setup.bash' >> ~/.bashrc   # optional convenience

ros2 pkg list | grep drona     # expect drona_bringup, drona_description, drona_msgs, drona_ros
```

---

## 6. Run the simulation (GUI windows appear on your Windows desktop)

```bash
# Full stack + RViz + record a demo bag:
ros2 launch drona_bringup drona_system.launch.py use_rviz:=true record:=true bag_path:=demo_run

# Or just Gazebo:
ros2 launch drona_bringup drona_gazebo.launch.py
```

In a **second** Ubuntu terminal (sourced — open it and run `source
install/setup.bash` or rely on `~/.bashrc`), drive a gesture:

```bash
ros2 action send_goal /drona/execute_gesture_action \
  drona_msgs/action/ExecuteGesture "{gesture_label: 'greet'}" --feedback
```

The Gazebo / RViz window opens like any Windows app (you will see it in the
taskbar). Record this for your demo video — see `docs/demo_video_script.md`.

> **If a GUI window does not appear or rendering is broken**, jump to §7. The
> reliable fallback is `headless:=true` (no GUI; the gesture action + rosbag still
> run and record), or `LIBGL_ALWAYS_SOFTWARE=1` for software GL.

---

## 7. Troubleshooting (WSL-specific)

| Symptom | Fix |
|---|---|
| No GUI window opens at all | `wsl --update` on the Windows side, then restart the WSL shell (`wsl --shutdown` in PowerShell, reopen Ubuntu). WSLg needs an up-to-date WSL. |
| Gazebo opens then crashes / black screen | GL issue. Try `export LIBGL_ALWAYS_SOFTWARE=1` then relaunch (software rendering — slower but always works on a GTX 1650 under WSL). |
| `gz sim` GL3+ / Ogre2 errors | `export QT_QPA_PLATFORM=xcb` and `export LIBGL_ALWAYS_SOFTWARE=1`, relaunch. Or use `headless:=true` and view via RViz/rosbag. |
| `nvidia-smi: command not found` in WSL | Update the **Windows** GeForce driver; do **not** apt-install a Linux GPU driver inside WSL. |
| `colcon build` very slow / file-watcher errors | You are on `/mnt/c`. Clone into the native WSL home (`~`) per §3, or raise `fs.inotify.max_user_watches`. |
| Build was on WSL1 | `wsl --set-version Ubuntu-22.04 2` (WSL1 cannot run Gazebo). |
| Editing files: which path? | Windows path `C:\Users\trish\...\D.R.O.N.A` == WSL path `/mnt/c/Users/trish/.../D.R.O.N.A`. VS Code: install the "WSL" extension and `code .` from the WSL shell. |
| ROS2 nodes can't see each other | All nodes must run in the **same** WSL distro and have ROS2 sourced. Set a matching `export ROS_DOMAIN_ID=42` in each terminal if you isolate runs. |

---

## 8. (Phase 2 only) Real SO-100 arm over USB

For the future hardware swap, WSL2 reaches USB devices via **usbipd-win**:

```powershell
# Windows PowerShell (admin), with the arm plugged in:
winget install usbipd
usbipd list                      # find the U2D2/arm bus-id
usbipd bind --busid <id>
usbipd attach --wsl --busid <id> # device now appears as /dev/ttyUSB0 in WSL
```

Then in WSL the arm is `/dev/ttyUSB0` exactly as the `hardware.yaml` params expect.
This is Phase-2 work — the simulation demo above needs no USB.

---

## 9. Drive the robot from the web app (rosbridge)

The Next.js **Robot Control** page has a *live* mode that talks to the ROS2 graph
over **rosbridge** (a WebSocket↔ROS2 bridge). It subscribes to
`/drona/joint_states` to mirror the real arm and calls the `/drona/execute_gesture`
service to trigger gestures.

```bash
# inside WSL2, once:
sudo apt install ros-humble-rosbridge-suite

# start the full stack WITH the bridge on :9090:
ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
# (or standalone, alongside any launch:)
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

Then in the web app: open **Robot Control → Live ROS2 bridge**, confirm the URL is
`ws://localhost:9090`, and click **Connect**. The browser reaches WSL on
`localhost` automatically (WSL2 forwards localhost ports to Windows). Gestures you
click now run on the real ROS2 robot and the arm view tracks the live joint
stream. With nothing connected, the page stays in its local-simulation mode.

---

## See also

- `docs/ros2_setup.md` — full ROS2 install + node/topic reference
- `docs/sim_setup_gazebo.md` — Gazebo launch details + actuation note
- `docs/sim_setup_isaac.md` — Isaac Sim (cloud GPU; your GTX 1650 can't run it)
- `docs/ros2_topics_actions.md` — every topic / action / service
- `docs/STUDENT_RUNBOOK.md` Part G — where this fits in the overall plan
