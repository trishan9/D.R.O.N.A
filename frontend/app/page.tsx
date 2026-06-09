"use client";

import * as React from "react";
import { Bot, LayoutGrid, GitCompare, Network } from "lucide-react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { HealthStatus } from "@/components/health-status";
import { ProfileBuilder } from "@/components/profile/profile-builder";
import { ChatPanel } from "@/components/chat/chat-panel";
import { PathwayCard } from "@/components/pathways/pathway-card";
import { PathwayComparison } from "@/components/pathways/pathway-comparison";
import { DiversityMeter } from "@/components/gamification/diversity-meter";
import { ExplorationBadges } from "@/components/gamification/badges";
import { SkillTree } from "@/components/gamification/skill-tree";
import { CounterRecommendationPanel } from "@/components/gamification/counter-recommendation-panel";
import { BiasFlags } from "@/components/bias/bias-flags";
import { emptyExploration, type ExplorationState } from "@/lib/gamification";
import type { AdvisingResponse, ProfileDraft } from "@/lib/types";

function newProfile(): ProfileDraft {
  return {
    session_id: crypto.randomUUID(),
    year_of_study: null,
    completed_modules: [],
    declared_interests: [],
    declared_skills: [],
    self_assessed_skill_levels: {},
    aspirations: [],
    aspiration_geography: "any",
    max_pathways: 3,
    require_local_first: true,
  };
}

export default function Home() {
  const [profile, setProfile] = React.useState<ProfileDraft>(newProfile);
  const [response, setResponse] = React.useState<AdvisingResponse | null>(null);
  const [exploration, setExploration] = React.useState<ExplorationState>(emptyExploration);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());

  const bumpExploration = (fn: (e: ExplorationState) => ExplorationState) =>
    setExploration((e) => fn({ ...e, pathwaysViewed: new Set(e.pathwaysViewed) }));

  const markViewed = (title: string) =>
    bumpExploration((e) => {
      e.pathwaysViewed.add(title);
      return e;
    });

  const toggleCompare = (title: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
    markViewed(title);
    bumpExploration((e) => ({ ...e, comparedPathways: e.comparedPathways || selected.size + 1 >= 2 }));
  };

  const onResponse = (r: AdvisingResponse) => {
    setResponse(r);
    setSelected(new Set());
  };

  const pathways = response?.pathways ?? [];
  const comparePathways = pathways.filter((p) => selected.has(p.pathway_title));

  return (
    <main className="container mx-auto max-w-7xl px-4 py-6">
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-tier-nepal text-white">
            <Bot className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold leading-tight">D.R.O.N.A.</h1>
            <p className="text-xs text-muted-foreground">
              Bias-aware, locally-grounded academic &amp; career advising
            </p>
          </div>
        </div>
        <HealthStatus />
      </header>

      <div className="grid gap-4 lg:grid-cols-12">
        <section className="space-y-4 lg:col-span-3">
          <ProfileBuilder
            profile={profile}
            onChange={setProfile}
            onReset={() => {
              setProfile(newProfile());
              setResponse(null);
              setExploration(emptyExploration());
              setSelected(new Set());
            }}
          />
        </section>

        <section className="lg:col-span-5">
          <div className="h-[calc(100vh-7rem)] min-h-[32rem]">
            <ChatPanel
              profile={profile}
              onResponse={onResponse}
              onQuerySent={() => bumpExploration((e) => ({ ...e, queriesAsked: e.queriesAsked + 1 }))}
            />
          </div>
        </section>

        <section className="space-y-4 lg:col-span-4">
          <DiversityMeter response={response} />
          <ExplorationBadges exploration={exploration} response={response} />
          <BiasFlags flags={response?.bias_flags ?? []} />
        </section>
      </div>

      <div className="mt-6">
        <Tabs defaultValue="pathways">
          <TabsList>
            <TabsTrigger value="pathways">
              <LayoutGrid className="h-4 w-4" /> Pathways
              {pathways.length > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {pathways.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="compare">
              <GitCompare className="h-4 w-4" /> Compare
              {comparePathways.length > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {comparePathways.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="skills">
              <Network className="h-4 w-4" /> Skill map
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pathways">
            {pathways.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-sm text-muted-foreground">
                  Ask a question to see multiple evidence-backed pathways here. You&apos;ll
                  always get more than one — by design.
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                <CounterRecommendationPanel
                  response={response}
                  declaredInterests={profile.declared_interests}
                  onReveal={() =>
                    bumpExploration((e) => ({ ...e, viewedCounterRecommendation: true }))
                  }
                />
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {pathways.map((p, i) => (
                    <PathwayCard
                      key={p.pathway_title + i}
                      pathway={p}
                      index={i}
                      selected={selected.has(p.pathway_title)}
                      onToggleCompare={() => toggleCompare(p.pathway_title)}
                      onCitationsOpen={() => {
                        markViewed(p.pathway_title);
                        bumpExploration((e) => ({ ...e, citationsOpened: e.citationsOpened + 1 }));
                      }}
                    />
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="compare">
            <PathwayComparison pathways={comparePathways} />
          </TabsContent>

          <TabsContent value="skills">
            <SkillTree
              response={response}
              haveSkills={profile.declared_skills}
              completedModules={profile.completed_modules}
            />
          </TabsContent>
        </Tabs>
      </div>

      <footer className="mt-8 border-t pt-4 text-center text-xs text-muted-foreground">
        Advising runs on a local LLM only. Your profile is session-scoped, never persisted,
        and never identity-linked.
      </footer>
    </main>
  );
}
