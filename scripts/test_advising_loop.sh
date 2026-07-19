#!/usr/bin/env bash
# =============================================================================
# D.R.O.N.A. - full conversational loop test (headless, mock brain)
# =============================================================================
# Boots a mock brain + the sim (pointed at it), then verifies the robot greets,
# answers a question through the brain, and speaks the answer. This exercises the
# SAME path the Colab T4 uses - only the brain URL differs.
#
#     bash scripts/test_advising_loop.sh
# =============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
LOG=/tmp/drona_convo_sim.log
BRAIN_PORT=8099

set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/drona_ws/install/setup.bash"
set -u
export LIBGL_ALWAYS_SOFTWARE=1

echo "==> starting mock brain on :$BRAIN_PORT"
python3 "$HERE/mock_brain.py" "$BRAIN_PORT" > /tmp/drona_mock_brain.log 2>&1 &
BRAIN_PID=$!
# speech to log only, so the test needs no audio device
export DRONA_TTS=log

cleanup() {
  kill "$BRAIN_PID" 2>/dev/null
  kill "${LAUNCH_PID:-}" 2>/dev/null
  pkill -f "gz sim" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT

# wait for the brain to answer /health
for _ in $(seq 1 30); do
  curl -sf "http://localhost:$BRAIN_PORT/health" >/dev/null 2>&1 && break
  sleep 0.5
done
echo "  brain health: $(curl -s http://localhost:$BRAIN_PORT/health || echo DOWN)"

echo "==> booting sim pointed at the mock brain"
: > "$LOG"
ros2 launch drona_bringup drona_gazebo.launch.py headless:=true use_rviz:=false \
  advisor_remote_url:="http://localhost:$BRAIN_PORT" \
  >> "$LOG" 2>&1 &
LAUNCH_PID=$!

for _ in $(seq 1 60); do grep -q "Entity creation successful" "$LOG" && break; sleep 1; done
grep -q "Entity creation successful" "$LOG" || { echo "FAIL: no spawn"; tail -20 "$LOG"; exit 2; }
sleep 6

echo "==> running the conversation"
python3 "$HERE/verify_advising_loop.py" "How do I get into a masters program abroad?"
RC=$?

echo
echo "==> orchestrator + speech log:"
grep -iE "Session:|Student asked|Query published|Advising response|Say:|SpeechNode" "$LOG" \
  | grep -viE "W0000|I0000" | tail -15 || true
exit $RC
