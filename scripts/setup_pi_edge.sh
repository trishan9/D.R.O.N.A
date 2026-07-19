#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - one-shot Raspberry Pi EDGE setup (USB camera + perception node)
# =============================================================================
# Turns a Raspberry Pi into the perception tier: a real USB camera watching a
# real student, publishing /drona/engagement onto the ROS2 graph that the robot
# (Gazebo or hardware) and the GPU brain also live on.
#
# Run on the Pi (64-bit Raspberry Pi OS Bookworm, Pi 4/5 recommended):
#     sudo bash scripts/setup_pi_edge.sh
#
# Then, in a normal shell:
#     export ROS_DOMAIN_ID=42            # SAME value on the robot machine
#     ros2 launch drona_bringup drona_edge.launch.py
#
# Idempotent. Installs ros-jazzy-ros-base (no Gazebo - the Pi never simulates).
# =============================================================================
set -euo pipefail

log()  { echo -e "\n\033[1;36m==> $*\033[0m"; }
ok()   { echo -e "\033[1;32m[ok] $*\033[0m"; }
warn() { echo -e "\033[1;33m[warn] $*\033[0m"; }

if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo bash $0" >&2; exit 1; fi
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo pi)}"
USER_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log "Base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl gnupg lsb-release locales git python3-pip rsync v4l-utils
locale-gen en_US.UTF-8 >/dev/null; update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ok "base"

log "ROS2 Jazzy apt repo"
if [[ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]]; then
  curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") main" \
  > /etc/apt/sources.list.d/ros2.list
apt-get update -qq
ok "repo"

log "ROS2 Jazzy base (no desktop/Gazebo - the Pi only perceives)"
apt-get install -y ros-jazzy-ros-base python3-colcon-common-extensions
ok "ros-base"

log "Python deps (perception: numpy<2 is mandatory for mediapipe + ROS)"
sudo -u "$REAL_USER" python3 -m pip install --break-system-packages -q \
  'numpy<2' 'mediapipe>=0.10.9' 'opencv-contrib-python<5'
sudo -u "$REAL_USER" python3 -m pip install --break-system-packages -q --no-deps -e "$REPO"
sudo -u "$REAL_USER" python3 -m pip install --break-system-packages -q -r "$REPO/ros2_ws/requirements-robot.txt"
ok "python deps"

log "Building the D.R.O.N.A. workspace (messages + nodes)"
WS="$USER_HOME/drona_ws"
sudo -u "$REAL_USER" mkdir -p "$WS/src"
sudo -u "$REAL_USER" rsync -a --delete "$REPO/ros2_ws/src/" "$WS/src/"
sudo -u "$REAL_USER" bash -lc "source /opt/ros/jazzy/setup.bash && cd '$WS' && MAKEFLAGS=-j2 colcon build --symlink-install --executor sequential"
ok "workspace built"

log "Shell setup"
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "DRONA EDGE setup" "$BASHRC" 2>/dev/null; then
  cat >> "$BASHRC" <<EOF

# --- DRONA EDGE setup ---
source /opt/ros/jazzy/setup.bash
[ -f $WS/install/setup.bash ] && source $WS/install/setup.bash
export ROS_DOMAIN_ID=42        # MUST match the robot machine
EOF
  chown "$REAL_USER:$REAL_USER" "$BASHRC"
fi
ok "shell"

log "Camera check"
if ls /dev/video* >/dev/null 2>&1; then
  echo "  video devices:"; ls -1 /dev/video* | sed 's/^/    /'
  v4l2-ctl --list-devices 2>/dev/null | head -10 || true
  usermod -aG video "$REAL_USER" || true
  ok "USB camera detected (user added to 'video' group)"
else
  warn "No /dev/video* found - plug the USB camera in and re-check with: ls /dev/video*"
fi

cat <<EOF

=============================================================================
 D.R.O.N.A. EDGE ready on this Pi.

 Open a NEW shell (for ~/.bashrc), then:
     ros2 launch drona_bringup drona_edge.launch.py

 Verify it is publishing (on the Pi or the robot machine):
     ros2 topic echo /drona/engagement

 On the ROBOT machine use the SAME ROS_DOMAIN_ID (42) and launch the sim:
     ros2 launch drona_bringup drona_gazebo.launch.py mobile:=true
 Do NOT run perception on both machines - two publishers will fight.
=============================================================================
EOF
