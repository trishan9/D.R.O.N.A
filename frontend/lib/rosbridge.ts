/**
 * Minimal rosbridge v2 client (zero dependencies).
 *
 * Talks the rosbridge_suite JSON protocol over a WebSocket so the browser can
 * drive the LIVE D.R.O.N.A. ROS2 graph running in WSL2.
 *
 * Enable on the ROS2 side (inside WSL2, Jazzy):
 *   sudo apt install ros-jazzy-rosbridge-suite
 *   ros2 launch rosbridge_server rosbridge_websocket_launch.xml
 *   # or: ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
 *
 * DESIGN NOTES
 * ------------
 * - **One socket per URL.** `sharedBridge()` hands every panel the same client.
 *   Previously each panel constructed its own `RosBridge`, so a page showing two
 *   panels opened two sockets and subscribed to the same topics twice.
 * - **Many callbacks per topic.** Subscriptions are a set, not a single slot.
 *   The previous `Map<topic, callback>` meant a second subscriber to a topic
 *   silently evicted the first - with a shared socket that would be a guaranteed
 *   bug rather than a latent one.
 * - **Throttled by default.** `/drona/joint_states` publishes far faster than a
 *   browser can paint. Subscriptions send `throttle_rate` and `queue_length` so
 *   rosbridge drops messages server-side instead of flooding the socket.
 * - **Canonical ROS2 type strings** (`pkg/msg/Type`). The two-part ROS1 form is
 *   not reliably resolved by rosbridge under ROS2.
 * - **Auto-reconnect** with capped exponential backoff, because an operator
 *   console that stays dead after a transient drop is not an operator console.
 *
 * The whole class degrades gracefully: if nothing is listening on the URL the
 * connection simply never opens and pages stay in local-simulation mode.
 */

export type RosStatus = "disconnected" | "connecting" | "connected" | "error";

type AnyMsg = Record<string, unknown>;
type SubCallback = (msg: AnyMsg) => void;

interface PendingService {
  resolve: (values: AnyMsg) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

interface SubEntry {
  type: string;
  throttleMs: number;
  callbacks: Set<SubCallback>;
}

/** Per-topic liveness, for the telemetry health strip. */
export interface TopicStat {
  topic: string;
  count: number;
  lastSeenMs: number | null;
  hz: number;
}

export interface SubscribeOptions {
  /** Minimum ms between messages, enforced by rosbridge. 0 disables throttling. */
  throttleMs?: number;
  /** How many messages rosbridge may buffer. 1 = always the freshest. */
  queueLength?: number;
}

const RECONNECT_BASE_MS = 750;
const RECONNECT_MAX_MS = 15000;

export class RosBridge {
  private ws: WebSocket | null = null;
  private advertised = new Set<string>();
  private url: string;
  private idCounter = 0;
  private subs = new Map<string, SubEntry>();
  private services = new Map<string, PendingService>();
  private statusCbs = new Set<(s: RosStatus) => void>();
  private stats = new Map<string, { count: number; lastSeen: number; hz: number }>();

  /** Reconnect state. `wantOpen` distinguishes a drop from a deliberate close. */
  private wantOpen = false;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(url: string) {
    this.url = url;
  }

  /** Register a status listener. Returns an unsubscribe function. */
  onStatus(cb: (s: RosStatus) => void): () => void {
    this.statusCbs.add(cb);
    return () => this.statusCbs.delete(cb);
  }

  private emitStatus(s: RosStatus): void {
    for (const cb of this.statusCbs) cb(s);
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  get endpoint(): string {
    return this.url;
  }

  /** Snapshot of per-topic message rates, for the health strip. */
  topicStats(): TopicStat[] {
    const now = Date.now();
    return [...this.subs.keys()].map((topic) => {
      const s = this.stats.get(topic);
      return {
        topic,
        count: s?.count ?? 0,
        lastSeenMs: s ? now - s.lastSeen : null,
        hz: s?.hz ?? 0,
      };
    });
  }

  connect(): void {
    this.wantOpen = true;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.emitStatus("connecting");

    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url);
    } catch {
      this.emitStatus("error");
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.emitStatus("connected");
      // A fresh socket carries no server-side state: re-advertise on demand and
      // re-subscribe everything registered while we were down.
      this.advertised.clear();
      for (const topic of this.subs.keys()) this.sendSubscribe(topic);
    };
    ws.onclose = () => {
      this.emitStatus("disconnected");
      this.scheduleReconnect();
    };
    ws.onerror = () => {
      this.emitStatus("error");
      // onclose fires after onerror and schedules the retry.
    };
    ws.onmessage = (ev) => this.handleMessage(ev.data as string);
  }

