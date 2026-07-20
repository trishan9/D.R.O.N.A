"use client";

/**
 * D.R.O.N.A. Mission Control - a real ROS2 operator console.
 *
 * Unlike the twin viewer (which can simulate locally), everything here is a
 * genuine ROS2 command over rosbridge:
 *   /cmd_vel                  drive the mobile base (held-key teleop @10 Hz)
 *   /drona/gesture_command    play a gesture on the arm
 *   /drona/ask                inject a student question into the session
 *   /drona/say                make the robot speak
 * and it subscribes to joint states, engagement and session state for telemetry.
 *
 * Safety-first, as an operator console must be:
 *   - every control is DISABLED until rosbridge is actually connected, so a
 *     button never silently does nothing;
 *   - teleop publishes only while a key/button is held and always sends a zero
 *     Twist on release, on blur, and on unmount (no runaway base);
 *   - E-STOP is always reachable and spams zero-velocity.
 */

import * as React from "react";
import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Gauge,
  HeartPulse,
  MessageSquare,
  OctagonX,
  Radio,
  Volume2,
} from "lucide-react";

import {
  DRONA_COMMAND_TOPICS,
  DRONA_TOPICS,
  diagnosticLevelName,
  sharedBridge,
  twist,
  zeroTwist,
  type RosBridge,
  type RosStatus,
  type TopicStat,
} from "@/lib/rosbridge";
import { GESTURES, JOINT_SHORT } from "@/lib/robot";
import { useStore } from "@/lib/store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";

const TELEOP_HZ = 10;

function StatusPill({ status }: { status: RosStatus }) {
  const map: Record<RosStatus, { label: string; cls: string }> = {
    connected: { label: "LINK UP", cls: "bg-tier-nepal/15 text-tier-nepal" },
    connecting: { label: "LINKING", cls: "bg-amber-500/15 text-amber-600" },
    disconnected: { label: "LINK DOWN", cls: "bg-muted text-muted-foreground" },
    error: { label: "LINK ERROR", cls: "bg-destructive/15 text-destructive" },
  };
  const m = map[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 font-mono text-[10px] ${m.cls}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {m.label}
    </span>
  );
}

/** One entry of a diagnostic_msgs/DiagnosticArray. */
interface DiagStatus {
  name?: string;
  level?: number | string;
  message?: string;
  hardware_id?: string;
}

