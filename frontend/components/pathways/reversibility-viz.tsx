"use client";

import { Lock, Unlock } from "lucide-react";

import { classifySteps } from "@/lib/gamification";
import { cn } from "@/lib/utils";

interface ReversibilityVizProps {
  steps: string[];
}

/**
 * Visualises each next step as reversible (low-stakes, try-and-see) or
 * irreversible (high-commitment). Counters loss-aversion by making the cheap,
 * undoable options visually inviting and flagging the few that aren't.
 */
export function ReversibilityViz({ steps }: ReversibilityVizProps) {
  if (steps.length === 0) return null;
  const classified = classifySteps(steps);

  return (
    <ul className="space-y-1.5">
      {classified.map((s, i) => {
        const reversible = s.reversibility === "reversible";
        return (
          <li
            key={i}
            className={cn(
              "flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-xs",
              reversible
                ? "border-emerald-500/30 bg-emerald-500/5"
                : "border-amber-500/40 bg-amber-500/10",
            )}
          >
            {reversible ? (
              <Unlock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
            ) : (
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
            )}
            <span className="flex-1">{s.text}</span>
            <span
              className={cn(
                "shrink-0 text-[10px] font-medium uppercase tracking-wide",
                reversible ? "text-emerald-600" : "text-amber-600",
              )}
            >
              {reversible ? "easily undone" : "big commitment"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
