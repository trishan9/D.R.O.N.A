#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - end-to-end gesture MOTION test (headless)
# =============================================================================
# Boots the Gazebo sim in the background, waits for the robot to spawn, then
# runs verify_motion.py to command a pose and confirm the arm actually moves.
# Self-terminating.
#
#     bash scripts/test_gesture_motion.sh
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG=/tmp/drona_motion_sim.log

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

echo "==> waiting for the robot to spawn"
for _ in $(seq 1 60); do
  grep -q "Entity creation successful" "$LOG" && break
  sleep 1
done
if ! grep -q "Entity creation successful" "$LOG"; then
  echo "FAIL: robot never spawned"; tail -20 "$LOG"; exit 2
fi
echo "  spawned. letting physics settle ..."
sleep 5

echo "==> commanding a gesture pose and measuring the arm"
python3 "$HERE/verify_motion.py"
RC=$?

echo "==> shutting the sim down"
exit $RC
