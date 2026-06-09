"use client";

import * as React from "react";
import { ShieldCheck, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { TokenInput } from "@/components/token-input";
import type { AspirationGeography, ProfileDraft } from "@/lib/types";

interface ProfileBuilderProps {
  profile: ProfileDraft;
  onChange: (next: ProfileDraft) => void;
  onReset: () => void;
}

const GEOGRAPHIES: { value: AspirationGeography; label: string }[] = [
  { value: "any", label: "Anywhere" },
  { value: "nepal", label: "Nepal" },
  { value: "regional", label: "Region" },
  { value: "international", label: "Global" },
];

export function ProfileBuilder({ profile, onChange, onReset }: ProfileBuilderProps) {
  const patch = (p: Partial<ProfileDraft>) => onChange({ ...profile, ...p });

  const setSkillLevel = (skill: string, level: number) => {
    patch({
      self_assessed_skill_levels: { ...profile.self_assessed_skill_levels, [skill]: level },
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Your profile</span>
          <Button variant="ghost" size="sm" onClick={onReset} className="text-muted-foreground">
            <Trash2 className="mr-1 h-3.5 w-3.5" /> Clear
          </Button>
        </CardTitle>
        <CardDescription className="flex items-center gap-1.5">
          <ShieldCheck className="h-3.5 w-3.5 text-tier-nepal" />
          Session-only. No name, no login, nothing saved or sent for tracking.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label>Year of study</Label>
          <div className="flex gap-2">
            {[1, 2, 3, 4].map((y) => (
              <Button
                key={y}
                type="button"
                variant={profile.year_of_study === y ? "default" : "outline"}
                size="sm"
                className="flex-1"
                onClick={() => patch({ year_of_study: profile.year_of_study === y ? null : y })}
              >
                Year {y}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label>Interests</Label>
          <TokenInput
            values={profile.declared_interests}
            onChange={(v) => patch({ declared_interests: v })}
            placeholder="e.g. machine learning, web, security…"
          />
        </div>

        <div className="space-y-2">
          <Label>Skills you have</Label>
          <TokenInput
            values={profile.declared_skills}
            onChange={(v) => {
              const levels = { ...profile.self_assessed_skill_levels };
              for (const k of Object.keys(levels)) if (!v.includes(k)) delete levels[k];
              patch({ declared_skills: v, self_assessed_skill_levels: levels });
            }}
            placeholder="e.g. Python, SQL, React…"
          />
          {profile.declared_skills.length > 0 && (
            <div className="space-y-3 rounded-md border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">
                Rate yourself honestly (1 = beginner, 5 = strong). This helps counter
                over- and under-confidence.
              </p>
              {profile.declared_skills.map((skill) => {
                const level = profile.self_assessed_skill_levels[skill] ?? 3;
                return (
                  <div key={skill} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>{skill}</span>
                      <span className="tabular-nums text-muted-foreground">{level}/5</span>
                    </div>
                    <Slider
                      min={1}
                      max={5}
                      step={1}
                      value={[level]}
                      onValueChange={([v]) => setSkillLevel(skill, v)}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-2">
          <Label>Completed modules</Label>
          <TokenInput
            values={profile.completed_modules}
            onChange={(v) => patch({ completed_modules: v })}
            placeholder="e.g. 4001COMP, 5002COMP…"
          />
        </div>

        <div className="space-y-2">
          <Label>Aspirations</Label>
          <TokenInput
            values={profile.aspirations}
            onChange={(v) => patch({ aspirations: v })}
            placeholder="e.g. become a data scientist…"
          />
        </div>

        <div className="space-y-2">
          <Label>Where do you want to work?</Label>
          <div className="flex gap-2">
            {GEOGRAPHIES.map((g) => (
              <Button
                key={g.value}
                type="button"
                variant={profile.aspiration_geography === g.value ? "default" : "outline"}
                size="sm"
                className="flex-1"
                onClick={() => patch({ aspiration_geography: g.value })}
              >
                {g.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <Label>How many pathways to surface? ({profile.max_pathways})</Label>
          <Slider
            min={1}
            max={6}
            step={1}
            value={[profile.max_pathways]}
            onValueChange={([v]) => patch({ max_pathways: v })}
          />
          <p className="text-xs text-muted-foreground">
            Seeing several options at once is a deliberate anti-anchoring choice.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
