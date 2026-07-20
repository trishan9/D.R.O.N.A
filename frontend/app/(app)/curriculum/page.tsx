"use client";

/**
 * Curriculum explorer - the real Softwarica corpus the advisor retrieves over.
 *
 * Every module here is ingested data, not a hand-written list. The page exists
 * to make the retrieval corpus inspectable: a reader can see which programmes
 * and years are covered, which skills the curriculum actually teaches, and -
 * importantly - how UNEVEN the lecture-text depth is across modules.
 *
 * The LMS lesson text itself is authenticated college material and is never sent
 * to the browser; only its size is, which is what the depth banding shows.
 */

import { useEffect, useMemo, useState } from "react";
import { BookOpen, GraduationCap, Layers, Search, Sparkles } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getCurriculumModules,
  type CurriculumModuleRow,
  type CurriculumModules,
} from "@/lib/api";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const PROGRAMME_LABELS: Record<string, string> = {
  software_engineering: "Software Engineering",
  ethical_hacking: "Ethical Hacking",
  csai: "CS with AI",
};

const DEPTH_COLOUR: Record<string, string> = {
  deep: "hsl(var(--tier-nepal))",
  moderate: "hsl(var(--tier-regional))",
  light: "hsl(var(--tier-synthetic))",
  "catalogue only": "hsl(var(--muted-foreground))",
};

