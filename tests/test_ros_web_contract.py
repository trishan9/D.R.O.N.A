"""
Contract tests between the ROS2 interfaces and the web operator console.

WHY THIS EXISTS
---------------
Three real bugs shipped in the dashboard because nothing checked that the
browser and the robot agreed on names:

  - GestureResult carries ``gesture_label`` / ``error_message``; the console read
    ``gesture_name`` / ``message`` and logged every gesture as unnamed.
  - EngagementDetection carries ``confidence``; the console read
    ``engagement_score`` / ``score`` / ``value``, none of which exist, so the
    engagement readout was permanently blank against a live graph.
  - Type strings used the two-part ROS1 form, which ROS2 rosbridge does not
    reliably resolve.

Every one of those fails **silently**: rosbridge does not error on a subscription
to a misspelled field, the value is simply ``undefined`` forever. That is the
worst kind of bug in an operator console, because the UI looks fine.

These tests parse the ``.msg``/``.srv`` definitions and the TypeScript client and
assert they still agree. They need no ROS2 installation, so they run in CI on
Windows - which matters, because the ROS2 graph itself only runs in WSL.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MSG_DIR = ROOT / "ros2_ws" / "src" / "drona_msgs"
ROSBRIDGE_TS = ROOT / "frontend" / "lib" / "rosbridge.ts"
ROS_NODES = ROOT / "ros2_ws" / "src" / "drona_ros" / "drona_ros"

pytestmark = pytest.mark.skipif(
    not MSG_DIR.exists() or not ROSBRIDGE_TS.exists(),
    reason="ROS2 workspace or frontend not present in this checkout",
)


def _interface_fields(rel: str) -> set[str]:
    """Field names declared by a drona_msgs interface, e.g. 'msg/GestureResult'.

    Handles the service '---' separator by reading only the request half unless a
    section is requested, and ignores comments and blank lines.
    """
    path = MSG_DIR / f"{rel}.msg"
    if not path.exists():
        path = MSG_DIR / f"{rel}.srv"
    if not path.exists():
        raise AssertionError(f"no such interface definition: {rel}")

    fields: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line == "---":
            continue
        parts = line.split()
        # "<type> <name>" - constants ("int32 X=1") are not fields we read.
        if len(parts) >= 2 and "=" not in parts[1]:
            fields.add(parts[1])
    return fields


def _ts_source() -> str:
    return ROSBRIDGE_TS.read_text(encoding="utf-8")


def _declared_types() -> list[str]:
    """Every ROS type string the client declares."""
    return re.findall(r'type:\s*"([^"]+)"', _ts_source())


def _declared_topics() -> list[str]:
    return re.findall(r'name:\s*"(/[^"]+)"', _ts_source())


# ── Type strings ─────────────────────────────────────────────────────────────


def test_every_declared_type_uses_the_canonical_ros2_form():
    """ROS2 rosbridge wants pkg/msg/Type, not the two-part ROS1 pkg/Type."""
    bad = [t for t in _declared_types() if len(t.split("/")) != 3]
    assert not bad, f"two-part ROS1 type strings will not resolve under ROS2: {bad}"


def test_drona_type_strings_resolve_to_real_interface_files():
    for t in _declared_types():
        pkg, kind, name = t.split("/")
        if pkg != "drona_msgs":
            continue  # standard messages are guaranteed by the ROS2 distro
        path_msg = MSG_DIR / kind / f"{name}.msg"
        path_srv = MSG_DIR / kind / f"{name}.srv"
        assert path_msg.exists() or path_srv.exists(), (
            f"{t} is declared in rosbridge.ts but {kind}/{name}.[msg|srv] does not exist"
        )


def test_declared_topics_exist_in_the_ros2_nodes():
    """A topic the console talks to must be one some node actually uses."""
    sources = "\n".join(
        p.read_text(encoding="utf-8") for p in ROS_NODES.glob("*.py")
    )
    for topic in _declared_topics():
        assert f'"{topic}"' in sources or f"'{topic}'" in sources, (
            f"{topic} is declared in rosbridge.ts but no drona_ros node publishes "
            f"or subscribes to it"
        )


# ── Field names the dashboard actually reads ─────────────────────────────────
#
# Curated deliberately: the TSX reads fields dynamically off an untyped message,
# so it cannot be derived. Keeping the list explicit means adding a field to a
# panel forces a conscious update here, which is the point.

CONSUMED_FIELDS: dict[str, set[str]] = {
    "msg/GestureResult": {"gesture_label", "success", "policy_used", "error_message"},
    "msg/GestureCommand": {
        "stamp", "gesture_label", "target_x", "target_y", "target_z", "policy_hint",
    },
    "msg/SessionState": {"state"},
    "msg/EngagementDetection": {"state", "confidence", "distance_m"},
    "msg/AdvisingResponse": {"summary", "pathways", "bias_flags"},
}


@pytest.mark.parametrize(("interface", "consumed"), sorted(CONSUMED_FIELDS.items()))
def test_consumed_fields_exist_on_the_interface(interface: str, consumed: set[str]):
    declared = _interface_fields(interface)
    missing = consumed - declared
    assert not missing, (
        f"the web console reads {sorted(missing)} from {interface}, which declares "
        f"{sorted(declared)}. A missing field is silently undefined at runtime."
    )


def test_engagement_regression_specific_field_names():
    """Guards the exact bug that shipped: reading a score field that never existed."""
    declared = _interface_fields("msg/EngagementDetection")
    assert "confidence" in declared
    for never_existed in ("engagement_score", "score", "value"):
        assert never_existed not in declared, (
            f"{never_existed} now exists on EngagementDetection - update the console "
            f"and this test together"
        )


def test_gesture_result_regression_specific_field_names():
    declared = _interface_fields("msg/GestureResult")
    assert {"gesture_label", "error_message"} <= declared
    for never_existed in ("gesture_name", "message"):
        assert never_existed not in declared, (
            f"{never_existed} now exists on GestureResult - update the console and "
            f"this test together"
        )


def test_console_source_does_not_read_known_bad_field_names():
    """Catch a regression at the call site, not just in the definitions."""
    panels = [
        ROOT / "frontend" / "components" / "robot" / "command-center.tsx",
        ROOT / "frontend" / "components" / "robot" / "robot-control.tsx",
    ]
    banned = ("gesture_name", "engagement_score", "msg.score", "msg.value")
    for panel in panels:
        if not panel.exists():
            continue
        text = panel.read_text(encoding="utf-8")
        # Strip comments so the explanatory notes about these names do not trip
        # it. The two passes must not share flags: DOTALL on `//.*` makes a line
        # comment swallow the rest of the FILE, which silently disabled this
        # check the first time it was written.
        code = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        code = re.sub(r"//[^\n]*", "", code)
        for name in banned:
            assert name not in code, (
                f"{panel.name} reads {name!r}, which does not exist on the message"
            )
