#!/usr/bin/env bash
# Boot the sim headless and measure end-to-end reaction latency.
#     bash scripts/run_latency_benchmark.sh [trials]
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
TRIALS="${1:-5}"
LOG=/tmp/drona_bench_sim.log

set +u
source /opt/ros/jazzy/setup.bash
source "$HOME/drona_ws/install/setup.bash"
set -u
export LIBGL_ALWAYS_SOFTWARE=1

echo "==> booting sim (headless)"
: > "$LOG"
ros2 launch drona_bringup drona_gazebo.launch.py headless:=true use_rviz:=false \
  >> "$LOG" 2>&1 &
LAUNCH_PID=$!
cleanup() { kill "$LAUNCH_PID" 2>/dev/null; pkill -f "gz sim" 2>/dev/null; wait 2>/dev/null; }
trap cleanup EXIT

for _ in $(seq 1 60); do grep -q "Entity creation successful" "$LOG" && break; sleep 1; done
grep -q "Entity creation successful" "$LOG" || { echo "FAIL: no spawn"; tail -20 "$LOG"; exit 2; }
sleep 6

cd "$REPO"
python3 "$HERE/benchmark_latency.py" "$TRIALS"
