import * as React from "react";

import { forwardKinematics } from "@/lib/robot";
import { cn } from "@/lib/utils";

interface RobotArmProps {
  joints: number[];
  /** 0..1 engagement - widens the eyes / brightens the halo. */
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

  const eyeOpen = 2.2 + engagement * 2.6;
  const haloOpacity = 0.14 + engagement * 0.26;
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
        {/* Metallic vertical body sheen. */}
        <linearGradient id="body-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(var(--card))" />
          <stop offset="50%" stopColor="hsl(var(--muted))" />
          <stop offset="100%" stopColor="hsl(var(--card))" />
        </linearGradient>
        <linearGradient id="edge-light" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="hsl(var(--brand))" stopOpacity="0.5" />
          <stop offset="100%" stopColor="hsl(var(--brand))" stopOpacity="0" />
        </linearGradient>
        <radialGradient id="halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="hsl(var(--brand))" stopOpacity={haloOpacity} />
          <stop offset="100%" stopColor="hsl(var(--brand))" stopOpacity="0" />
        </radialGradient>
        {/* Soft neon glow for the arm + eyes. */}
        <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="3.2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* engagement halo */}
      <circle cx="150" cy="118" r="124" fill="url(#halo)" />

      {/* ground shadow + reflective pedestal */}
      <ellipse cx="150" cy="320" rx="96" ry="15" fill="hsl(var(--brand))" opacity={0.06 + engagement * 0.06} />
      <ellipse cx="150" cy="318" rx="78" ry="11" fill="hsl(var(--muted-foreground))" opacity="0.18" />
      <rect x="118" y="248" width="64" height="62" rx="12" fill="url(#body-grad)" stroke="hsl(var(--border))" strokeWidth="1.5" />
      <rect x="104" y="300" width="92" height="15" rx="7" fill="hsl(var(--border))" />
      <rect x="104" y="300" width="92" height="4" rx="2" fill="hsl(var(--muted-foreground))" opacity="0.25" />

      <g transform={`rotate(${skew} 150 180)`}>
        {/* torso */}
        <rect x="115" y="150" width="70" height="110" rx="24" fill="url(#body-grad)" stroke="hsl(var(--border))" strokeWidth="2" />
        <rect x="115" y="150" width="70" height="22" rx="22" fill="url(#edge-light)" opacity="0.35" />
        {/* chest status light */}
        <circle cx="150" cy="200" r="6" fill="hsl(var(--brand))" opacity="0.9" filter="url(#glow)" className={active ? "animate-pulse" : ""} />
        <circle cx="150" cy="200" r="2.4" fill="hsl(var(--brand-foreground))" />

        {/* neck + head */}
        <rect x="143" y="128" width="14" height="14" rx="4" fill="hsl(var(--muted))" />
        <rect x="118" y="76" width="64" height="56" rx="20" fill="url(#body-grad)" stroke="hsl(var(--border))" strokeWidth="2" />
        <rect x="118" y="76" width="64" height="18" rx="18" fill="url(#edge-light)" opacity="0.4" />
        {/* antenna */}
        <line x1="150" y1="76" x2="150" y2="62" stroke="hsl(var(--border))" strokeWidth="3" strokeLinecap="round" />
        <circle cx="150" cy="60" r="4" fill="hsl(var(--brand))" filter="url(#glow)" className={active ? "animate-pulse" : ""} />
        {/* visor */}
        <rect x="128" y="92" width="44" height="26" rx="13" fill="hsl(222 47% 11%)" opacity="0.85" />
        {/* eyes */}
        <circle cx="139" cy="105" r={eyeOpen} fill="hsl(var(--brand))" filter="url(#glow)" />
        <circle cx="161" cy="105" r={eyeOpen} fill="hsl(var(--brand))" filter="url(#glow)" />
        <circle cx="139" cy="105" r={eyeOpen * 0.45} fill="#fff" opacity="0.85" />
        <circle cx="161" cy="105" r={eyeOpen * 0.45} fill="#fff" opacity="0.85" />
      </g>

      {/* arm: shoulder → elbow → wrist → tip (with neon glow) */}
      <g strokeLinecap="round" strokeLinejoin="round" filter="url(#glow)">
        <polyline
          points={`${shoulder.x},${shoulder.y} ${elbow.x},${elbow.y} ${wrist.x},${wrist.y}`}
          fill="none"
          stroke="url(#arm-grad)"
          strokeWidth="14"
        />
        <polyline
          points={`${wrist.x},${wrist.y} ${tip.x},${tip.y}`}
          fill="none"
          stroke="url(#arm-grad)"
          strokeWidth="10"
        />
        {/* hand fingers */}
        {[-0.5, 0, 0.5].map((spread, i) => {
          const a = pose.handAngle + spread * (0.35 + pose.openness * 0.5);
          const len = 13;
          const fx = tip.x + len * Math.cos(a);
          const fy = tip.y - len * Math.sin(a);
          return (
            <line key={i} x1={tip.x} y1={tip.y} x2={fx} y2={fy} stroke="url(#arm-grad)" strokeWidth="5.5" />
          );
        })}
      </g>

      {/* joints (crisp, on top of the glow) */}
      <g strokeLinecap="round">
        <circle cx={shoulder.x} cy={shoulder.y} r="8.5" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="3.5" />
        <circle cx={elbow.x} cy={elbow.y} r="7" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="3" />
        <circle cx={wrist.x} cy={wrist.y} r="6" fill="hsl(var(--background))" stroke="hsl(var(--brand))" strokeWidth="2.5" />
        <circle cx={shoulder.x} cy={shoulder.y} r="2.5" fill="hsl(var(--brand))" />
        <circle cx={elbow.x} cy={elbow.y} r="2" fill="hsl(var(--brand))" />
      </g>
    </svg>
  );
}