export function CommandCenter() {
  const { prefs } = useStore();
  const bridgeRef = React.useRef<RosBridge | null>(null);
  const [status, setStatus] = React.useState<RosStatus>("disconnected");
  const [joints, setJoints] = React.useState<number[] | null>(null);
  const [engagement, setEngagement] = React.useState<{ state?: string; distance_m?: number } | null>(null);
  const [session, setSession] = React.useState<string>("—");
  const [log, setLog] = React.useState<string[]>([]);
  const [speed, setSpeed] = React.useState(0.25);
  const [turn, setTurn] = React.useState(0.6);
  const [askText, setAskText] = React.useState("");
  const [sayText, setSayText] = React.useState("");
  const [diagnostics, setDiagnostics] = React.useState<DiagStatus[]>([]);
  const [topicStats, setTopicStats] = React.useState<TopicStat[]>([]);
  const [lastAdvice, setLastAdvice] = React.useState<{
    summary: string;
    nPathways: number;
    nBiasFlags: number;
  } | null>(null);

  const connected = status === "connected";

  const addLog = React.useCallback((line: string) => {
    const ts = new Date().toLocaleTimeString();
    setLog((l) => [`[${ts}] ${line}`, ...l].slice(0, 60));
  }, []);

  // ── Connect + telemetry subscriptions ──────────────────────────────────────
  React.useEffect(() => {
    const bridge = sharedBridge(prefs.rosbridgeUrl);
    bridgeRef.current = bridge;

    // Every registration returns its own detach function. The socket is shared
    // with other panels, so cleanup releases THIS panel's handles and never
    // closes the connection out from under them.
    const detach: Array<() => void> = [];

    detach.push(
      bridge.onStatus((s) => {
        setStatus(s);
        addLog(`rosbridge ${s}`);
      }),
    );
    detach.push(
      // Joint states arrive far faster than the panel repaints; 100 ms is
      // smooth to the eye and keeps the socket quiet.
      bridge.subscribe(
        DRONA_TOPICS.jointStates.name,
        DRONA_TOPICS.jointStates.type,
        (m) => {
          const pos = (m.position as number[]) ?? null;
          if (pos) setJoints(pos);
        },
        { throttleMs: 100 },
      ),
    );
    detach.push(
      bridge.subscribe(DRONA_TOPICS.engagement.name, DRONA_TOPICS.engagement.type, (m) => {
        setEngagement({ state: m.state as string, distance_m: m.distance_m as number });
      }),
    );
    detach.push(
      bridge.subscribe(DRONA_TOPICS.sessionState.name, DRONA_TOPICS.sessionState.type, (m) => {
        setSession((m.state as string) ?? "—");
      }),
    );
    detach.push(
      // Field names verified against `ros2 interface show drona_msgs/msg/GestureResult`:
      // gesture_label / success / policy_used / error_message.
      bridge.subscribe(DRONA_TOPICS.gestureResult.name, DRONA_TOPICS.gestureResult.type, (m) => {
        const ok = Boolean(m.success);
        const label = (m.gesture_label as string) || "gesture";
        const policy = (m.policy_used as string) || "";
        const err = (m.error_message as string) || "";
        const detail = ok ? (policy ? ` via ${policy}` : "") : err ? ` - ${err}` : "";
        addLog(`${ok ? "✓" : "✗"} ${label}${detail}`);
      }),
    );
    detach.push(
      bridge.subscribe(
        DRONA_TOPICS.diagnostics.name,
        DRONA_TOPICS.diagnostics.type,
        (m) => {
          const status = (m.status as DiagStatus[]) ?? [];
          setDiagnostics(status);
        },
        { throttleMs: 1000 },
      ),
    );
    detach.push(
      bridge.subscribe(
        DRONA_TOPICS.advisingResponse.name,
        DRONA_TOPICS.advisingResponse.type,
        (m) => {
          setLastAdvice({
            summary: (m.summary as string) ?? "",
            nPathways: Array.isArray(m.pathways) ? m.pathways.length : 0,
            nBiasFlags: Array.isArray(m.bias_flags) ? m.bias_flags.length : 0,
          });
          addLog(`advice received (${Array.isArray(m.pathways) ? m.pathways.length : 0} pathways)`);
        },
      ),
    );

    bridge.connect();

    return () => {
      // Never leave the base moving when the console unmounts.
      try {
        bridge.publish(DRONA_COMMAND_TOPICS.cmdVel.name, DRONA_COMMAND_TOPICS.cmdVel.type, zeroTwist());
      } catch {
        /* noop */
      }
      for (const off of detach) off();
      bridgeRef.current = null;
    };
  }, [prefs.rosbridgeUrl, addLog]);

  // Refresh the topic-rate strip on a timer; the bridge accumulates the counts.
  React.useEffect(() => {
    const t = setInterval(() => {
      setTopicStats(bridgeRef.current?.topicStats() ?? []);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // ── Teleop: publish while held, zero on release ────────────────────────────
  const driveRef = React.useRef<{ lin: number; ang: number } | null>(null);
  React.useEffect(() => {
    const id = setInterval(() => {
      const b = bridgeRef.current;
      const d = driveRef.current;
      if (!b || !b.connected || !d) return;
      b.publish(DRONA_COMMAND_TOPICS.cmdVel.name, DRONA_COMMAND_TOPICS.cmdVel.type, twist(d.lin, d.ang));
    }, 1000 / TELEOP_HZ);
    return () => clearInterval(id);
  }, []);

  const startDrive = (lin: number, ang: number, label: string) => {
    driveRef.current = { lin, ang };
    addLog(`cmd_vel ${label} (v=${lin.toFixed(2)} w=${ang.toFixed(2)})`);
  };
  const stopDrive = React.useCallback(() => {
    if (!driveRef.current) return;
    driveRef.current = null;
    bridgeRef.current?.publish(
      DRONA_COMMAND_TOPICS.cmdVel.name,
      DRONA_COMMAND_TOPICS.cmdVel.type,
      zeroTwist(),
    );
  }, []);

  // Release the base if the window loses focus mid-press.
  React.useEffect(() => {
    window.addEventListener("blur", stopDrive);
    return () => window.removeEventListener("blur", stopDrive);
  }, [stopDrive]);

  const eStop = () => {
    driveRef.current = null;
    const b = bridgeRef.current;
    for (let i = 0; i < 5; i += 1) {
      b?.publish(DRONA_COMMAND_TOPICS.cmdVel.name, DRONA_COMMAND_TOPICS.cmdVel.type, zeroTwist());
    }
    addLog("*** E-STOP - zero velocity latched ***");
  };

  const sendGesture = (g: string) => {
    bridgeRef.current?.publish(DRONA_COMMAND_TOPICS.gesture.name, DRONA_COMMAND_TOPICS.gesture.type, {
      stamp: { sec: 0, nanosec: 0 },
      gesture_label: g,
      target_x: 0,
      target_y: 0,
      target_z: 0,
      policy_hint: "",
    });
    addLog(`gesture_command → ${g}`);
  };

  const sendString = (which: "ask" | "say", text: string) => {
    const t = text.trim();
    if (!t) return;
    const topic = which === "ask" ? DRONA_COMMAND_TOPICS.ask : DRONA_COMMAND_TOPICS.say;
    bridgeRef.current?.publish(topic.name, topic.type, { data: t });
    addLog(`${topic.name} → "${t.slice(0, 48)}"`);
    if (which === "ask") setAskText("");
    else setSayText("");
  };

  const DirBtn = ({
    icon: Icon,
    lin,
    ang,
    label,
  }: {
    icon: typeof ArrowUp;
    lin: number;
    ang: number;
    label: string;
  }) => (
    <Button
      variant="outline"
      size="icon"
      disabled={!connected}
      className="h-12 w-12 active:scale-95"
      onPointerDown={() => startDrive(lin, ang, label)}
      onPointerUp={stopDrive}
      onPointerLeave={stopDrive}
      aria-label={label}
    >
      <Icon className="h-5 w-5" />
    </Button>
  );

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <Card className="border-border/70">
        <CardContent className="flex flex-wrap items-center gap-3 py-3 font-mono text-xs">
          <StatusPill status={status} />
          <span className="text-muted-foreground">{prefs.rosbridgeUrl}</span>
          <span className="ml-auto flex flex-wrap items-center gap-3">
            <span>
              SESSION <Badge variant="outline" className="ml-1 font-mono text-[10px]">{session}</Badge>
            </span>
            <span>
              ENGAGEMENT{" "}
              <Badge variant="outline" className="ml-1 font-mono text-[10px]">
                {engagement?.state ?? "—"}
                {engagement?.distance_m ? ` @ ${engagement.distance_m.toFixed(2)}m` : ""}
              </Badge>
            </span>
          </span>
          <Button variant="destructive" size="sm" onClick={eStop} className="gap-1.5">
            <OctagonX className="h-4 w-4" />
            E-STOP
          </Button>
        </CardContent>
      </Card>

      {!connected ? (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardContent className="py-3 text-xs text-muted-foreground">
            Controls are disabled until rosbridge connects. Start it in WSL2:
            <pre className="mt-2 overflow-x-auto rounded bg-muted/50 p-2 text-[11px]">
{`sudo apt install ros-jazzy-rosbridge-suite
ros2 launch rosbridge_server rosbridge_websocket_launch.xml`}
            </pre>
            Set the URL in Preferences (default <code>ws://localhost:9090</code>).
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Base teleop */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Radio className="h-4 w-4" /> Mobile base
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col items-center gap-2">
              <DirBtn icon={ArrowUp} lin={speed} ang={0} label="forward" />
              <div className="flex gap-2">
                <DirBtn icon={ArrowLeft} lin={0} ang={turn} label="rotate left" />
                <Button
                  variant="secondary"
                  size="icon"
                  className="h-12 w-12"
                  disabled={!connected}
                  onClick={stopDrive}
                  aria-label="stop"
                >
                  <span className="text-[10px] font-mono">STOP</span>
                </Button>
                <DirBtn icon={ArrowRight} lin={0} ang={-turn} label="rotate right" />
              </div>
              <DirBtn icon={ArrowDown} lin={-speed} ang={0} label="reverse" />
            </div>
            <div className="space-y-3 pt-2">
              <div>
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>Linear</span>
                  <span className="font-mono">{speed.toFixed(2)} m/s</span>
                </div>
                <Slider
                  value={[speed]}
                  min={0.05}
                  max={0.5}
                  step={0.05}
                  onValueChange={([v]) => setSpeed(v)}
                />
              </div>
              <div>
                <div className="flex justify-between text-[11px] text-muted-foreground">
                  <span>Angular</span>
                  <span className="font-mono">{turn.toFixed(2)} rad/s</span>
                </div>
                <Slider value={[turn]} min={0.1} max={1.5} step={0.1} onValueChange={([v]) => setTurn(v)} />
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground">
              Publishes /cmd_vel at {TELEOP_HZ} Hz while held; zero Twist on release.
            </p>
          </CardContent>
        </Card>

        {/* Gestures + speech */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Activity className="h-4 w-4" /> Gestures &amp; voice
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-2">
              {GESTURES.map((g) => (
                <Button
                  key={g}
                  variant="outline"
                  size="sm"
                  disabled={!connected}
                  onClick={() => sendGesture(g)}
                  className="text-xs capitalize"
                >
                  {g}
                </Button>
              ))}
            </div>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  value={askText}
                  onChange={(e) => setAskText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendString("ask", askText)}
                  placeholder="Ask the robot (→ /drona/ask)"
                  disabled={!connected}
                  className="text-xs"
                />
                <Button size="icon" variant="secondary" disabled={!connected} onClick={() => sendString("ask", askText)}>
                  <MessageSquare className="h-4 w-4" />
                </Button>
              </div>
              <div className="flex gap-2">
                <Input
                  value={sayText}
                  onChange={(e) => setSayText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendString("say", sayText)}
                  placeholder="Make it speak (→ /drona/say)"
                  disabled={!connected}
                  className="text-xs"
                />
                <Button size="icon" variant="secondary" disabled={!connected} onClick={() => sendString("say", sayText)}>
                  <Volume2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Telemetry */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Joint telemetry</CardTitle>
          </CardHeader>
          <CardContent>
            {joints ? (
              <div className="space-y-1.5 font-mono text-[11px]">
                {JOINT_SHORT.map((name, i) => (
                  <div key={name} className="flex items-center gap-2">
                    <span className="w-20 text-muted-foreground">{name}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded bg-muted">
                      <div
                        className="h-full bg-primary"
                        style={{
                          width: `${Math.min(100, Math.abs((joints[i] ?? 0) / Math.PI) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="w-14 text-right">{(joints[i] ?? 0).toFixed(3)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No /drona/joint_states yet - start the sim or hardware bring-up.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Node health, straight from /diagnostics. */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <HeartPulse className="h-4 w-4" /> Node health
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                /diagnostics
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {diagnostics.length > 0 ? (
              <div className="space-y-1.5">
                {diagnostics.map((d, i) => {
                  const level = diagnosticLevelName(d.level);
                  const cls =
                    level === "OK"
                      ? "bg-tier-nepal/15 text-tier-nepal"
                      : level === "WARN"
                        ? "bg-amber-500/15 text-amber-600"
                        : "bg-destructive/15 text-destructive";
                  return (
                    <div key={i} className="flex items-center gap-2 text-[11px]">
                      <span className={`rounded px-1.5 py-0.5 font-mono ${cls}`}>{level}</span>
                      <span className="truncate font-medium">{d.name ?? "unnamed"}</span>
                      <span className="ml-auto truncate text-muted-foreground">{d.message}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                No /diagnostics yet - the diagnostics node aggregates per-stream liveness once the
                graph is up.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Per-topic message rates: proves the link is live, not just open. */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Gauge className="h-4 w-4" /> Topic rates
            </CardTitle>
          </CardHeader>
          <CardContent>
            {topicStats.some((t) => t.count > 0) ? (
              <div className="space-y-1.5 font-mono text-[11px]">
                {topicStats
                  .filter((t) => t.count > 0)
                  .map((t) => {
                    const stale = t.lastSeenMs !== null && t.lastSeenMs > 5000;
                    return (
                      <div key={t.topic} className="flex items-center gap-2">
                        <span className="truncate text-muted-foreground">{t.topic}</span>
                        <span className="ml-auto tabular-nums">
                          {t.hz >= 0.1 ? `${t.hz.toFixed(1)} Hz` : "—"}
                        </span>
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                            stale ? "bg-muted-foreground/40" : "bg-tier-nepal"
                          }`}
                          title={stale ? "no message in >5 s" : "live"}
                        />
                      </div>
                    );
                  })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Connected topics will report their measured publish rate here.
              </p>
            )}
          </CardContent>
        </Card>

        {/* What the robot last advised - closes the ask -> advise loop on-screen. */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm">
              <MessageSquare className="h-4 w-4" /> Last advice from the robot
              <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                /drona/advising_response
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lastAdvice ? (
              <div className="space-y-2">
                <p className="text-sm">{lastAdvice.summary || "(no summary)"}</p>
                <div className="flex gap-2">
                  <Badge variant="secondary" className="text-[10px]">
                    {lastAdvice.nPathways} pathways
                  </Badge>
                  <Badge
                    variant={lastAdvice.nBiasFlags ? "default" : "outline"}
                    className="text-[10px]"
                  >
                    {lastAdvice.nBiasFlags} bias flags
                  </Badge>
                </div>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Send a question with <span className="font-mono">Ask</span> above; the advice the
                robot produces appears here.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Command log */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Command log</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-52 overflow-y-auto rounded bg-muted/40 p-2 font-mono text-[11px] leading-5">
            {log.length ? (
              log.map((l, i) => (
                <div key={i} className={l.includes("E-STOP") ? "text-destructive" : ""}>
                  {l}
                </div>
              ))
            ) : (
              <span className="text-muted-foreground">no commands issued yet</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
