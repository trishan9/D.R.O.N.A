"use client";

import { Brain, ShieldCheck } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BIAS_LABELS } from "@/lib/gamification";
import type { BiasFlag } from "@/lib/types";

interface BiasFlagsProps {
  flags: BiasFlag[];
}

/**
 * Transparent display of which cognitive biases the backend detected in the
 * student's question and how the answer was shaped to counter them. This makes
 * the bias-mitigation explicit rather than silent — a core proposal claim.
 */
export function BiasFlags({ flags }: BiasFlagsProps) {
  if (flags.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4 text-emerald-600" /> Bias check
          </CardTitle>
          <CardDescription>
            No strong cognitive-bias signals detected in your last question.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="border-amber-500/40 bg-amber-500/5">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Brain className="h-4 w-4 text-amber-600" /> Bias check
        </CardTitle>
        <CardDescription>
          Patterns in how the question was framed that can skew decisions. Naming them is
          the first step to seeing past them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {flags.map((f, i) => (
          <div key={i} className="space-y-1.5 rounded-md border bg-background/60 p-3">
            <Badge variant="secondary" className="bg-amber-500/15 text-amber-700">
              {BIAS_LABELS[f.bias_type] ?? f.bias_type}
            </Badge>
            <p className="text-xs">
              <span className="font-medium text-muted-foreground">Signal: </span>
              {f.detected_signal}
            </p>
            <p className="text-xs">
              <span className="font-medium text-muted-foreground">How we countered it: </span>
              {f.mitigation_applied}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