const axisProps = {
  stroke: "hsl(var(--muted-foreground))",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

const tooltipStyle = {
  contentStyle: {
    background: "hsl(var(--popover))",
    border: "1px solid hsl(var(--border))",
    borderRadius: 10,
    fontSize: 12,
    color: "hsl(var(--popover-foreground))",
  },
  cursor: { fill: "hsl(var(--muted))", opacity: 0.4 },
} as const;

function ModuleCard({ m }: { m: CurriculumModuleRow }) {
  return (
    <Card className="card-interactive">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-mono text-[10px]">
            {m.module_code}
          </Badge>
          <Badge variant="secondary" className="text-[10px]">
            Year {m.year}
          </Badge>
          {m.credits ? (
            <Badge variant="secondary" className="text-[10px]">
              {m.credits} cr
            </Badge>
          ) : null}
          <Badge
            className="ml-auto text-[10px]"
            style={{
              background: `color-mix(in srgb, ${DEPTH_COLOUR[m.content_depth]} 15%, transparent)`,
              color: DEPTH_COLOUR[m.content_depth],
            }}
            title={`${m.content_chars.toLocaleString()} characters of lecture text back this module in the RAG index`}
          >
            {m.content_depth}
          </Badge>
        </div>
        <CardTitle className="pt-1 text-sm leading-snug">{m.title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-xs text-muted-foreground">
          {PROGRAMME_LABELS[m.programme] ?? m.programme}
          {m.is_core ? " · core" : " · elective"}
        </p>
        {m.skills.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {m.skills.slice(0, 8).map((s) => (
              <span
                key={s}
                className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {s}
              </span>
            ))}
            {m.skills.length > 8 && (
              <span className="text-[10px] text-muted-foreground">
                +{m.skills.length - 8} more
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function CurriculumPage() {
  const [data, setData] = useState<CurriculumModules | null>(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [programme, setProgramme] = useState<string>("all");
  const [year, setYear] = useState<string>("all");

  useEffect(() => {
    const ctrl = new AbortController();
    getCurriculumModules(ctrl.signal)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, []);

  const modules = useMemo(() => data?.modules ?? [], [data]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return modules.filter((m) => {
      if (programme !== "all" && m.programme !== programme) return false;
      if (year !== "all" && String(m.year) !== year) return false;
      if (!needle) return true;
      return (
        m.title.toLowerCase().includes(needle) ||
        m.module_code.toLowerCase().includes(needle) ||
        m.skills.some((s) => s.toLowerCase().includes(needle))
      );
    });
  }, [modules, q, programme, year]);

  // Charts computed from the filtered set, so they respond to the facets.
  const byYear = useMemo(() => {
    const counts = new Map<number, number>();
    for (const m of filtered) counts.set(m.year, (counts.get(m.year) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([y, count]) => ({ name: `Year ${y}`, count }));
  }, [filtered]);

  const byDepth = useMemo(() => {
    const order = ["deep", "moderate", "light", "catalogue only"];
    const counts = new Map<string, number>();
    for (const m of filtered) counts.set(m.content_depth, (counts.get(m.content_depth) ?? 0) + 1);
    return order
      .filter((d) => counts.has(d))
      .map((d) => ({ name: d, count: counts.get(d) ?? 0 }));
  }, [filtered]);

  const topSkills = useMemo(() => {
    const counts = new Map<string, number>();
    for (const m of filtered) for (const s of m.skills) counts.set(s, (counts.get(s) ?? 0) + 1);
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 12)
      .map(([name, count]) => ({ name, count }));
  }, [filtered]);

  const totals = data?.totals;

  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Curriculum explorer"
        description="Every Softwarica module the advisor retrieves over - ingested, not hand-listed."
      />

      {loading && <p className="text-sm text-muted-foreground">Loading curriculum…</p>}

      {!loading && !data?.available && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            <BookOpen className="mx-auto mb-3 h-8 w-8 opacity-40" />
            <p className="font-medium text-foreground">No ingested curriculum found</p>
            <p className="mt-1">
              Expected{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                data/processed/curriculum_modules.json
              </code>
              . Run the data pipeline to generate it.
            </p>
          </CardContent>
        </Card>
      )}

      {data?.available && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={BookOpen} label="Modules" value={totals?.modules ?? 0} accent="brand" />
            <StatCard
              icon={GraduationCap}
              label="Programmes"
              value={totals?.programmes ?? 0}
              hint="BSc pathways covered"
              accent="international"
            />
            <StatCard
              icon={Layers}
              label="Total credits"
              value={totals?.total_credits ?? 0}
              accent="regional"
            />
            <StatCard
              icon={Sparkles}
              label="Distinct skills"
              value={totals?.distinct_skills ?? 0}
              hint="taught across the corpus"
              accent="nepal"
            />
          </div>

          {/* Facets */}
          <Card>
            <CardContent className="flex flex-wrap items-center gap-2 py-4">
              <div className="relative min-w-[220px] flex-1">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search title, code, or skill…"
                  className="pl-8"
                />
              </div>
              <div className="flex flex-wrap gap-1">
                <Button
                  size="sm"
                  variant={programme === "all" ? "default" : "outline"}
                  onClick={() => setProgramme("all")}
                >
                  All programmes
                </Button>
                {(data.facets?.programmes ?? []).map((p) => (
                  <Button
                    key={p}
                    size="sm"
                    variant={programme === p ? "default" : "outline"}
                    onClick={() => setProgramme(p)}
                  >
                    {PROGRAMME_LABELS[p] ?? p}
                  </Button>
                ))}
              </div>
              <div className="flex flex-wrap gap-1">
                <Button
                  size="sm"
                  variant={year === "all" ? "default" : "outline"}
                  onClick={() => setYear("all")}
                >
                  All years
                </Button>
                {(data.facets?.years ?? []).map((y) => (
                  <Button
                    key={y}
                    size="sm"
                    variant={year === String(y) ? "default" : "outline"}
                    onClick={() => setYear(String(y))}
                  >
                    Y{y}
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Charts over the current selection */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Modules per year</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={byYear}>
                    <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <XAxis dataKey="name" {...axisProps} />
                    <YAxis allowDecimals={false} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Bar dataKey="count" fill="hsl(var(--brand))" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Lecture-text depth</CardTitle>
                <p className="text-xs text-muted-foreground">
                  How much real content backs each module in the RAG index.
                </p>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={byDepth}>
                    <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <XAxis dataKey="name" {...axisProps} />
                    <YAxis allowDecimals={false} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {byDepth.map((d) => (
                        <Cell key={d.name} fill={DEPTH_COLOUR[d.name]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Most-taught skills</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={topSkills} layout="vertical" margin={{ left: 4 }}>
                    <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
                    <XAxis type="number" allowDecimals={false} {...axisProps} />
                    <YAxis type="category" dataKey="name" width={92} {...axisProps} />
                    <Tooltip {...tooltipStyle} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar
                      dataKey="count"
                      name="modules teaching it"
                      fill="hsl(var(--tier-international))"
                      radius={[0, 3, 3, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          <SectionHeading
            title={`${filtered.length} module${filtered.length === 1 ? "" : "s"}`}
            description={
              filtered.length === modules.length
                ? "Showing the whole ingested corpus."
                : `Filtered from ${modules.length} ingested modules.`
            }
          />

          {filtered.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                No modules match those filters.
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filtered.map((m) => (
                <ModuleCard key={`${m.programme}-${m.module_code}`} m={m} />
              ))}
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            Lecture text is authenticated Softwarica LMS material and is never sent to the browser -
            only its size, which is what the depth banding above reflects.
          </p>
        </>
      )}
    </div>
  );
}
