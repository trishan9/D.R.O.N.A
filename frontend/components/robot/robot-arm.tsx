import * as React from "react";

import { forwardKinematics } from "@/lib/robot";
import { cn } from "@/lib/utils";

interface RobotArmProps {
  joints: number[];
  /** 0..1 engagement — widens the eyes / brightens the halo. */
  engagement?: number;
  active?: boolean;
  className?: string;
}

/**
 * Side-view render of the D.R.O.N.A. 6-DOF upper-body robot. The arm geometry
 * is computed by forwardKinematics() directly from the joint vector, so the
 * exact same poses that play on the ROS2 arm play here.
 */
export function RobotArm({ joints, engagement = 0.4, active = false, className }: RobotArmProps) {
  const pose = forwardKinematics(joints);

  // Shoulder origin in SVG space; FK is y-up so we negate y.
  const ox = 150;
  const oy = 158;
  const pts = pose.points.map((p) => ({ x: ox + p.x, y: oy - p.y }));
  const [shoulder, elbow, wrist, tip] = pts;

  // Fingers: short lines fanned around the hand axis, spread by openness.
  const eyeOpen = 2.2 + engagement * 2.6;
  const haloOpacity = 0.12 + engagement * 0.22;
  const skew = pose.yaw * 6; // subtle torso lean from base yaw

  return (
    <svg
      viewBox="0 0 300 340"
      className={cn("h-full w-full", className)}
      role="img"
      aria-label="D.R.O.N.A. robot"
    >
      <defs>
        <linearGradient id="arm-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="hsl(var(--brand))" />
          <stop offset="100%" stopColor="hsl(var(--tier-international))" />
        </linearGradient>
        <radialGradient id="halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="hsl(var(--brand))" stopOpacity={haloOpacity} />
          <stop offset="100%" stopColor="hsl(var(--brand))" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* engagement halo */}
      <circle cx="150" cy="120" r="120" fill="url(#halo)" />

      {/* ground + pedestal */}
      <ellipse cx="150" cy="318" rx="92" ry="14" fill="hsl(var(--muted-foreground))" opacity="0.16" />
      <rect x="120" y="250" width="60" height="60" rx="10" fill="hsl(var(--muted))" />
      <rect x="108" y="300" width="84" height="14" rx="7" fill="hsl(var(--border))" />

      <g transform={`rotate(${skew} 150 180)`}>
        {/* torso */}
        <rect x="116" y="150" width="68" height="108" rx="22" fill="hsl(var(--card))" stroke="hsl(var(--border))" strokeWidth="2" />
        <rect x="134" y="170" width="32" height="6" rx="3" fill="hsl(var(--border))" />

        {/* head */}
        <rect x="120" y="78" width="60" height="52" rx="18" fill="hsl(var(--card))" stroke="hsl(var(--border))" strokeWidth="2" />
        <rect x="146" y="68" width="8" height="14" rx="4" fill="hsl(var(--border))" />
        <circle cx="150" cy="64" r="4" fill="hsl(var(--brand))" className={active ? "animate-pulse" : ""} />
        {/* eyes */}
        <circle cx="138" cy="104" r={eyeOpen} fill="hsl(var(--brand))" />
        <circle cx="162" cy="104" r={eyeOpen} fill="hsl(var(--brand))" />
        <path d="M140 118 Q150 124 160 118" stroke="hsl(var(--muted-foreground))" strokeWidth="2" fill="none" strokeLinecap="round" />
      </g>

      {/* arm: shoulder → elbow → wrist → tip */}
      <g strokeLinecap="round" strokeLinejoin="round">
        <polyline
          points={`${shoulder.x},${shoulder.y} ${elbow.x},${elbow.y} ${wrist.x},${wrist.y}`}
          fill="none"
          stroke="url(#arm-grad)"
          strokeWidth="13"
        />
        <polyline
          points={`${wrist.x},${wrist.y} ${tip.x},${tip.y}`}
          fill="none"
          stroke="url(#arm-grad)"
          strokeWidth="9"
        />
        {/* hand fingers */}
        {[-0.5, 0, 0.5].map((spread, i) => {
          const a = pose.handAngle + spread * (0.35 + pose.openness * 0.5);
          const len = 12;
          const fx = tip.x + len * Math.cos(a);
          const fy = tip.y - len * Math.sin(a);
          return (
            <line key={i} x1={tip.x} y1={tip.y} x2={fx} y2={fy} stroke="url(#arm-grad)" strokeWidth="5" />
          );
        })}
        {/* joints */}
        <circle cx={shoulder.x} cy={shoulder.y} r="8" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="3" />
        <circle cx={elbow.x} cy={elbow.y} r="6.5" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="3" />
        <circle cx={wrist.x} cy={wrist.y} r="5.5" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="2.5" />
      </g>
    </svg>
  );
}
