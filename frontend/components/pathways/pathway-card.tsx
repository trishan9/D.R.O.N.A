"use client";

import * as React from "react";
import { GraduationCap, MapPin, Globe2, ListChecks, GitCompare, Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { CitationDrilldown } from "@/components/pathways/citation-drilldown";
import { ReversibilityViz } from "@/components/pathways/reversibility-viz";
import type { Confidence, PathwayRecommendation } from "@/lib/types";
import { GOAL_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIDENCE_META: Record<Confidence, { label: string; dot: string; className: string }> = {
  high: { label: "High confidence", dot: "bg-success", className: "border-success/30 bg-success/10 text-success" },
  medium: { label: "Medium confidence", dot: "bg-warning", className: "border-warning/30 bg-warning/10 text-warning" },
  low: { label: "Low confidence", dot: "bg-destructive", className: "border-destructive/30 bg-destructive/10 text-destructive" },
};

interface PathwayCardProps {
  pathway: PathwayRecommendation;
  index: number;
  selected?: boolean;
  onToggleCompare?: () => void;
  onCitationsOpen?: () => void;
  highlightCounter?: boolean;
}

export function PathwayCard({
  pathway,
  index,
  selected,
  onToggleCompare,
  onCitationsOpen,
  highlightCounter,
}: PathwayCardProps) {
  const conf = CONFIDENCE_META[pathway.confidence];

  return (
    <Card
      className={cn(
        "flex flex-col overflow-hidden shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-card",
        selected && "ring-2 ring-brand ring-offset-2 ring-offset-background",
        highlightCounter && "border-tier-synthetic/50",
      )}
    >
      <CardHeader className="space-y-2.5 border-b bg-muted/20 pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-tier-international text-xs font-bold text-brand-foreground shadow-soft">
              {index + 1}
            </span>
            <h3 className="font-semibold leading-tight">{pathway.pathway_title}</h3>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold", conf.className)}>
            <span className={cn("h-1.5 w-1.5 rounded-full", conf.dot)} />
            {conf.label}
          </span>
          {pathway.goal_type && GOAL_LABELS[pathway.goal_type] && (
            <Badge variant="outline" className="text-[11px] font-medium">
              {GOAL_LABELS[pathway.goal_type]}
            </Badge>
          )}
        </div>
        <p className="text-sm leading-relaxed text-muted-foreground">{pathway.rationale}</p>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3.5 pt-4 text-sm">
        {pathway.matched_softwarica_modules.length > 0 && (
          <div className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <GraduationCap className="h-3.5 w-3.5" /> Builds on your modules
            </p>
            <div className="flex flex-wrap gap-1.5">
              {pathway.matched_softwarica_modules.map((m) => (
                <Badge key={m} variant="secondary" className="font-normal">
                  {m}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {pathway.local_market_evidence && (
          <div className="flex items-start gap-2 rounded-lg border border-tier-nepal/20 bg-tier-nepal/5 p-2.5 text-xs">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tier-nepal" />
            <span>
              <span className="font-semibold text-tier-nepal">Nepal market - </span>
              <span className="text-foreground/80">{pathway.local_market_evidence}</span>
            </span>
          </div>
        )}

        {pathway.international_context && (
          <div className="flex items-start gap-2 rounded-lg border border-tier-international/20 bg-tier-international/5 p-2.5 text-xs">
            <Globe2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tier-international" />
            <span>
              <span className="font-semibold text-tier-international">Global context - </span>
              <span className="text-foreground/80">{pathway.international_context}</span>
            </span>
          </div>
        )}

        {pathway.next_concrete_steps.length > 0 && (
          <div className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <ListChecks className="h-3.5 w-3.5" /> Next steps - by commitment
            </p>
            <ReversibilityViz steps={pathway.next_concrete_steps} />
          </div>
        )}

        <div className="mt-auto space-y-3 pt-1">
          <CitationDrilldown citations={pathway.citations} onOpen={onCitationsOpen} />
          {onToggleCompare && (
            <>
              <Separator />
              <Button
                variant={selected ? "default" : "outline"}
                size="sm"
                className="w-full"
                onClick={onToggleCompare}
              >
                {selected ? <Check className="h-3.5 w-3.5" /> : <GitCompare className="h-3.5 w-3.5" />}
                {selected ? "Selected to compare" : "Add to comparison"}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
