"use client";

import * as React from "react";
import { Route, LayoutGrid, GitCompare } from "lucide-react";

import { useStore } from "@/lib/store";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { PathwayCard } from "@/components/pathways/pathway-card";
import { PathwayComparison } from "@/components/pathways/pathway-comparison";
import { CounterRecommendationPanel } from "@/components/gamification/counter-recommendation-panel";
import { EmptyState } from "@/components/shared/empty-state";

export default function PathwaysPage() {
  const { response, profile, markPathwayViewed, bumpExploration } = useStore();
  const [selected, setSelected] = React.useState<Set<string>>(new Set());

  const pathways = response?.pathways ?? [];
  const comparePathways = pathways.filter((p) => selected.has(p.pathway_title));

  const toggleCompare = (title: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      return next;
    });
    markPathwayViewed(title);
    bumpExploration((e) => ({ ...e, comparedPathways: e.comparedPathways || selected.size + 1 >= 2 }));
  };

  if (!response || pathways.length === 0) {
    return (
      <div className="animate-fade-in">
        <EmptyState
          icon={Route}
          title="No pathways yet"
          description="Ask D.R.O.N.A. a question and it will surface multiple evidence-backed pathways here - always more than one, by design, to counter anchoring."
          actionLabel="Go to the Advisor"
          actionHref="/advisor"
        />
      </div>
    );
  }

  return (
    <div className="space-y-4 animate-fade-in">
      <Tabs defaultValue="pathways">
        <TabsList>
          <TabsTrigger value="pathways">
            <LayoutGrid className="h-4 w-4" /> All pathways
            <Badge variant="secondary" className="ml-1">{pathways.length}</Badge>
          </TabsTrigger>
          <TabsTrigger value="compare">
            <GitCompare className="h-4 w-4" /> Compare
            {comparePathways.length > 0 && (
              <Badge variant="secondary" className="ml-1">{comparePathways.length}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pathways" className="space-y-4">
          <CounterRecommendationPanel
            response={response}
            declaredInterests={profile.declared_interests}
            onReveal={() => bumpExploration((e) => ({ ...e, viewedCounterRecommendation: true }))}
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
                  markPathwayViewed(p.pathway_title);
                  bumpExploration((e) => ({ ...e, citationsOpened: e.citationsOpened + 1 }));
                }}
              />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="compare">
          {comparePathways.length === 0 ? (
            <EmptyState
              icon={GitCompare}
              title="Pick pathways to compare"
              description="Use the Compare toggle on any pathway card to line them up side-by-side and weigh them on the same evidence - a deliberate counter to confirmation bias."
            />
          ) : (
            <PathwayComparison pathways={comparePathways} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
