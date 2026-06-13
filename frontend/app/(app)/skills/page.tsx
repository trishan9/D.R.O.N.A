"use client";

import * as React from "react";
import { Sparkles, Target, Heart, ShieldQuestion } from "lucide-react";

import { useStore } from "@/lib/store";
import { SkillTree } from "@/components/gamification/skill-tree";
import { ReversibilityViz } from "@/components/pathways/reversibility-viz";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SkillsPage() {
  const { response, profile } = useStore();

  const interests = profile.declared_interests;
  const skillLevels = Object.entries(profile.self_assessed_skill_levels);
  const nextSteps = (response?.pathways ?? []).flatMap((p) => p.next_concrete_steps);

  return (
    <div className="grid gap-4 animate-fade-in lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-brand" /> Curriculum skill map
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              A graph of skills you have versus those the recommended pathways draw on — shown as a web,
              not a ladder, so no single track looks like the &ldquo;top&rdquo;.
            </p>
          </CardHeader>
          <CardContent className="pt-5">
            <SkillTree
              response={response}
              haveSkills={profile.declared_skills}
              completedModules={profile.completed_modules}
            />
          </CardContent>
        </Card>

        {nextSteps.length > 0 && (
          <Card>
            <CardHeader className="border-b">
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldQuestion className="h-4 w-4 text-brand" /> Next steps by reversibility
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                Low-stakes, reversible steps are inviting; the few high-commitment ones are flagged — a
                counter to loss aversion.
              </p>
            </CardHeader>
            <CardContent className="pt-5">
              <ReversibilityViz steps={nextSteps} />
            </CardContent>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <Heart className="h-4 w-4" /> Declared interests
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {interests.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                None yet — add interests on your <strong>Profile</strong> so advising can weigh them
                (and deliberately challenge them).
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {interests.map((i) => (
                  <Badge key={i} variant="secondary" className="capitalize">{i}</Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <Target className="h-4 w-4" /> Self-assessed skills
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-4">
            {skillLevels.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Rate a few skills on your Profile to see them here. Self-ratings are a known
                Dunning–Kruger trap — advising treats them as hints, not facts.
              </p>
            ) : (
              skillLevels.map(([skill, level]) => (
                <div key={skill}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="capitalize">{skill}</span>
                    <span className="text-muted-foreground">{level}/5</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-brand" style={{ width: `${(level / 5) * 100}%` }} />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
