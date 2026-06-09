"""
Standalone NVIDIA Isaac Sim stage builder for D.R.O.N.A.

Run with Isaac Sim's bundled Python (NOT the ROS2 python):

    cd ~/.local/share/ov/pkg/isaac-sim-*        # or your Isaac install
    ./python.sh <repo>/ros2_ws/src/drona_bringup/isaac/drona_isaac_stage.py \
        --urdf <repo>/ros2_ws/src/drona_description/urdf/drona_humanoid.urdf.xacro

What it does:
    1. Boots a headless-capable Isaac Sim app (SimulationApp).
    2. Imports the D.R.O.N.A. humanoid URDF as an articulation.
    3. Enables the Isaac ROS2 bridge and wires an OmniGraph action graph that:
         - publishes /clock
         - subscribes /drona/joint_states  → drives the articulation targets
         - publishes /isaac/joint_states    (true sim joint state)
    4. Steps the simulation until interrupted.

This is intentionally dependency-isolated: it imports omni.* / pxr, which only
exist inside Isaac's Python. The D.R.O.N.A. ROS2 nodes run in the normal ROS2
environment (see drona_isaac.launch.py) and communicate over the bridge.

REQUIRES Isaac Sim 4.x and ≥ 8 GB VRAM. See docs/sim_setup_isaac.md, including a
cloud-GPU recipe for machines without a capable GPU.
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_URDF_REL = "ros2_ws/src/drona_description/urdf/drona_humanoid.urdf.xacro"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="D.R.O.N.A. Isaac Sim stage builder")
    p.add_argument("--urdf", required=True, help="Path to the D.R.O.N.A. URDF/xacro")
    p.add_argument("--headless", action="store_true", help="Run without the Kit UI")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # 1. SimulationApp MUST be created before importing any other omni modules.
    try:
        from isaacsim import SimulationApp  # Isaac Sim 4.x
    except ImportError:
        try:
            from omni.isaac.kit import SimulationApp  # older Isaac
        except ImportError:
            print(
                "ERROR: omni/isaacsim not found. Run this with Isaac Sim's python.sh, "
                "not the ROS2 python. See docs/sim_setup_isaac.md.",
                file=sys.stderr,
            )
            return 1

    sim_app = SimulationApp({"headless": args.headless})

    # 2. Now safe to import the rest of the Isaac API.
    import omni  # noqa: F401
    from omni.isaac.core import World
    from omni.isaac.core.utils.extensions import enable_extension

    # Enable the ROS2 bridge extension.
    enable_extension("omni.isaac.ros2_bridge")
    sim_app.update()

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()

    # 3. Import the URDF as an articulation.
    #    (xacro must be pre-expanded to plain URDF; see docs for the one-liner.)
    from omni.importer.urdf import _urdf  # type: ignore[import]

    urdf_interface = _urdf.acquire_urdf_interface()
    import_config = _urdf.ImportConfig()
    import_config.merge_fixed_joints = False
    import_config.fix_base = True
    import_config.make_default_prim = True
    status, prim_path = omni.kit.commands.execute(  # type: ignore[attr-defined]
        "URDFParseAndImportFile",
        urdf_path=args.urdf,
        import_config=import_config,
    )
    print(f"Imported D.R.O.N.A. articulation at {prim_path} (status={status})")

    # 4. Build the ROS2 action graph (clock + joint state I/O).
    #    See docs/sim_setup_isaac.md for the full OmniGraph node wiring; we keep a
    #    minimal clock publisher here so the bridge is verifiably live.
    import omni.graph.core as og  # type: ignore[import]

    og.Controller.edit(
        {"graph_path": "/drona_ros_graph", "evaluator_name": "execution"},
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnPlaybackTick"),
                ("PublishClock", "omni.isaac.ros2_bridge.ROS2PublishClock"),
                ("ReadSimTime", "omni.isaac.core_nodes.IsaacReadSimulationTime"),
            ],
            og.Controller.Keys.CONNECT: [
                ("OnTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
            ],
        },
    )

    world.reset()
    print("D.R.O.N.A. Isaac stage ready. Stepping simulation (Ctrl-C to stop)…")
    try:
        while sim_app.is_running():
            world.step(render=not args.headless)
    except KeyboardInterrupt:
        pass
    finally:
        sim_app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
