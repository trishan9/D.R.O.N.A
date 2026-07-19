#!/usr/bin/env bash
# Verify the D.R.O.N.A. URDF processes in every xacro arg combination.
set -uo pipefail
set +u; source /opt/ros/jazzy/setup.bash; source "$HOME/drona_ws/install/setup.bash"; set -u
U="$HOME/drona_ws/src/drona_description/urdf/drona_humanoid.urdf.xacro"

echo "--- desk mode (default) ---"
if xacro "$U" -o /tmp/desk.urdf 2>/tmp/desk.err; then
  echo "  OK  links=$(grep -c '<link' /tmp/desk.urdf) joints=$(grep -c '<joint' /tmp/desk.urdf)"
  echo "  wheels present (should be 0): $(grep -c wheel /tmp/desk.urdf)"
else
  echo "  FAIL"; cat /tmp/desk.err; exit 1
fi

echo "--- mobile base mode ---"
if xacro "$U" use_mobile_base:=true use_gz_control:=true use_gz_camera:=true \
      -o /tmp/mob.urdf 2>/tmp/mob.err; then
  echo "  OK  links=$(grep -c '<link' /tmp/mob.urdf) joints=$(grep -c '<joint' /tmp/mob.urdf)"
  echo "  wheel refs : $(grep -c wheel /tmp/mob.urdf)"
  echo "  DiffDrive  : $(grep -c DiffDrive /tmp/mob.urdf)"
  echo "  root link  : $(python3 - <<'PY'
import xml.etree.ElementTree as ET
r = ET.parse('/tmp/mob.urdf').getroot()
links = {l.get('name') for l in r.findall('link')}
children = {j.find('child').get('link') for j in r.findall('joint')}
print(sorted(links - children))
PY
)"
else
  echo "  FAIL"; cat /tmp/mob.err; exit 1
fi
