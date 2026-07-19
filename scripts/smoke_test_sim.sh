#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - headless smoke test of the Gazebo simulation
# =============================================================================
# Launches drona_gazebo.launch.py headless for a fixed window, captures the
# logs, and checks the robot + core nodes actually came up. Non-interactive:
# it self-terminates, so it is safe to run from an automated context.
#
#     bash scripts/smoke_test_sim.sh [seconds]     # default 45
# =============================================================================
set -uo pipefail
DUR="${1:-45}"
LOG=/tmp/drona_sim_smoke.log

set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/drona_ws/install/setup.bash"
set -u

echo "==> xacro sanity (both arg modes)"
URDF="$HOME/drona_ws/install/drona_description/share/drona_description/urdf/drona_humanoid.urdf.xacro"
xacro "$URDF" -o /tmp/drona_default.urdf && echo "  default URDF: $(grep -c '<link' /tmp/drona_default.urdf) links, $(grep -c '<joint' /tmp/drona_default.urdf) joints"
xacro "$URDF" use_gz_camera:=true use_gz_control:=true -o /tmp/drona_gz.urdf && echo "  gz URDF: $(grep -ci sensor /tmp/drona_gz.urdf) sensor blocks, $(grep -ci 'gz-sim' /tmp/drona_gz.urdf) gz plugin refs"

echo "==> launching drona_gazebo.launch.py headless for ${DUR}s"
# Software GL: WSLg's GL can be flaky for the gz server; force llvmpipe so the
# headless server never blocks on a GPU context.
export LIBGL_ALWAYS_SOFTWARE=1
: > "$LOG"
timeout --preserve-status "${DUR}" \
  ros2 launch drona_bringup drona_gazebo.launch.py headless:=true use_rviz:=false \
  >> "$LOG" 2>&1 || true

echo
echo "==> RESULT"
mark() { if grep -qiE "$2" "$LOG"; then echo "  [PASS] $1"; else echo "  [ ?? ] $1"; fi; }
mark "gz sim server started"        "Gazebo Harmonic|gazebo-[0-9]+.*process started|drona_advising world"
mark "robot model spawned"          "Entity creation successful|Entity creation|create-[0-9]+.*finished cleanly"
mark "advising node up"             "AdvisingNode ready|drona_advising_node"
mark "policy node up"               "policy_node|drona_policy_node|PolicyRouter|Policy node"
mark "gz joint relay up"            "gz_joint_relay|joint_relay|relay"
mark "ros_gz bridge up"             "ros_gz_bridge|parameter_bridge|Creating.*bridge|bridge"
mark "diagnostics up"               "diagnostics|/diagnostics"
echo
echo "==> ERRORS / TRACEBACKS (if any):"
grep -iE "error|traceback|no module|failed|exception|not found" "$LOG" | grep -viE "INFO|error_|will be" | sort -u | head -25 || echo "  (none)"
echo
echo "Full log: $LOG  ($(wc -l < "$LOG") lines)"
