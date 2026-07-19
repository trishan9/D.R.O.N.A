#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - one-shot ROS2 + Gazebo bring-up for WSL2 (Ubuntu 24.04)
# =============================================================================
# Installs ROS2 Jazzy Jalisco + Gazebo Harmonic + build tooling.
#
# Ubuntu 24.04 pairs with ROS2 *Jazzy* (not Humble, which targets 22.04) and
# Gazebo *Harmonic* - which is what drona_gazebo.launch.py already expects.
#
# Run once, from Windows PowerShell:
#     wsl -e bash -lc "sudo bash /mnt/c/Users/trish/Documents/Developer/D.R.O.N.A/scripts/setup_ros2_wsl.sh"
#
# Idempotent: safe to re-run if it fails partway.
# Downloads ~2-3 GB; takes 10-25 min depending on connection.
# =============================================================================
set -euo pipefail

log()  { echo -e "\n\033[1;36m==> $*\033[0m"; }
warn() { echo -e "\033[1;33m[warn] $*\033[0m"; }
ok()   { echo -e "\033[1;32m[ok] $*\033[0m"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo:  sudo bash $0" >&2
  exit 1
fi

# The unprivileged user we hand the workspace back to.
REAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo root)}"

# --- sanity ------------------------------------------------------------------
UBU="$(. /etc/os-release && echo "$VERSION_ID")"
log "Ubuntu $UBU detected"
if [[ "$UBU" != "24.04" ]]; then
  warn "This script targets Ubuntu 24.04 (ROS2 Jazzy). Found $UBU - continuing anyway."
fi

# --- 1. base tooling ---------------------------------------------------------
log "Installing base tooling"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq software-properties-common curl gnupg lsb-release locales \
                       build-essential git python3-pip python3-venv
add-apt-repository -y universe >/dev/null 2>&1 || true

# ROS2 requires a UTF-8 locale.
locale-gen en_US.UTF-8 >/dev/null
update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
ok "base tooling"

# --- 2. ROS2 apt repository --------------------------------------------------
log "Adding the ROS2 apt repository"
install -d -m 0755 /etc/apt/keyrings
if [[ ! -f /usr/share/keyrings/ros-archive-keyring.gpg ]]; then
  curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  > /etc/apt/sources.list.d/ros2.list
ok "ROS2 repo"

# --- 3. Gazebo (Harmonic) apt repository -------------------------------------
log "Adding the Gazebo apt repository"
if [[ ! -f /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg ]]; then
  curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
    -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] \
http://packages.osrfoundation.org/gazebo/ubuntu-stable $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
  > /etc/apt/sources.list.d/gazebo-stable.list
ok "Gazebo repo"

apt-get update -qq

# --- 4. ROS2 Jazzy desktop ---------------------------------------------------
log "Installing ROS2 Jazzy desktop (this is the big one, ~2 GB)"
apt-get install -y ros-jazzy-desktop
ok "ROS2 Jazzy desktop"

# --- 5. Gazebo Harmonic + the ROS<->gz bridge --------------------------------
log "Installing Gazebo Harmonic + ros_gz bridge"
apt-get install -y gz-harmonic ros-jazzy-ros-gz
ok "Gazebo Harmonic + ros_gz"

# --- 6. packages the D.R.O.N.A. launch files need ----------------------------
log "Installing D.R.O.N.A. launch dependencies"
apt-get install -y \
  ros-jazzy-xacro \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-joint-state-publisher \
  ros-jazzy-joint-state-publisher-gui \
  ros-jazzy-rviz2 \
  ros-jazzy-diagnostic-msgs \
  ros-jazzy-diagnostic-updater \
  ros-jazzy-image-transport \
  ros-jazzy-cv-bridge \
  ros-jazzy-vision-opencv \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool
ok "launch dependencies"

# --- 7. rosdep ---------------------------------------------------------------
log "Initialising rosdep"
rosdep init >/dev/null 2>&1 || true
sudo -u "$REAL_USER" rosdep update >/dev/null 2>&1 || warn "rosdep update failed (non-fatal)"
ok "rosdep"

# --- 8. shell setup for the real user ----------------------------------------
log "Wiring up $REAL_USER's shell"
USER_HOME="$(getent passwd "$REAL_USER" | cut -d: -f6)"
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "DRONA ROS2 setup" "$BASHRC" 2>/dev/null; then
  cat >> "$BASHRC" <<'EOF'

# --- DRONA ROS2 setup ---
source /opt/ros/jazzy/setup.bash
[ -f ~/drona_ws/install/setup.bash ] && source ~/drona_ws/install/setup.bash
# WSLg software GL fallback: uncomment if Gazebo's GUI fails to render.
# export LIBGL_ALWAYS_SOFTWARE=1
EOF
  chown "$REAL_USER:$REAL_USER" "$BASHRC"
fi
ok "shell configured"

# --- done --------------------------------------------------------------------
log "Verifying"
set +u; source /opt/ros/jazzy/setup.bash; set -u
echo "  ROS_DISTRO = ${ROS_DISTRO:-<unset>}"
echo "  gz         = $(gz sim --version 2>/dev/null | head -1 || echo '<not found>')"
echo "  colcon     = $(command -v colcon || echo '<not found>')"

cat <<EOF

=============================================================================
 ROS2 Jazzy + Gazebo Harmonic installed.
 Open a NEW WSL shell (so ~/.bashrc is re-sourced), then tell Claude it's done.
 Claude will build the workspace and launch the simulation from here.
=============================================================================
EOF