  /**
   * Reconnect with capped exponential backoff.
   *
   * Only runs while `wantOpen` - an explicit `disconnect()` must stay
   * disconnected, or "stop the robot" would silently undo itself.
   */
  private scheduleReconnect(): void {
    if (!this.wantOpen || this.reconnectTimer) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.attempt, RECONNECT_MAX_MS);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.wantOpen) this.connect();
    }, delay);
  }

  disconnect(): void {
    this.wantOpen = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    for (const [, p] of this.services) {
      clearTimeout(p.timer);
      p.reject(new Error("disconnected"));
    }
    this.services.clear();
    try {
      this.ws?.close();
    } catch {
      /* noop */
    }
    this.ws = null;
    this.emitStatus("disconnected");
  }

  private send(obj: AnyMsg): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
    }
  }

  private nextId(prefix: string): string {
    this.idCounter += 1;
    return `${prefix}_${this.idCounter}`;
  }

  private sendSubscribe(topic: string): void {
    const entry = this.subs.get(topic);
    if (!entry) return;
    this.send({
      op: "subscribe",
      topic,
      type: entry.type,
      throttle_rate: entry.throttleMs,
      queue_length: 1,
      id: this.nextId("sub"),
    });
  }

  /**
   * Register a callback for a topic. Returns an unsubscribe function.
   *
   * Multiple callers may subscribe to the same topic; each gets every message,
   * and the socket-level subscription is dropped only when the last one leaves.
   */
  subscribe(
    topic: string,
    type: string,
    cb: SubCallback,
    opts: SubscribeOptions = {},
  ): () => void {
    const existing = this.subs.get(topic);
    if (existing) {
      existing.callbacks.add(cb);
    } else {
      this.subs.set(topic, {
        type,
        throttleMs: opts.throttleMs ?? 100,
        callbacks: new Set([cb]),
      });
      if (this.connected) this.sendSubscribe(topic);
    }
    return () => this.removeCallback(topic, cb);
  }

  private removeCallback(topic: string, cb: SubCallback): void {
    const entry = this.subs.get(topic);
    if (!entry) return;
    entry.callbacks.delete(cb);
    if (entry.callbacks.size === 0) {
      this.subs.delete(topic);
      this.stats.delete(topic);
      this.send({ op: "unsubscribe", topic });
    }
  }

  /** Drop a topic entirely, regardless of how many callbacks are attached. */
  unsubscribe(topic: string): void {
    this.subs.delete(topic);
    this.stats.delete(topic);
    this.send({ op: "unsubscribe", topic });
  }

  /**
   * Publish a message, advertising the topic once first.
   *
   * rosbridge requires an `advertise` before the first `publish` on a topic, so
   * repeated calls (a 10 Hz /cmd_vel teleop stream) only pay that once. Silently
   * no-ops when disconnected, so a control panel degrades to "buttons do
   * nothing" instead of throwing.
   */
  publish(topic: string, type: string, msg: AnyMsg): void {
    if (!this.connected) return;
    if (!this.advertised.has(topic)) {
      this.send({ op: "advertise", topic, type, id: this.nextId("adv") });
      this.advertised.add(topic);
    }
    this.send({ op: "publish", topic, msg, id: this.nextId("pub") });
  }

  /** Stop advertising a topic (e.g. when a control panel unmounts). */
  unadvertise(topic: string): void {
    if (!this.advertised.has(topic)) return;
    this.advertised.delete(topic);
    this.send({ op: "unadvertise", topic });
  }

  /** Call a ROS2 service; resolves with the response `values`. */
  callService(service: string, type: string, args: AnyMsg, timeoutMs = 8000): Promise<AnyMsg> {
    return new Promise((resolve, reject) => {
      if (!this.connected) {
        reject(new Error("rosbridge not connected"));
        return;
      }
      const id = this.nextId("svc");
      const timer = setTimeout(() => {
        this.services.delete(id);
        reject(new Error("service call timed out"));
      }, timeoutMs);
      this.services.set(id, { resolve, reject, timer });
      this.send({ op: "call_service", id, service, type, args });
    });
  }

  private recordStat(topic: string): void {
    const now = Date.now();
    const prev = this.stats.get(topic);
    if (!prev) {
      this.stats.set(topic, { count: 1, lastSeen: now, hz: 0 });
      return;
    }
    const dt = (now - prev.lastSeen) / 1000;
    // Exponential moving average, so the readout is stable rather than jittery.
    const instant = dt > 0 ? 1 / dt : prev.hz;
    this.stats.set(topic, {
      count: prev.count + 1,
      lastSeen: now,
      hz: prev.hz === 0 ? instant : prev.hz * 0.7 + instant * 0.3,
    });
  }

  private handleMessage(raw: string): void {
    let data: AnyMsg;
    try {
      data = JSON.parse(raw) as AnyMsg;
    } catch {
      return;
    }
    const op = data.op as string | undefined;
    if (op === "publish") {
      const topic = data.topic as string;
      const entry = this.subs.get(topic);
      if (entry) {
        this.recordStat(topic);
        const msg = (data.msg as AnyMsg) ?? {};
        // Copy before iterating: a callback may unsubscribe itself.
        for (const cb of [...entry.callbacks]) {
          try {
            cb(msg);
          } catch {
            /* one bad panel must not stop the others receiving telemetry */
          }
        }
      }
    } else if (op === "service_response") {
      const id = data.id as string;
      const pending = this.services.get(id);
      if (pending) {
        clearTimeout(pending.timer);
        this.services.delete(id);
        if (data.result === false) {
          pending.reject(new Error(String(data.values ?? "service failed")));
        } else {
          pending.resolve((data.values as AnyMsg) ?? {});
        }
      }
    }
  }
}

