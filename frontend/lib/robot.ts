/**
 * Robot kinematics + gesture model - a faithful TypeScript port of
 * `drona/interaction/demonstration.py`.
 *
 * The joint convention, limits, rest pose, and keyframe trajectories below are
 * copied 1:1 from the Python source so the in-browser "robot twin" plays the
 * EXACT same motions the ROS2 `policy_node` / `gesture_node` execute on the
 * 6-DOF arm. When the page is connected to a live ROS2 graph (rosbridge), the
 * same joint vector arrives over /drona/joint_states and drives the same render.
 *
 *   j0 - base rotation (yaw)        ±π
 *   j1 - shoulder pitch             ±π/2
 *   j2 - elbow pitch                ±π
 *   j3 - wrist pitch                ±π/2
 *   j4 - wrist roll                 ±π
 *   j5 - gripper (0 open .. 1 closed)
 */

export const DOF = 6;

export const JOINT_NAMES = [
  "j0_base_yaw",
  "j1_shoulder",
  "j2_elbow",
  "j3_wrist_pitch",
  "j4_wrist_roll",
  "j5_gripper",
] as const;

export const JOINT_SHORT = ["Base yaw", "Shoulder", "Elbow", "Wrist pitch", "Wrist roll", "Gripper"];

export const JOINT_LIMITS_LOW = [-Math.PI, -Math.PI / 2, -Math.PI, -Math.PI / 2, -Math.PI, 0.0];
export const JOINT_LIMITS_HIGH = [Math.PI, Math.PI / 2, Math.PI, Math.PI / 2, Math.PI, 1.0];

/** Rest pose - arm hanging naturally at side. */
export const REST_POSE = [0.0, -0.3, 0.5, -0.2, 0.0, 0.0];

export type GestureName = "greet" | "nod" | "point" | "idle" | "listen" | "farewell";

export const GESTURES: GestureName[] = ["greet", "nod", "point", "listen", "farewell", "idle"];

export const GESTURE_META: Record<
  GestureName,
  { label: string; icon: string; blurb: string }
> = {
  greet: { label: "Greet", icon: "👋", blurb: "Raise and wave - opens a session" },
  nod: { label: "Nod", icon: "🙂", blurb: "Acknowledge / affirm while listening" },
  point: { label: "Point", icon: "👉", blurb: "Direct attention to a pathway" },
  listen: { label: "Listen", icon: "👂", blurb: "Open, attentive posture" },
  farewell: { label: "Farewell", icon: "🫡", blurb: "Wave goodbye - closes a session" },
  idle: { label: "Idle", icon: "⏸️", blurb: "Neutral rest pose" },
};

type Keyframe = [number[], number]; // [jointAngles(6), holdSeconds]

/** Pre-programmed gesture keyframes - identical to GESTURE_KEYFRAMES in Python. */
export const GESTURE_KEYFRAMES: Record<GestureName, Keyframe[]> = {
  greet: [
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.3],
    [[0.3, 0.2, 0.2, 0.0, 0.0, 0.0], 0.4],
    [[0.3, 0.2, 0.2, 0.3, 0.4, 0.0], 0.25],
    [[0.3, 0.2, 0.2, 0.3, -0.4, 0.0], 0.25],
    [[0.3, 0.2, 0.2, 0.3, 0.4, 0.0], 0.25],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.5],
  ],
  nod: [
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.2],
    [[0.0, -0.2, 0.4, -0.3, 0.0, 0.0], 0.3],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.3],
    [[0.0, -0.2, 0.4, -0.3, 0.0, 0.0], 0.3],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.3],
  ],
  point: [
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.2],
    [[0.0, 0.1, 0.0, -0.1, 0.0, 0.0], 0.5],
    [[0.0, 0.1, 0.0, -0.1, 0.0, 0.0], 0.8],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.4],
  ],
  idle: [[[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 1.0]],
  listen: [
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.3],
    [[0.0, -0.1, 0.3, -0.1, 0.0, 0.0], 0.5],
    [[0.0, -0.1, 0.3, -0.1, 0.0, 0.0], 1.0],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.4],
  ],
  farewell: [
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.2],
    [[0.4, 0.2, 0.2, 0.0, 0.0, 0.0], 0.4],
    [[0.4, 0.2, 0.2, 0.2, 0.5, 0.0], 0.3],
    [[0.4, 0.2, 0.2, 0.2, -0.5, 0.0], 0.3],
    [[0.4, 0.2, 0.2, 0.2, 0.5, 0.0], 0.3],
    [[0.0, -0.3, 0.5, -0.2, 0.0, 0.0], 0.5],
  ],
};

