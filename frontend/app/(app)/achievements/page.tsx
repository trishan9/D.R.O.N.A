"use client";

import { MessageSquare, Eye, Search, GitCompare, Shuffle, Trophy } from "lucide-react";

import { useStore } from "@/lib/store";
import { computeBadges } from "@/lib/gamification";
import { ExplorationBadges } from "@/components/gamification/badges";
import { DiversityMeter } from "@/components/gamification/diversity-meter";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AchievementsPage() {
  const { exploration, response, history } = useStore();
  const earned = computeBadges(exploration, response).filter((b) => b.earned).length;

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Badges earned" value={`${earned}/6`} icon={Trophy} accent="brand" />
        <StatCard label="Questions asked" value={exploration.queriesAsked} icon={MessageSquare} accent="international" />
        <StatCard label="Pathways viewed" value={exploration.pathwaysViewed.size} icon={Eye} accent="regional" />
        <StatCard label="Citations opened" value={exploration.citationsOpened} icon={Search} accent="synthetic" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <SectionHeading
            title="Exploration badges"
            description="These reward breadth and scepticism — not committing fast. That's the point: the gamification fights anchoring and confirmation bias instead of feeding them."
          />
          <ExplorationBadges exploration={exploration} response={response} />

          <Card>
            <CardHeader className="border-b py-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">Anti-bias habits</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-2 pt-4 sm:grid-cols-2">
              <Habit
                icon={GitCompare}
                label="Compared pathways"
                done={exploration.comparedPathways}
                hint="Weighed options side-by-side"
              />
              <Habit
                icon={Shuffle}
                label="Saw the counter-recommendation"
                done={exploration.viewedCounterRecommendation}
                hint="Considered the option you'd skip"
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <DiversityMeter response={response} />
          <Card>
            <CardHeader className="border-b py-3">
              <CardTitle className="text-sm font-semibold text-muted-foreground">Recent questions</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              {history.length === 0 ? (
                <p className="text-sm text-muted-foreground">Your asked questions will appear here.</p>
              ) : (
                <ul className="space-y-2.5">
                  {history.slice(0, 6).map((h) => (
                    <li key={h.id} className="border-l-2 border-brand/40 pl-3 text-sm">
                      <p className="line-clamp-2">{h.query}</p>
                      <p className="text-xs text-muted-foreground">
                        {h.pathwayCount} pathways · {h.biasCount} bias checks
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Habit({
  icon: Icon,
  label,
  done,
  hint,
}: {
  icon: typeof GitCompare;
  label: string;
  done: boolean;
  hint: string;
}) {
  return (
    <div
      className={
        "flex items-start gap-2.5 rounded-lg border p-3 " +
        (done ? "border-brand/40 bg-brand/5" : "opacity-70")
      }
    >
      <Icon className={"mt-0.5 h-4 w-4 " + (done ? "text-brand" : "text-muted-foreground")} />
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{done ? hint : "Not yet"}</p>
      </div>
    </div>
  );
}