/**
 * Process-wide bridge per URL.
 *
 * Every panel shares one socket, so telemetry is subscribed once no matter how
 * many widgets render it, and a reconnect heals the whole dashboard at once.
 */
const bridges = new Map<string, RosBridge>();

export function sharedBridge(url: string): RosBridge {
  let b = bridges.get(url);
  if (!b) {
    b = new RosBridge(url);
    bridges.set(url, b);
  }
  return b;
}

/** Topics the dashboard SUBSCRIBES to, with the canonical ROS2 type strings. */
export const DRONA_TOPICS = {
  jointStates: { name: "/drona/joint_states", type: "sensor_msgs/msg/JointState" },
  sessionState: { name: "/drona/session_state", type: "drona_msgs/msg/SessionState" },
  engagement: { name: "/drona/engagement", type: "drona_msgs/msg/EngagementDetection" },
  advisingResponse: {
    name: "/drona/advising_response",
    type: "drona_msgs/msg/AdvisingResponse",
  },
  gestureResult: { name: "/drona/gesture_result", type: "drona_msgs/msg/GestureResult" },
  diagnostics: { name: "/diagnostics", type: "diagnostic_msgs/msg/DiagnosticArray" },
} as const;

/** Topics the control centre PUBLISHES to (command surface). */
export const DRONA_COMMAND_TOPICS = {
  cmdVel: { name: "/cmd_vel", type: "geometry_msgs/msg/Twist" },
  gesture: { name: "/drona/gesture_command", type: "drona_msgs/msg/GestureCommand" },
  ask: { name: "/drona/ask", type: "std_msgs/msg/String" },
  say: { name: "/drona/say", type: "std_msgs/msg/String" },
} as const;

/** Zero-velocity Twist - the emergency stop payload. */
export function zeroTwist() {
  return {
    linear: { x: 0, y: 0, z: 0 },
    angular: { x: 0, y: 0, z: 0 },
  };
}

export function twist(linearX: number, angularZ: number) {
  return {
    linear: { x: linearX, y: 0, z: 0 },
    angular: { x: 0, y: 0, z: angularZ },
  };
}

export const DRONA_GESTURE_SERVICE = {
  name: "/drona/execute_gesture",
  type: "drona_msgs/srv/ExecuteGesture",
} as const;

/** DiagnosticStatus.level values from diagnostic_msgs. */
export const DIAGNOSTIC_LEVELS = ["OK", "WARN", "ERROR", "STALE"] as const;

export function diagnosticLevelName(level: number | string | undefined): string {
  const n = typeof level === "string" ? level.charCodeAt(0) : (level ?? 0);
  return DIAGNOSTIC_LEVELS[n] ?? "OK";
}
