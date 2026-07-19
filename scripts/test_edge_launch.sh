#!/usr/bin/env bash
# Verify the Pi EDGE launch starts and publishes /drona/engagement.
# On a machine with no camera the detector falls back to the stub, which still
# proves the launch + node + topic wiring that the Pi will use.
set -uo pipefail
LOG=/tmp/drona_edge.log
set +u; source /opt/ros/jazzy/setup.bash; source "$HOME/drona_ws/install/setup.bash"; set -u

echo "==> launching drona_edge.launch.py (perception only)"
: > "$LOG"
ros2 launch drona_bringup drona_edge.launch.py detection_hz:=5.0 >> "$LOG" 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null; pkill -f perception_node 2>/dev/null; wait 2>/dev/null' EXIT
sleep 12

echo "==> is /drona/engagement being published?"
timeout 12 ros2 topic echo /drona/engagement --once 2>/dev/null | head -8 || echo "(no message)"

echo
echo "==> node + camera backend from the log:"
grep -iE "PerceptionNode ready|CameraSource|MediaPipeDetector|camera|EDGE" "$LOG" \
  | grep -viE "W0000|I0000" | tail -8
echo
echo "==> errors (if any):"
grep -iE "error|traceback|no usable camera" "$LOG" | grep -viE "W0000|I0000" | tail -5 || echo "  (none)"
