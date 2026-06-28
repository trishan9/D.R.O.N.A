"use client";

import { Trophy, Zap } from "lucide-react";

import { RANKS, type Progress } from "@/lib/achievements";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function RankProgress({ progress }: { progress: Progress }) {
  const { xp, level, rank, next, pctToNext, xpIntoLevel, xpForLevel } = progress;

  return (
    <Card className="bg-aurora relative overflow-hidden border-brand/20">
      <div className="bg-grid pointer-events-none absolute inset-0 opacity-50" />
      <CardContent className="relative z-10 py-6">
        <div className="flex flex-wrap items-center gap-5">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-glow">
            <Trophy className="h-8 w-8" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Level {level} · Explorer rank
            </p>
            <h2 className="gradient-text text-2xl font-bold tracking-tight">{rank.name}</h2>
            <p className="text-sm text-muted-foreground">{rank.blurb}</p>
          </div>
          <div className="text-right">
            <p className="flex items-center justify-end gap-1.5 text-2xl font-bold tabular-nums">
              <Zap className="h-5 w-5 text-brand" /> {xp}
              <span className="text-sm font-medium text-muted-foreground">XP</span>
            </p>
            {next ? (
              <p className="text-xs text-muted-foreground">
                {xpForLevel - xpIntoLevel} XP to {next.name}
              </p>
            ) : (
              <p className="text-xs font-medium text-brand">Top rank reached</p>
            )}
          </div>
        </div>

        <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-gradient-to-r from-brand to-tier-international transition-all duration-500"
            style={{ width: `${pctToNext}%` }}
          />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {RANKS.map((r) => {
            const reached = xp >= r.minXp;
            const current = r.name === rank.name;
            return (
              <div
                key={r.name}
                className={cn(
                  "rounded-lg border p-2.5 text-center transition-colors",
                  current
                    ? "border-brand bg-brand/10 shadow-soft"
                    : reached
                      ? "border-brand/30 bg-brand/5"
                      : "border-border opacity-60",
                )}
              >
                <p
                  className={cn(
                    "text-[11px] font-semibold leading-tight",
                    current ? "text-brand" : reached ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {r.name}
                </p>
                <p className="mt-0.5 text-[10px] tabular-nums text-muted-foreground">{r.minXp} XP</p>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
