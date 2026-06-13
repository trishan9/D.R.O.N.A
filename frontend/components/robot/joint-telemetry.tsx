import { JOINT_SHORT, JOINT_LIMITS_LOW, JOINT_LIMITS_HIGH, JOINT_NAMES } from "@/lib/robot";

export function JointTelemetry({ joints }: { joints: number[] }) {
  return (
    <div className="space-y-2.5 font-mono text-xs">
      {JOINT_SHORT.map((name, i) => {
        const low = JOINT_LIMITS_LOW[i];
        const high = JOINT_LIMITS_HIGH[i];
        const v = joints[i] ?? 0;
        const pct = ((v - low) / (high - low)) * 100;
        const zeroPct = ((0 - low) / (high - low)) * 100;
        return (
          <div key={JOINT_NAMES[i]}>
            <div className="mb-1 flex items-center justify-between">
              <span className="font-sans font-medium text-foreground">
                <span className="text-muted-foreground">j{i}</span> {name}
              </span>
              <span className="tabular-nums text-muted-foreground">{v.toFixed(2)}</span>
            </div>
            <div className="relative h-2 overflow-hidden rounded-full bg-muted">
              {/* zero marker */}
              <span
                className="absolute top-0 h-full w-px bg-muted-foreground/50"
                style={{ left: `${zeroPct}%` }}
              />
              <span
                className="absolute top-0 h-full rounded-full bg-brand transition-all duration-150"
                style={{
                  left: `${Math.min(pct, zeroPct)}%`,
                  width: `${Math.abs(pct - zeroPct)}%`,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
