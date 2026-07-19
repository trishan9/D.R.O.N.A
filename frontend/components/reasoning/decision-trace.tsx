"use client";

/**
 * Decision Trace - the explainability view.
 *
 * Answers "why did D.R.O.N.A. say that?" by laying out the whole chain the
 * system actually executed, in order, from the last advising response:
 *
 *   student context -> question -> bias analysis -> retrieved evidence
 *   -> ranked pathways -> spoken answer
 *
 * Everything shown is read from the real AdvisingResponse + the session profile;
 * nothing is invented. If a stage produced nothing (e.g. no bias detected) the
 * card says so explicitly rather than hiding, because "no bias found" is itself
 * a result worth defending.
 */

import {
  Bar,
  BarChart,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AdvisingResponse, ProfileDraft } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TIER_COLOR: Record<string, string> = {
  nepal: "hsl(var(--tier-nepal))",
  regional: "hsl(var(--tier-regional))",
  international: "hsl(var(--tier-international))",
  synthetic: "hsl(var(--muted-foreground))",
};

function Stage({
  n,
  title,
  subtitle,
  children,
}: {
  n: number;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="relative overflow-hidden">
      <span className="absolute left-0 top-0 h-full w-1 bg-primary/60" aria-hidden />
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <span className="grid h-6 w-6 place-items-center rounded-full bg-primary/15 text-[11px] font-semibold text-primary">
            {n}
          </span>
          {title}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground">{children}</p>;
}

export function DecisionTrace({
  response,
  profile,
  question,
}: {
  response: AdvisingResponse | null;
  profile: ProfileDraft;
  question?: string;
}) {
  if (!response) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-sm text-muted-foreground">
            No advising response yet. Ask D.R.O.N.A. a question on the Advisor page, then come
            back - this page reconstructs exactly how that answer was produced.
          </p>
        </CardContent>
      </Card>
    );
  }

  // ── Evidence ─────────────────────────────────────────────────────────────
  const allCitations = response.pathways.flatMap((p) => p.citations);
  const byTier = allCitations.reduce<Record<string, number>>((acc, c) => {
    acc[c.tier] = (acc[c.tier] ?? 0) + 1;
    return acc;
  }, {});
  const tierData = Object.entries(byTier).map(([tier, count]) => ({ tier, count }));
  const relevanceData = allCitations
    .slice()
    .sort((a, b) => b.relevance_score - a.relevance_score)
    .slice(0, 8)
    .map((c) => ({
      source: c.source_id.length > 16 ? `${c.source_id.slice(0, 16)}…` : c.source_id,
      score: Number(c.relevance_score.toFixed(3)),
      tier: c.tier,
    }));

  // ── Pathway confidence (why one option over another) ─────────────────────
  const confScore = { low: 1, medium: 2, high: 3 } as const;
  const pathwayData = response.pathways.map((p) => ({
    pathway: p.pathway_title.length > 18 ? `${p.pathway_title.slice(0, 18)}…` : p.pathway_title,
    confidence: confScore[p.confidence] ?? 2,
    evidence: p.citations.length,
    modules: p.matched_softwarica_modules.length,
  }));

  const skills = profile.declared_skills ?? [];
  const interests = profile.declared_interests ?? [];

  return (
    <div className="space-y-4">
      {/* 1 - what the system knew about the student */}
      <Stage
        n={1}
        title="Student context the model was given"
        subtitle="Session-scoped only - never persisted, never identity-linked."
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-[11px] uppercase text-muted-foreground">Goal</p>
            <Badge variant="secondary" className="mt-1">{profile.goal ?? "employment"}</Badge>
          </div>
          <div>
            <p className="text-[11px] uppercase text-muted-foreground">Programme / year</p>
            <p className="mt-1 text-sm">
              {profile.programme ?? "—"} {profile.year_of_study ? `· Year ${profile.year_of_study}` : ""}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase text-muted-foreground">Declared skills</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {skills.length ? (
                skills.slice(0, 6).map((s) => (
                  <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">none given</span>
              )}
            </div>
          </div>
          <div>
            <p className="text-[11px] uppercase text-muted-foreground">Interests</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {interests.length ? (
                interests.slice(0, 6).map((s) => (
                  <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">none given</span>
              )}
            </div>
          </div>
        </div>
        {question ? (
          <p className="mt-4 rounded-md bg-muted/40 p-3 text-sm">
            <span className="text-[11px] uppercase text-muted-foreground">Question </span>
            <br />“{question}”
          </p>
        ) : null}
      </Stage>

      {/* 2 - bias analysis: the core contribution */}
      <Stage
        n={2}
        title="Cognitive bias analysis"
        subtitle="Detected in the question, and how the answer was instructed to counter it."
      >
        {response.bias_flags.length === 0 ? (
          <Empty>
            No cognitive bias detected in this question - the advisor answered without applying a
            debiasing instruction. (A clean question is a valid outcome, not a failure.)
          </Empty>
        ) : (
          <div className="space-y-3">
            {response.bias_flags.map((b) => (
              <div key={b.bias_type} className="rounded-md border border-border/60 p-3">
                <div className="flex items-center gap-2">
                  <Badge className="bg-amber-500/15 text-amber-600 hover:bg-amber-500/15">
                    {b.bias_type.replace(/_/g, " ")}
                  </Badge>
                </div>
                <p className="mt-2 text-xs">
                  <span className="text-muted-foreground">Triggered by: </span>
                  <span className="font-mono">{b.detected_signal}</span>
                </p>
                <p className="mt-1 text-xs">
                  <span className="text-muted-foreground">Mitigation applied: </span>
                  {b.mitigation_applied}
                </p>
              </div>
            ))}
          </div>
        )}
      </Stage>

      {/* 3 - retrieved evidence */}
      <Stage
        n={3}
        title="Evidence retrieved (RAG)"
        subtitle="Hybrid BM25 + dense retrieval, re-ranked by a cross-encoder. Nepal-tier first."
      >
        {allCitations.length === 0 ? (
          <Empty>No citations attached to this response.</Empty>
        ) : (
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-xs text-muted-foreground">Sources by data tier</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={tierData} layout="vertical" margin={{ left: 8, right: 8 }}>
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="tier" type="category" width={86} tick={{ fontSize: 11 }} />
                  <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {tierData.map((d) => (
                      <Cell key={d.tier} fill={TIER_COLOR[d.tier] ?? "hsl(var(--primary))"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div>
              <p className="mb-2 text-xs text-muted-foreground">Top sources by relevance</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={relevanceData} margin={{ left: 8, right: 8 }}>
                  <XAxis dataKey="source" tick={{ fontSize: 10 }} interval={0} angle={-20} dy={8} />
                  <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                  <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {relevanceData.map((d, i) => (
                      <Cell key={i} fill={TIER_COLOR[d.tier] ?? "hsl(var(--primary))"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </Stage>

      {/* 4 - the decision */}
      <Stage
        n={4}
        title="Ranked pathways and why"
        subtitle="Multiple options are shown deliberately - single-answer advice is what anchors students."
      >
        {response.pathways.length === 0 ? (
          <Empty>
            {response.refusal
              ? `Refused: ${response.refusal_reason ?? "insufficient grounded evidence"}`
              : "No pathways returned."}
          </Empty>
        ) : (
          <>
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-xs text-muted-foreground">
                  Confidence vs supporting evidence
                </p>
                <ResponsiveContainer width="100%" height={190}>
                  <BarChart data={pathwayData} margin={{ left: 8, right: 8 }}>
                    <XAxis dataKey="pathway" tick={{ fontSize: 10 }} interval={0} angle={-15} dy={8} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
                    <Bar dataKey="confidence" name="confidence (1-3)" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="evidence" name="citations" fill="hsl(var(--tier-nepal))" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {pathwayData.length >= 3 ? (
                <div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Curriculum coverage per pathway
                  </p>
                  <ResponsiveContainer width="100%" height={190}>
                    <RadarChart data={pathwayData} outerRadius={70}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="pathway" tick={{ fontSize: 10 }} />
                      <Radar
                        dataKey="modules"
                        stroke="hsl(var(--primary))"
                        fill="hsl(var(--primary))"
                        fillOpacity={0.35}
                      />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
            </div>

            <div className="mt-4 space-y-3">
              {response.pathways.map((p, i) => (
                <div key={i} className="rounded-md border border-border/60 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{p.pathway_title}</span>
                    <Badge variant="outline" className="text-[10px]">{p.confidence} confidence</Badge>
                    {p.goal_type ? (
                      <Badge variant="secondary" className="text-[10px]">{p.goal_type}</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{p.rationale}</p>
                  {p.matched_softwarica_modules.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {p.matched_softwarica_modules.map((m) => (
                        <Badge key={m} variant="outline" className="text-[10px]">{m}</Badge>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </>
        )}
      </Stage>

      {/* 5 - what the robot said */}
      <Stage
        n={5}
        title="Spoken answer"
        subtitle="The exact text sent to the robot's voice (speech_node)."
      >
        <p className="rounded-md bg-muted/40 p-3 text-sm">“{response.speak_text}”</p>
        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
          {response.generation_time_ms != null ? (
            <Badge variant="outline">{response.generation_time_ms} ms</Badge>
          ) : null}
          <Badge variant="outline">{response.pathways.length} pathways</Badge>
          <Badge variant="outline">{allCitations.length} citations</Badge>
          {response.requires_human_followup ? (
            <Badge className="bg-amber-500/15 text-amber-600 hover:bg-amber-500/15">
              human follow-up advised
            </Badge>
          ) : null}
        </div>
      </Stage>
    </div>
  );
}
