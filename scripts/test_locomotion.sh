#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - mobile base locomotion test (headless)
# =============================================================================
# Boots the sim with the wheeled base, then verifies the robot drives to the
# student, stops at conversation range, and halts when the student leaves.
#
#     bash scripts/test_locomotion.sh
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG=/tmp/drona_mobile_sim.log

set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/drona_ws/install/setup.bash"
set -u
export LIBGL_ALWAYS_SOFTWARE=1

echo "==> booting sim with mobile base (headless)"
: > "$LOG"
ros2 launch drona_bringup drona_gazebo.launch.py \
  headless:=true use_rviz:=false mobile:=true >> "$LOG" 2>&1 &
LAUNCH_PID=$!
cleanup() { kill "$LAUNCH_PID" 2>/dev/null; pkill -f "gz sim" 2>/dev/null; pkill -f drona_gazebo 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT

echo "==> waiting for spawn"
for _ in $(seq 1 60); do grep -q "Entity creation successful" "$LOG" && break; sleep 1; done
grep -q "Entity creation successful" "$LOG" || { echo "FAIL: no spawn"; tail -25 "$LOG"; exit 2; }
sleep 6

echo "==> driving"
python3 "$HERE/verify_locomotion.py"
RC=$?

echo
echo "==> approach_node log:"
grep -iE "ApproachNode|approaching|conversation range" "$LOG" | tail -8 || true
exit $RC