export function clampJoints(q: number[]): number[] {
  return q.map((v, i) => Math.min(Math.max(v, JOINT_LIMITS_LOW[i]), JOINT_LIMITS_HIGH[i]));
}

export interface TrajFrame {
  q: number[];
  t: number;
}

/** Linear interpolation between keyframes - mirrors interpolate_keyframes(). */
export function interpolateKeyframes(keyframes: Keyframe[], dt = 0.05): TrajFrame[] {
  if (keyframes.length === 0) return [];
  const frames: TrajFrame[] = [];
  let t = 0;
  let prev = keyframes[0][0];
  for (const [target, hold] of keyframes) {
    const nSteps = Math.max(1, Math.round(hold / dt));
    for (let step = 0; step < nSteps; step++) {
      const alpha = step / nSteps;
      const q = prev.map((p, i) => p + alpha * (target[i] - p));
      frames.push({ q: clampJoints(q), t });
      t += dt;
    }
    prev = target;
  }
  // Append the terminal keyframe exactly.
  frames.push({ q: clampJoints(keyframes[keyframes.length - 1][0]), t });
  return frames;
}

export function gestureTrajectory(name: GestureName, dt = 0.05): TrajFrame[] {
  return interpolateKeyframes(GESTURE_KEYFRAMES[name], dt);
}

export function gestureDurationSeconds(name: GestureName): number {
  return GESTURE_KEYFRAMES[name].reduce((acc, [, hold]) => acc + hold, 0);
}

// ── Forward kinematics for the 2D side-view render ────────────────────────────
//
// A stylised planar arm whose segment angles are driven directly by the real
// joint vector, so every distinct gesture produces a visibly distinct motion
// (greet/farewell wave via j4, nod dips via j1/j3, point extends via j1/j2).

export interface ArmPose {
  /** Points from shoulder → elbow → wrist → hand tip, in a y-up local frame. */
  points: { x: number; y: number }[];
  /** Hand/palm orientation (radians, y-up) for drawing fingers. */
  handAngle: number;
  /** Gripper openness 0..1 (1 = fully open). */
  openness: number;
  /** Base yaw, used to skew the torso slightly. */
  yaw: number;
}

const L_UPPER = 64;
const L_FORE = 56;
const L_HAND = 22;

export function forwardKinematics(joints: number[]): ArmPose {
  const [j0, j1, j2, j3, j4, j5] = clampJoints(joints);

  // Shoulder: -π/2 = straight down. Raising j1 lifts the arm forward/up.
  const upperAngle = -Math.PI / 2 + (j1 + 0.3) * 1.7;
  // Forearm bends forward from the upper arm; elbow angle modulates it.
  const foreAngle = upperAngle + 0.5 + (j2 - 0.5) * 1.3;
  // Wrist pitch + a touch of roll so the wave reads in 2D.
  const handAngle = foreAngle + j3 * 1.2 + j4 * 0.6;

  const shoulder = { x: 0, y: 0 };
  const elbow = {
    x: shoulder.x + L_UPPER * Math.cos(upperAngle),
    y: shoulder.y + L_UPPER * Math.sin(upperAngle),
  };
  const wrist = {
    x: elbow.x + L_FORE * Math.cos(foreAngle),
    y: elbow.y + L_FORE * Math.sin(foreAngle),
  };
  const tip = {
    x: wrist.x + L_HAND * Math.cos(handAngle),
    y: wrist.y + L_HAND * Math.sin(handAngle),
  };

  return {
    points: [shoulder, elbow, wrist, tip],
    handAngle,
    openness: 1 - j5,
    yaw: j0,
  };
}

/** Mean absolute jerk of a trajectory (rad/s³) - the C3 smoothness proxy. */
export function meanAbsJerk(traj: TrajFrame[], dt = 0.05): number {
  if (traj.length < 4) return 0;
  let total = 0;
  let count = 0;
  for (let d = 0; d < DOF; d++) {
    for (let i = 3; i < traj.length; i++) {
      const a = traj[i].q[d];
      const b = traj[i - 1].q[d];
      const c = traj[i - 2].q[d];
      const e = traj[i - 3].q[d];
      const jerk = (a - 3 * b + 3 * c - e) / (dt * dt * dt);
      total += Math.abs(jerk);
      count += 1;
    }
  }
  return count ? total / count : 0;
}
