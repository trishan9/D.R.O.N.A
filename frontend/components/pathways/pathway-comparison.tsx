"use client";

import { GitCompare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ReversibilityViz } from "@/components/pathways/reversibility-viz";
import type { Confidence, PathwayRecommendation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface PathwayComparisonProps {
  pathways: PathwayRecommendation[];
}

const ROWS: { key: string; label: string }[] = [
  { key: "confidence", label: "Confidence" },
  { key: "modules", label: "Builds on modules" },
  { key: "local", label: "Nepal evidence" },
  { key: "intl", label: "Global context" },
  { key: "steps", label: "Next steps" },
  { key: "citations", label: "Citations" },
];

const CONF: Record<Confidence, string> = {
  high: "border-success/30 bg-success/10 text-success",
  medium: "border-warning/30 bg-warning/10 text-warning",
  low: "border-destructive/30 bg-destructive/10 text-destructive",
};

export function PathwayComparison({ pathways }: PathwayComparisonProps) {
  if (pathways.length < 2) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          <GitCompare className="mx-auto mb-2 h-6 w-6 opacity-50" />
          Select at least two pathways (from the All pathways tab) to compare them
          side-by-side. Comparing options head-to-head counters anchoring on the first
          idea you hear.
        </CardContent>
      </Card>
    );
  }

  const gridCols = { gridTemplateColumns: `minmax(8rem,9rem) repeat(${pathways.length}, minmax(0,1fr))` };

  return (
    <Card className="overflow-hidden shadow-soft">
      <CardHeader className="border-b bg-muted/20">
        <CardTitle className="flex items-center gap-2 text-base">
          <GitCompare className="h-4 w-4 text-brand" /> Side-by-side comparison
        </CardTitle>
        <CardDescription>
          The same dimensions for every option, so no single pathway gets undue weight.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <div className="min-w-[640px]">
          {/* Header row */}
          <div className="grid border-b bg-muted/30" style={gridCols}>
            <div className="p-3" />
            {pathways.map((p, i) => (
              <div key={i} className="border-l p-3">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-brand to-tier-international text-[11px] font-bold text-brand-foreground">
                    {i + 1}
                  </span>
                  <span className="text-sm font-semibold leading-tight">{p.pathway_title}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Rows */}
          {ROWS.map((row, ri) => (
            <div
              key={row.key}
              className={cn("grid border-b last:border-b-0", ri % 2 === 1 && "bg-muted/15")}
              style={gridCols}
            >
              <div className="p-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {row.label}
              </div>
              {pathways.map((p, i) => (
                <div key={i} className="border-l p-3 align-top">
                  <ComparisonCell row={row.key} pathway={p} />
                </div>
              ))}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ComparisonCell({ row, pathway }: { row: string; pathway: PathwayRecommendation }) {
  switch (row) {
    case "confidence":
      return (
        <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold capitalize", CONF[pathway.confidence])}>
          {pathway.confidence}
        </span>
      );
    case "modules":
      return pathway.matched_softwarica_modules.length ? (
        <div className="flex flex-wrap gap-1">
          {pathway.matched_softwarica_modules.map((m) => (
            <Badge key={m} variant="secondary" className="font-normal">
              {m}
            </Badge>
          ))}
        </div>
      ) : (
        <Dash />
      );
    case "local":
      return pathway.local_market_evidence ? (
        <span className="text-xs leading-relaxed">{pathway.local_market_evidence}</span>
      ) : (
        <Dash />
      );
    case "intl":
      return pathway.international_context ? (
        <span className="text-xs leading-relaxed">{pathway.international_context}</span>
      ) : (
        <Dash />
      );
    case "steps":
      return pathway.next_concrete_steps.length ? (
        <ReversibilityViz steps={pathway.next_concrete_steps} />
      ) : (
        <Dash />
      );
    case "citations":
      return (
        <span className="text-xs text-muted-foreground">
          {pathway.citations.length} source{pathway.citations.length === 1 ? "" : "s"}
        </span>
      );
    default:
      return <Dash />;
  }
}

function Dash() {
  return <span className="text-xs text-muted-foreground/40">-</span>;
}
