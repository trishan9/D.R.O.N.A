import type { Metadata } from "next";
import { Terminal } from "lucide-react";

import { RobotControl } from "@/components/robot/robot-control";
import { Card, CardContent } from "@/components/ui/card";

export const metadata: Metadata = { title: "Robot Control" };

export default function RobotPage() {
  return (
    <div className="space-y-5 animate-fade-in">
      <p className="max-w-3xl text-sm text-muted-foreground">
        A faithful in-browser twin of the D.R.O.N.A. 6-DOF upper-body robot. Every gesture plays the
        <strong className="font-medium text-foreground"> exact keyframe trajectories</strong> the ROS2
        policy executes (greet, nod, point, listen, farewell), with live joint telemetry, the session
        state machine, and engagement estimation. Connect the live bridge to drive the real arm in WSL2.
      </p>

      <RobotControl />

      <Card className="border-dashed">
        <CardContent className="flex items-start gap-3 py-4 text-sm">
          <Terminal className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
          <div className="space-y-1">
            <p className="font-medium">Enable live control (inside WSL2)</p>
            <pre className="overflow-x-auto rounded-lg bg-muted/60 p-3 font-mono text-[11px] leading-relaxed">
{`sudo apt install ros-humble-rosbridge-suite
ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
# (or, standalone):  ros2 launch rosbridge_server rosbridge_websocket_launch.xml`}
            </pre>
            <p className="text-xs text-muted-foreground">
              Then set the bridge URL above (default <code className="font-mono">ws://localhost:9090</code>) and click
              Connect. See <code className="font-mono">docs/wsl_setup.md</code> §9.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
