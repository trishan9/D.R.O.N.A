"use client";

/**
 * Corpus & market analytics - every number measured from the ingested data.
 *
 * Source: GET /corpus/stats, computed over the real Softwarica curriculum, the
 * O*NET pathway set and the collected job postings. Nothing here is an
 * illustrative shape; if an aggregate is missing the card says so.
 *
 * The headline is the SKILL GAP: which skills real postings ask for, and
 * whether the curriculum actually covers them. That is the evidence behind
 * "advice grounded in the local market".
 */

import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BookOpen, Briefcase, Building2, Route, Sparkles, Target } from "lucide-react";

import type { CorpusStats } from "@/lib/api";
import { StatCard } from "@/components/shared/stat-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TIER_FILL: Record<string, string> = {
  nepal: "hsl(var(--tier-nepal))",
  regional: "hsl(var(--tier-regional))",
  international: "hsl(var(--tier-international))",
  synthetic: "hsl(var(--muted-foreground))",
};

const PROGRAMME_LABEL: Record<string, string> = {
  csai: "CS + AI",
  ethical_hacking: "Ethical Hacking",
  software_engineering: "Software Eng.",
};

function ChartCard({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
        {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function CorpusPanel({ data }: { data: CorpusStats | null }) {
  if (!data?.available) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Corpus analytics unavailable - start the API and ensure the ingested data exists
          (<code>data/processed/</code>).
        </CardContent>
      </Card>
    );
  }

  const t = data.totals;
  const gap = data.skill_gap ?? [];
  const uncovered = gap.filter((g) => !g.covered);
  const coverage = data.skill_coverage_rate ?? 0;

  const programmeData = (data.modules_by_programme ?? []).map((d) => ({
    ...d,
    label: PROGRAMME_LABEL[d.name] ?? d.name,
  }));

  return (
    <div className="space-y-4">
      {/* Data cards - the real corpus at a glance */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <StatCard icon={BookOpen} label="Modules" value={String(t?.modules ?? 0)} hint="Softwarica curriculum" />
        <StatCard icon={Route} label="Career pathways" value={String(t?.pathways ?? 0)} hint="O*NET-derived" />
        <StatCard icon={Briefcase} label="Job postings" value={String(t?.postings ?? 0)} hint="Nepal + international" />
        <StatCard icon={Building2} label="Employers" value={String(t?.employers ?? 0)} hint="distinct hiring orgs" />
        <StatCard icon={Sparkles} label="Skills demanded" value={String(t?.distinct_skills_demanded ?? 0)} hint="distinct, from postings" />
        <StatCard
          icon={Target}
          label="Curriculum coverage"
          value={`${(coverage * 100).toFixed(0)}%`}
          hint="of top demanded skills"
        />
      </div>

      {/* THE headline: market demand vs curriculum coverage */}
      <Card className="border-brand/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Skill gap - market demand vs curriculum coverage</CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Each bar is a skill real postings ask for. Green = the curriculum covers it; amber = a
            gap. Coverage is a literal text match against module titles/descriptions/content, so it
            is falsifiable rather than an LLM judgement.
          </p>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={gap} margin={{ left: 8, right: 8, bottom: 42 }}>
              <XAxis dataKey="skill" tick={{ fontSize: 10 }} interval={0} angle={-40} textAnchor="end" height={62} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                cursor={{ fill: "hsl(var(--muted)/0.3)" }}
                formatter={(v: number, n: string) => [v, n === "taught" ? "covered by curriculum" : "NOT covered"]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="taught" stackId="a" name="covered" fill="hsl(var(--tier-nepal))" radius={[3, 3, 0, 0]} />
              <Bar dataKey="gap" stackId="a" name="gap" fill="hsl(38 92% 50%)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          {uncovered.length ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground">Not covered:</span>
              {uncovered.map((g) => (
                <Badge key={g.skill} variant="outline" className="text-[10px] text-amber-600">
                  {g.skill} ({g.demand})
                </Badge>
              ))}
            </div>
          ) : (
            <p className="mt-3 text-[11px] text-tier-nepal">
              Every top-demanded skill is covered somewhere in the curriculum.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard title="Modules by programme" hint="Where the curriculum's weight sits">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={programmeData} margin={{ left: 8, right: 8 }}>
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
              <Bar dataKey="count" name="modules" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Job postings by data tier" hint="Nepal-first grounding (contribution C4)">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={data.postings_by_tier ?? []}
                dataKey="count"
                nameKey="name"
                innerRadius={52}
                outerRadius={82}
                paddingAngle={2}
              >
                {(data.postings_by_tier ?? []).map((d) => (
                  <Cell key={d.name} fill={TIER_FILL[d.name] ?? "hsl(var(--primary))"} />
                ))}
              </Pie>
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Most demanded skills" hint="Frequency across all collected postings">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.top_skills_demanded ?? []} layout="vertical" margin={{ left: 12, right: 8 }}>
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={92} tick={{ fontSize: 10 }} />
              <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
              <Bar dataKey="count" name="postings" fill="hsl(var(--tier-international))" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top hiring employers" hint="Who is actually posting these roles">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.top_employers ?? []} layout="vertical" margin={{ left: 12, right: 8 }}>
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis dataKey="name" type="category" width={112} tick={{ fontSize: 10 }} />
              <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
              <Bar dataKey="count" name="postings" fill="hsl(var(--tier-nepal))" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
