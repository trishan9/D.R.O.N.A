"use client";

import { Check, Target } from "lucide-react";

import type { Quest } from "@/lib/achievements";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function Quests({ quests }: { quests: Quest[] }) {
  const done = quests.filter((q) => q.done).length;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 border-b py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Target className="h-4 w-4 text-brand" /> Quests
        </CardTitle>
        <span className="text-xs tabular-nums text-muted-foreground">{done}/{quests.length}</span>
      </CardHeader>
      <CardContent className="space-y-2.5 pt-4">
        {quests.map((q) => {
          const pct = Math.round((q.current / q.target) * 100);
          return (
            <div key={q.id} className={cn("rounded-lg border p-3 transition-colors", q.done && "border-brand/40 bg-brand/5")}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                      q.done ? "bg-brand text-brand-foreground" : "border border-border",
                    )}
                  >
                    {q.done && <Check className="h-3 w-3" />}
                  </span>
                  <p className="text-sm font-medium">{q.label}</p>
                </div>
                <span className="chip shrink-0">+{q.xp} XP</span>
              </div>
              <p className="ml-7 mt-0.5 text-xs text-muted-foreground">{q.hint}</p>
              <div className="ml-7 mt-1.5 flex items-center gap-2">
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-[11px] tabular-nums text-muted-foreground">{q.current}/{q.target}</span>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
