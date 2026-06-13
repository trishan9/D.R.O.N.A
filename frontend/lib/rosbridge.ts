/**
 * Minimal rosbridge v2 client (zero dependencies).
 *
 * Talks the rosbridge_suite JSON protocol over a WebSocket so the browser can
 * drive the LIVE D.R.O.N.A. ROS2 graph running in WSL2:
 *
 *   - subscribe /drona/joint_states  (sensor_msgs/JointState)  → live arm
 *   - subscribe /drona/session_state (drona_msgs/SessionState) → live FSM
 *   - subscribe /drona/engagement    (drona_msgs/EngagementDetection)
 *   - call /drona/execute_gesture    (drona_msgs/ExecuteGesture srv) → gesture
 *
 * Enable on the ROS2 side (inside WSL2):
 *   sudo apt install ros-humble-rosbridge-suite
 *   ros2 launch rosbridge_server rosbridge_websocket_launch.xml
 *   # or: ros2 launch drona_bringup drona_system.launch.py rosbridge:=true
 *
 * The whole class degrades gracefully: if nothing is listening on the URL the
 * connection simply never opens and the page stays in local-simulation mode.
 */

export type RosStatus = "disconnected" | "connecting" | "connected" | "error";

type AnyMsg = Record<string, unknown>;
type SubCallback = (msg: AnyMsg) => void;

interface PendingService {
  resolve: (values: AnyMsg) => void;
  reject: (err: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export class RosBridge {
  private ws: WebSocket | null = null;
  private url: string;
  private idCounter = 0;
  private subs = new Map<string, SubCallback>();
  private services = new Map<string, PendingService>();
  private statusCb?: (s: RosStatus) => void;

  constructor(url: string) {
    this.url = url;
  }

  onStatus(cb: (s: RosStatus) => void) {
    this.statusCb = cb;
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  connect(): void {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    this.statusCb?.("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.url);
    } catch {
      this.statusCb?.("error");
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.statusCb?.("connected");
      // Re-subscribe everything that was registered before connect.
      for (const topic of this.subs.keys()) this.sendSubscribe(topic);
    };
    ws.onclose = () => {
      this.statusCb?.("disconnected");
    };
    ws.onerror = () => {
      this.statusCb?.("error");
    };
    ws.onmessage = (ev) => this.handleMessage(ev.data);
  }

  disconnect(): void {
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
    this.statusCb?.("disconnected");
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
    this.send({ op: "subscribe", topic, id: this.nextId("sub") });
  }

  /** Register a subscription. Subscribes immediately if already connected. */
  subscribe(topic: string, _type: string, cb: SubCallback): void {
    this.subs.set(topic, cb);
    if (this.connected) this.sendSubscribe(topic);
  }

  unsubscribe(topic: string): void {
    this.subs.delete(topic);
    this.send({ op: "unsubscribe", topic });
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
      const cb = this.subs.get(topic);
      if (cb) cb((data.msg as AnyMsg) ?? {});
    } else if (op === "service_response") {
      const id = data.id as string;
      const pending = this.services.get(id);
      if (pending) {
        clearTimeout(pending.timer);
        this.services.delete(id);
        if (data.result === false) {
          pending.reject(new Error((data.values as AnyMsg)?.toString?.() ?? "service failed"));
        } else {
          pending.resolve((data.values as AnyMsg) ?? {});
        }
      }
    }
  }
}

export const DRONA_TOPICS = {
  jointStates: "/drona/joint_states",
  sessionState: "/drona/session_state",
  engagement: "/drona/engagement",
} as const;

export const DRONA_GESTURE_SERVICE = {
  name: "/drona/execute_gesture",
  type: "drona_msgs/ExecuteGesture",
} as const;
