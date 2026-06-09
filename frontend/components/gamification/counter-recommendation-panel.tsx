"use client";

import * as React from "react";
import { Shuffle, Eye } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CitationDrilldown } from "@/components/pathways/citation-drilldown";
import { selectCounterRecommendation } from "@/lib/gamification";
import type { AdvisingResponse } from "@/lib/types";

interface CounterRecommendationPanelProps {
  response: AdvisingResponse | null;
  declaredInterests: string[];
  onReveal?: () => void;
}

/**
 * Surfaces the ONE pathway the student is least likely to pick given their
 * stated interests — the antidote to confirmation bias. It's hidden behind a
 * deliberate "show me what I might be ignoring" action so revealing it is an
 * active, rewarded choice (ties into the "Open Mind" badge).
 */
export function CounterRecommendationPanel({
  response,
  declaredInterests,
  onReveal,
}: CounterRecommendationPanelProps) {
  const [revealed, setRevealed] = React.useState(false);
  const pick = selectCounterRecommendation(response, declaredInterests);

  React.useEffect(() => setRevealed(false), [response?.query_id]);

  if (!pick) return null;

  return (
    <Card className="border-tier-synthetic/40 bg-tier-synthetic/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Shuffle className="h-4 w-4 text-tier-synthetic" /> The option you might overlook
        </CardTitle>
        <CardDescription>
          A pathway that doesn&apos;t match what you said you wanted — worth a look precisely
          for that reason.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!revealed ? (
          <Button
            variant="outline"
            className="w-full border-tier-synthetic/40"
            onClick={() => {
              setRevealed(true);
              onReveal?.();
            }}
          >
            <Eye className="h-4 w-4" /> Show me what I might be ignoring
          </Button>
        ) : (
          <div className="space-y-2.5">
            <h4 className="font-semibold">{pick.pathway_title}</h4>
            <p className="text-sm text-muted-foreground">{pick.rationale}</p>
            {pick.local_market_evidence && (
              <p className="text-xs">
                <span className="font-medium text-tier-nepal">Nepal: </span>
                {pick.local_market_evidence}
              </p>
            )}
            <CitationDrilldown citations={pick.citations} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
