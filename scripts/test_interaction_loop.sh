#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - end-to-end interaction loop test (headless)
# =============================================================================
# Boots the sim, waits for spawn, then injects an engagement sequence and
# verifies: engaged student -> orchestrator greets -> gesture_node -> arm moves.
#
#     bash scripts/test_interaction_loop.sh
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG=/tmp/drona_loop_sim.log

set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/drona_ws/install/setup.bash"
set -u
export LIBGL_ALWAYS_SOFTWARE=1

echo "==> booting sim (headless) in background"
: > "$LOG"
ros2 launch drona_bringup drona_gazebo.launch.py headless:=true use_rviz:=false \
  >> "$LOG" 2>&1 &
LAUNCH_PID=$!
cleanup() { kill "$LAUNCH_PID" 2>/dev/null; pkill -f "gz sim" 2>/dev/null; pkill -f drona_gazebo 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT

echo "==> waiting for the robot to spawn + nodes to settle"
for _ in $(seq 1 60); do grep -q "Entity creation successful" "$LOG" && break; sleep 1; done
grep -q "Entity creation successful" "$LOG" || { echo "FAIL: no spawn"; tail -20 "$LOG"; exit 2; }
sleep 6

echo "==> injecting engagement + measuring the loop"
python3 "$HERE/verify_interaction.py"
RC=$?

echo
echo "==> orchestrator session transitions seen:"
grep -iE "Session:|commanded gesture|Gesture '" "$LOG" | tail -12 || true
exit $RC
