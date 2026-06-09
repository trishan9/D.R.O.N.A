"use client";

import { GitCompare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ReversibilityViz } from "@/components/pathways/reversibility-viz";
import type { PathwayRecommendation } from "@/lib/types";

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

export function PathwayComparison({ pathways }: PathwayComparisonProps) {
  if (pathways.length < 2) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          <GitCompare className="mx-auto mb-2 h-6 w-6 opacity-50" />
          Select at least two pathways (from the Pathways tab) to compare them
          side-by-side. Comparing options head-to-head counters anchoring on the first
          idea you hear.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Side-by-side comparison</CardTitle>
        <CardDescription>
          The same dimensions for every option, so no single pathway gets undue weight.
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-32 border-b p-2 text-left text-xs font-medium text-muted-foreground" />
              {pathways.map((p, i) => (
                <th key={i} className="border-b p-2 text-left align-bottom">
                  <span className="text-sm font-semibold">{p.pathway_title}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.key} className="align-top">
                <td className="border-b p-2 text-xs font-medium text-muted-foreground">
                  {row.label}
                </td>
                {pathways.map((p, i) => (
                  <td key={i} className="border-b p-2">
                    <ComparisonCell row={row.key} pathway={p} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function ComparisonCell({ row, pathway }: { row: string; pathway: PathwayRecommendation }) {
  switch (row) {
    case "confidence":
      return <Badge variant="secondary">{pathway.confidence}</Badge>;
    case "modules":
      return pathway.matched_softwarica_modules.length ? (
        <div className="flex flex-wrap gap-1">
          {pathway.matched_softwarica_modules.map((m) => (
            <Badge key={m} variant="outline" className="text-xs">
              {m}
            </Badge>
          ))}
        </div>
      ) : (
        <Dash />
      );
    case "local":
      return pathway.local_market_evidence ? (
        <span className="text-xs">{pathway.local_market_evidence}</span>
      ) : (
        <Dash />
      );
    case "intl":
      return pathway.international_context ? (
        <span className="text-xs">{pathway.international_context}</span>
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
  return <span className="text-xs text-muted-foreground/50">—</span>;
}
