"use client";

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Compass } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { computeDiversity, TIER_META } from "@/lib/gamification";
import type { AdvisingResponse, DataTier } from "@/lib/types";

const TIER_COLORS: Record<DataTier, string> = {
  nepal: "hsl(351 70% 47%)",
  regional: "hsl(32 95% 50%)",
  international: "hsl(217 91% 60%)",
  synthetic: "hsl(262 52% 58%)",
};

interface DiversityMeterProps {
  response: AdvisingResponse | null;
}

export function DiversityMeter({ response }: DiversityMeterProps) {
  if (!response) return null;
  const d = computeDiversity(response);

  const data = (Object.keys(d.tierBreakdown) as DataTier[])
    .map((t) => ({ name: TIER_META[t].label, tier: t, value: d.tierBreakdown[t] }))
    .filter((x) => x.value > 0);

  const labelColor =
    d.label === "broad" ? "text-emerald-600" : d.label === "moderate" ? "text-amber-600" : "text-rose-600";

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Compass className="h-4 w-4 text-brand" /> Evidence diversity
        </CardTitle>
        <CardDescription>
          How wide a net this answer casts across sources. Broader = less anchored on one
          narrative.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4">
          <div className="relative h-28 w-28 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.length ? data : [{ name: "none", tier: "synthetic", value: 1 }]}
                  dataKey="value"
                  innerRadius={34}
                  outerRadius={52}
                  paddingAngle={2}
                  stroke="none"
                >
                  {(data.length ? data : [{ tier: "synthetic" as DataTier }]).map((entry, i) => (
                    <Cell key={i} fill={TIER_COLORS[(entry as { tier: DataTier }).tier]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold tabular-nums">{d.score}</span>
              <span className="text-[10px] uppercase text-muted-foreground">score</span>
            </div>
          </div>

          <div className="flex-1 space-y-2">
            <p className={`text-sm font-semibold capitalize ${labelColor}`}>{d.label} view</p>
            <p className="text-xs text-muted-foreground">
              {d.pathwayCount} pathway{d.pathwayCount === 1 ? "" : "s"} · {d.distinctTiers}{" "}
              evidence tier{d.distinctTiers === 1 ? "" : "s"}
            </p>
            <ul className="space-y-1">
              {data.map((x) => (
                <li key={x.tier} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: TIER_COLORS[x.tier] }}
                  />
                  {x.name}
                  <span className="ml-auto tabular-nums text-muted-foreground">{x.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
