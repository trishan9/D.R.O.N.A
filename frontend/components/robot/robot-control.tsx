"use client";

import * as React from "react";
import {
  Play,
  Square,
  Wifi,
  WifiOff,
  Cpu,
  Radio,
  Sparkles,
  CircleDot,
} from "lucide-react";

import {
  GESTURES,
  GESTURE_META,
  REST_POSE,
  gestureTrajectory,
  gestureDurationSeconds,
  type GestureName,
  type TrajFrame,
} from "@/lib/robot";
import { RosBridge, type RosStatus, DRONA_TOPICS, DRONA_GESTURE_SERVICE } from "@/lib/rosbridge";
import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { RobotArm } from "./robot-arm";
import { JointTelemetry } from "./joint-telemetry";
import { SessionFsm, type SessionStateId } from "./session-fsm";
import { EngagementGauge } from "./engagement-gauge";

const GESTURE_TO_STATE: Record<GestureName, SessionStateId> = {
  idle: "IDLE",
  greet: "GREETING",
  listen: "NEEDS_ASSESSMENT",
  nod: "ADVISING",
  point: "ADVISING",
  farewell: "CLOSURE",
};

export function RobotControl() {
  const { prefs, setPrefs } = useStore();
  const [joints, setJoints] = React.useState<number[]>(REST_POSE);
  const [mode, setMode] = React.useState<"sim" | "live">("sim");
  const [rosStatus, setRosStatus] = React.useState<RosStatus>("disconnected");
  const [gesture, setGesture] = React.useState<GestureName | null>(null);
  const [progress, setProgress] = React.useState(0);
  const [session, setSession] = React.useState<SessionStateId>("IDLE");
  const [engagement, setEngagement] = React.useState(0.7);
  const [busy, setBusy] = React.useState(false);
  const [log, setLog] = React.useState<string[]>([]);

  const rafRef = React.useRef<number | null>(null);
  const tokenRef = React.useRef(0);
  const bridgeRef = React.useRef<RosBridge | null>(null);
  const cancelledRef = React.useRef(false);

  const addLog = React.useCallback((line: string) => {
    const t = new Date().toLocaleTimeString();
    setLog((l) => [`${t}  ${line}`, ...l].slice(0, 60));
  }, []);

  // Cleanup on unmount.
  React.useEffect(() => {
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      bridgeRef.current?.disconnect();
    };
  }, []);

  // ── Simulation player (RAF, real-time playback of the keyframe trajectory) ──
  const animate = React.useCallback(
    (traj: TrajFrame[]) =>
      new Promise<void>((resolve) => {
        const token = ++tokenRef.current;
        const total = traj[traj.length - 1]?.t || 0.001;
        const start = performance.now();
        const step = (now: number) => {
          if (token !== tokenRef.current) return resolve();
          const elapsed = (now - start) / 1000;
          let i = traj.findIndex((f) => f.t >= elapsed);
          if (i === -1) i = traj.length - 1;
          setJoints(traj[i].q);
          setProgress(Math.min(elapsed / total, 1));
          if (elapsed >= total) {
            setJoints(traj[traj.length - 1].q);
            return resolve();
          }
          rafRef.current = requestAnimationFrame(step);
        };
        rafRef.current = requestAnimationFrame(step);
      }),
    [],
  );

  const playSim = React.useCallback(
    async (name: GestureName) => {
      setGesture(name);
      setSession(GESTURE_TO_STATE[name]);
      addLog(`▶ gesture '${name}' (${gestureDurationSeconds(name).toFixed(2)}s) — sim`);
      await animate(gestureTrajectory(name));
      setProgress(0);
      setGesture(null);
    },
    [animate, addLog],
  );

  const playLive = React.useCallback(
    async (name: GestureName) => {
      const bridge = bridgeRef.current;
      if (!bridge?.connected) return;
      setGesture(name);
      setSession(GESTURE_TO_STATE[name]);
      addLog(`▶ call ${DRONA_GESTURE_SERVICE.name} {gesture_label:'${name}'} — live`);
      try {
        await bridge.callService(DRONA_GESTURE_SERVICE.name, DRONA_GESTURE_SERVICE.type, {
          gesture_label: name,
        });
        addLog(`✓ '${name}' completed on robot`);
      } catch (e) {
        addLog(`✗ ${(e as Error).message}`);
      }
      setGesture(null);
    },
    [addLog],
  );

  const runGesture = React.useCallback(
    (name: GestureName) => (mode === "live" ? playLive(name) : playSim(name)),
    [mode, playLive, playSim],
  );

  const onGestureClick = async (name: GestureName) => {
    if (busy) return;
    setBusy(true);
    await runGesture(name);
    setBusy(false);
    if (mode === "sim") setSession("IDLE");
  };

  const stop = () => {
    tokenRef.current++;
    cancelledRef.current = true;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    setBusy(false);
    setGesture(null);
    setProgress(0);
    addLog("■ stopped");
  };

  // ── Full autonomous session: idle → greet → assess → advise → close ────────
  const runSession = async () => {
    if (busy) return;
    setBusy(true);
    cancelledRef.current = false;
    addLog("● running full session");
    const sequence: GestureName[] = ["greet", "listen", "point", "farewell"];
    for (const g of sequence) {
      if (cancelledRef.current) break;
      await runGesture(g);
      await new Promise((r) => setTimeout(r, 250));
    }
    if (!cancelledRef.current) {
      setSession("IDLE");
      setJoints(REST_POSE);
      addLog("✓ session complete");
    }
    setBusy(false);
  };

  // ── Live ROS2 bridge ───────────────────────────────────────────────────────
  const connect = () => {
    bridgeRef.current?.disconnect();
    const bridge = new RosBridge(prefs.rosbridgeUrl);
    bridge.onStatus((s) => {
      setRosStatus(s);
      if (s === "connected") {
        addLog(`✓ rosbridge connected → ${prefs.rosbridgeUrl}`);
        setMode("live");
      } else if (s === "error") addLog("✗ rosbridge connection error");
      else if (s === "disconnected") addLog("rosbridge disconnected");
    });
    bridge.subscribe(DRONA_TOPICS.jointStates, "sensor_msgs/JointState", (msg) => {
      const pos = msg.position as number[] | undefined;
      if (Array.isArray(pos) && pos.length >= 6) setJoints(pos.slice(0, 6));
    });
    bridge.subscribe(DRONA_TOPICS.engagement, "drona_msgs/EngagementDetection", (msg) => {
      const score = (msg.engagement_score ?? msg.score ?? msg.value) as number | undefined;
      if (typeof score === "number") setEngagement(Math.max(0, Math.min(1, score)));
    });
    bridge.subscribe(DRONA_TOPICS.sessionState, "drona_msgs/SessionState", (msg) => {
      const raw = (msg.state ?? msg.current_state ?? msg.session_state) as string | undefined;
      if (raw) {
        const up = raw.toUpperCase();
        const match = (["IDLE", "GREETING", "NEEDS_ASSESSMENT", "ADVISING", "CLOSURE"] as SessionStateId[]).find(
          (s) => up.includes(s),
        );
        if (match) setSession(match);
      }
    });
    bridge.connect();
    bridgeRef.current = bridge;
  };

  const disconnect = () => {
    bridgeRef.current?.disconnect();
    bridgeRef.current = null;
    setMode("sim");
    setJoints(REST_POSE);
  };

  const live = rosStatus === "connected";

  return (
    <div className="grid gap-4 lg:grid-cols-12">
      {/* Stage */}
      <Card className="overflow-hidden lg:col-span-5">
        <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 border-b">
          <CardTitle className="flex items-center gap-2 text-base">
            <Cpu className="h-4 w-4 text-brand" /> Robot stage
          </CardTitle>
          <Badge variant={live ? "default" : "secondary"} className="gap-1">
            {live ? <Radio className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}
            {live ? "Live ROS2" : "Simulation"}
          </Badge>
        </CardHeader>
        <CardContent className="relative p-0">
          <div className="bg-grid relative aspect-square w-full">
            <RobotArm joints={joints} engagement={engagement} active={!!gesture || busy} />
            {gesture && (
              <div className="absolute bottom-3 left-1/2 w-[80%] -translate-x-1/2">
                <div className="mb-1 flex items-center justify-between text-xs font-medium">
                  <span className="capitalize">{GESTURE_META[gesture].label}</span>
                  <span className="tabular-nums text-muted-foreground">{Math.round(progress * 100)}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${progress * 100}%` }} />
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Controls */}
      <div className="space-y-4 lg:col-span-7">
        {/* Gesture controls */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-base">Gesture control</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {GESTURES.map((g) => (
                <button
                  key={g}
                  disabled={busy || (mode === "live" && !live)}
                  onClick={() => onGestureClick(g)}
                  className={cn(
                    "flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-colors disabled:opacity-50",
                    gesture === g ? "border-brand bg-brand/5" : "hover:border-brand/50 hover:bg-accent/50",
                  )}
                >
                  <span className="text-lg leading-none">{GESTURE_META[g].icon}</span>
                  <span className="text-sm font-semibold">{GESTURE_META[g].label}</span>
                  <span className="text-[11px] leading-tight text-muted-foreground">{GESTURE_META[g].blurb}</span>
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={runSession} disabled={busy || (mode === "live" && !live)}>
                <Sparkles className="h-4 w-4" /> Run full session
              </Button>
              <Button variant="outline" onClick={stop} disabled={!busy}>
                <Square className="h-4 w-4" /> Stop
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setJoints(REST_POSE);
                  setSession("IDLE");
                }}
                disabled={busy}
              >
                <Play className="h-4 w-4" /> Rest pose
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Session FSM */}
        <Card>
          <CardHeader className="border-b py-3">
            <CardTitle className="text-sm font-semibold text-muted-foreground">Session state machine</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <SessionFsm current={session} />
          </CardContent>
        </Card>

        {/* Telemetry + engagement */}
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader className="border-b py-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">Joint telemetry (6-DOF)</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <JointTelemetry joints={joints} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="border-b py-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">Engagement</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-4">
              <EngagementGauge value={engagement} />
              <div>
                <p className="mb-1 text-xs text-muted-foreground">
                  {live ? "From /drona/engagement (live)" : "Simulated — drag to set"}
                </p>
                <Slider
                  value={[engagement * 100]}
                  onValueChange={(v) => setEngagement(v[0] / 100)}
                  min={0}
                  max={100}
                  step={1}
                  disabled={live}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Live connection */}
        <Card>
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              {live ? <Wifi className="h-4 w-4 text-success" /> : <WifiOff className="h-4 w-4" />}
              Live ROS2 bridge
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            <p className="text-xs text-muted-foreground">
              Connect to the ROS2 graph running in WSL2 via rosbridge. The arm then mirrors
              <code className="mx-1 rounded bg-muted px-1 font-mono">/drona/joint_states</code> and gestures call the
              <code className="mx-1 rounded bg-muted px-1 font-mono">/drona/execute_gesture</code> service.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                value={prefs.rosbridgeUrl}
                onChange={(e) => setPrefs({ rosbridgeUrl: e.target.value })}
                placeholder="ws://localhost:9090"
                className="h-9 max-w-[16rem] font-mono text-xs"
              />
              {live ? (
                <Button variant="outline" size="sm" onClick={disconnect}>
                  <WifiOff className="h-4 w-4" /> Disconnect
                </Button>
              ) : (
                <Button size="sm" onClick={connect} disabled={rosStatus === "connecting"}>
                  <Wifi className="h-4 w-4" />
                  {rosStatus === "connecting" ? "Connecting…" : "Connect"}
                </Button>
              )}
              <StatusDot status={rosStatus} />
            </div>
            <pre className="max-h-32 overflow-y-auto rounded-lg bg-muted/50 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
              {log.length === 0 ? "// activity log" : log.join("\n")}
            </pre>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: RosStatus }) {
  const map: Record<RosStatus, { c: string; t: string }> = {
    connected: { c: "bg-success", t: "connected" },
    connecting: { c: "bg-warning animate-pulse", t: "connecting" },
    error: { c: "bg-destructive", t: "error" },
    disconnected: { c: "bg-muted-foreground", t: "offline" },
  };
  const m = map[status];
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={cn("h-2 w-2 rounded-full", m.c)} /> {m.t}
    </span>
  );
}
