"use client";

import * as React from "react";
import { GraduationCap, MapPin, Globe2, ListChecks, GitCompare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { CitationDrilldown } from "@/components/pathways/citation-drilldown";
import { ReversibilityViz } from "@/components/pathways/reversibility-viz";
import type { Confidence, PathwayRecommendation } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIDENCE_META: Record<Confidence, { label: string; className: string }> = {
  high: { label: "High confidence", className: "bg-emerald-500/15 text-emerald-600" },
  medium: { label: "Medium confidence", className: "bg-amber-500/15 text-amber-600" },
  low: { label: "Low confidence", className: "bg-rose-500/15 text-rose-600" },
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
        "flex flex-col transition-shadow hover:shadow-md",
        selected && "ring-2 ring-primary",
        highlightCounter && "border-tier-synthetic/50",
      )}
    >
      <CardHeader className="space-y-2 pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-secondary text-xs font-bold">
              {index + 1}
            </span>
            <h3 className="font-semibold leading-tight">{pathway.pathway_title}</h3>
          </div>
          <Badge className={cn("shrink-0", conf.className)} variant="secondary">
            {conf.label}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{pathway.rationale}</p>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 text-sm">
        {pathway.matched_softwarica_modules.length > 0 && (
          <div className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <GraduationCap className="h-3.5 w-3.5" /> Builds on your modules
            </p>
            <div className="flex flex-wrap gap-1">
              {pathway.matched_softwarica_modules.map((m) => (
                <Badge key={m} variant="outline" className="text-xs">
                  {m}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {pathway.local_market_evidence && (
          <p className="flex items-start gap-1.5 text-xs">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tier-nepal" />
            <span>
              <span className="font-medium text-tier-nepal">Nepal market: </span>
              {pathway.local_market_evidence}
            </span>
          </p>
        )}

        {pathway.international_context && (
          <p className="flex items-start gap-1.5 text-xs">
            <Globe2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-tier-international" />
            <span>
              <span className="font-medium text-tier-international">Global context: </span>
              {pathway.international_context}
            </span>
          </p>
        )}

        {pathway.next_concrete_steps.length > 0 && (
          <div className="space-y-1.5">
            <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <ListChecks className="h-3.5 w-3.5" /> Next steps — colour-coded by commitment
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
                <GitCompare className="h-3.5 w-3.5" />
                {selected ? "Selected to compare" : "Add to comparison"}
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
