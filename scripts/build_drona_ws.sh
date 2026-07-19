#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - build the ROS2 workspace + install the thin robot runtime (WSL2)
# =============================================================================
# Run AFTER setup_ros2_wsl.sh, in a shell where ROS2 Jazzy is sourced.
# No sudo needed. Idempotent.
#
#     bash scripts/build_drona_ws.sh
#
# What it does:
#   1. installs the `drona` package (--no-deps) + the thin robot runtime into
#      the WSL Python ROS uses, so the nodes can `import drona.*`;
#   2. copies ros2_ws/src into ~/drona_ws (colcon builds outside the Windows
#      filesystem - /mnt/c is very slow and breaks some symlinks);
#   3. colcon build;
#   4. prints how to launch.
# =============================================================================
set -euo pipefail

log()  { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[ok] $*\033[0m"; }
warn() { echo -e "\033[1;33m[warn] $*\033[0m"; }

# Repo root: this script lives in <repo>/scripts.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="$HOME/drona_ws"

if [[ -z "${ROS_DISTRO:-}" ]]; then
  if [[ -f /opt/ros/jazzy/setup.bash ]]; then
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
  else
    echo "ROS2 not found. Run scripts/setup_ros2_wsl.sh first." >&2
    exit 1
  fi
fi
log "ROS_DISTRO=$ROS_DISTRO"

# --- 1. Python runtime for the nodes -----------------------------------------
log "Installing the thin robot runtime into $(python3 --version 2>&1)"
# --no-deps: do NOT pull the heavy retrieval/LLM stack; the brain is remote.
python3 -m pip install --break-system-packages --no-deps -e "$REPO" -q
python3 -m pip install --break-system-packages -r "$REPO/ros2_ws/requirements-robot.txt" -q
python3 -c "import drona, httpx, pydantic_settings; print('  drona importable:', drona.__version__)"
ok "robot runtime installed"
warn "perception (mediapipe) not installed - run requirements-perception.txt if you use the camera node"

# --- 2. stage the workspace off /mnt/c ---------------------------------------
log "Staging workspace at $WS (colcon is slow/buggy on /mnt/c)"
mkdir -p "$WS/src"
# mirror sources; delete removed files so renames don't linger
rsync -a --delete --exclude='build' --exclude='install' --exclude='log' \
      --exclude='__pycache__' "$REPO/ros2_ws/src/" "$WS/src/"
ok "sources staged"

# --- 3. build ----------------------------------------------------------------
log "Building (colcon) - drona_msgs first, then the rest"
cd "$WS"
# Limit parallelism: this box has ~4 GB RAM in WSL; the message generator + gcc
# can OOM at full width.
export MAKEFLAGS="-j2"
colcon build --symlink-install \
  --cmake-args -DCMAKE_BUILD_TYPE=Release \
  --executor sequential
ok "colcon build complete"

# --- 4. next steps -----------------------------------------------------------
cat <<EOF

=============================================================================
 Workspace built at $WS

 Every new shell:   source /opt/ros/jazzy/setup.bash && source $WS/install/setup.bash
 (setup_ros2_wsl.sh already added both to ~/.bashrc)

 Launch the simulation:
   source $WS/install/setup.bash
   ros2 launch drona_bringup drona_gazebo.launch.py

 Use the Colab T4 brain for advising:
   ros2 launch drona_bringup drona_gazebo.launch.py advisor_remote_url:=https://<your>.trycloudflare.com

 Headless (no GUI, if WSLg GL is flaky):
   ros2 launch drona_bringup drona_gazebo.launch.py headless:=true
=============================================================================
EOF
