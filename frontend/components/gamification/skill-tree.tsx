"use client";

import { CheckCircle2, Circle, Target } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buildSkillTree, type SkillNode } from "@/lib/gamification";
import type { AdvisingResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SkillTreeProps {
  response: AdvisingResponse | null;
  haveSkills: string[];
  completedModules: string[];
}

/**
 * Skill graph, deliberately NOT a ranked ladder. Shows what the student already
 * has vs. what surfaced pathways ask for - framed as a connected map so no
 * single "destination" anchors the student.
 */
export function SkillTree({ response, haveSkills, completedModules }: SkillTreeProps) {
  const nodes = buildSkillTree(response, [...haveSkills, ...completedModules]);

  if (nodes.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Skill map</CardTitle>
          <CardDescription>
            Add skills/modules to your profile, or ask a question, to grow your map.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const have = nodes.filter((n) => n.status === "have" || n.status === "both");
  const targets = nodes.filter((n) => n.status === "target");

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Skill map</CardTitle>
        <CardDescription>
          What you already bring, and what the pathways above would grow. A web of
          options - not a single ladder.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Section
          title="You already have"
          icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />}
          nodes={have}
          empty="Tell D.R.O.N.A. your skills to populate this."
        />
        <Section
          title="Pathways would grow"
          icon={<Target className="h-3.5 w-3.5 text-tier-international" />}
          nodes={targets}
          empty="Ask a question to see which skills your options develop."
        />
      </CardContent>
    </Card>
  );
}

function Section({
  title,
  icon,
  nodes,
  empty,
}: {
  title: string;
  icon: React.ReactNode;
  nodes: SkillNode[];
  empty: string;
}) {
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon} {title}
      </p>
      {nodes.length === 0 ? (
        <p className="text-xs text-muted-foreground/70">{empty}</p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {nodes.map((n) => (
            <Badge
              key={n.id}
              variant="outline"
              className={cn(
                "gap-1",
                n.status === "both"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
                  : n.status === "have"
                    ? "border-emerald-500/30 bg-emerald-500/5"
                    : "border-tier-international/30 bg-tier-international/5",
              )}
              title={n.pathways.length ? `Used by: ${n.pathways.join(", ")}` : undefined}
            >
              {n.status === "both" ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <Circle className="h-3 w-3" />
              )}
              {n.label}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
