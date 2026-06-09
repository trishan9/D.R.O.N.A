"use client";

import * as React from "react";

import { getHealth } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export function HealthStatus() {
  const [health, setHealth] = React.useState<HealthResponse | null>(null);
  const [reachable, setReachable] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const h = await getHealth();
        if (active) {
          setHealth(h);
          setReachable(true);
        }
      } catch {
        if (active) setReachable(false);
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const ok = reachable && health?.status === "ok";
  const color =
    reachable === null
      ? "bg-muted-foreground"
      : !reachable
        ? "bg-rose-500"
        : ok
          ? "bg-emerald-500"
          : "bg-amber-500";

  const text =
    reachable === null
      ? "Connecting…"
      : !reachable
        ? "Backend offline"
        : ok
          ? "Local LLM ready"
          : "Degraded (LLM unavailable)";

  return (
    <div className="flex items-center gap-2 rounded-full border bg-background/70 px-3 py-1 text-xs">
      <span className={cn("h-2 w-2 rounded-full", color, ok && "animate-pulse")} />
      <span className="font-medium">{text}</span>
      {health && (
        <span className="text-muted-foreground">
          · {health.orchestrator} · {health.vector_backend}
        </span>
      )}
    </div>
  );
}
