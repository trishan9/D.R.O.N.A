"use client";

import { Activity, ShieldAlert, Route, MapPin, Timer, Gauge } from "lucide-react";

import { useStore } from "@/lib/store";
import { CONTRIBUTIONS, liveSummary } from "@/lib/analytics";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AblationBars, BiasBars, JerkBars, TierDonut } from "@/components/analytics/charts";

function SourceBadge({ live }: { live?: boolean }) {
  return (
    <Badge variant={live ? "default" : "outline"} className="gap-1 text-[10px]">
      {live ? "Live (this session)" : "Reference shape"}
    </Badge>
  );
}

export default function AnalyticsPage() {
  const { response } = useStore();
  const s = liveSummary(response);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Live session metrics */}
      <section className="space-y-3">
        <SectionHeading
          title="Live session metrics"
          description="Computed in-browser from your most recent advising response — fully reproducible, not placeholders."
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Pathways" value={s.pathwayCount} icon={Route} accent="brand" />
          <StatCard label="Diversity" value={s.hasResponse ? s.diversityScore : "—"} hint={s.diversityLabel} icon={Gauge} accent="international" />
          <StatCard label="Bias checks" value={s.biasFlagCount} icon={ShieldAlert} accent="regional" />
          <StatCard label="Citations" value={s.citationCount} icon={Activity} accent="synthetic" />
          <StatCard label="Nepal-first" value={s.hasResponse ? `${s.nepalRate}%` : "—"} icon={MapPin} accent="nepal" />
          <StatCard
            label="Latency"
            value={s.generationMs ? `${(s.generationMs / 1000).toFixed(1)}s` : "—"}
            icon={Timer}
            accent="muted"
          />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="card-interactive">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Citation tier mix (C4)</CardTitle>
            <SourceBadge live />
          </CardHeader>
          <CardContent>
            <TierDonut response={response} />
            <p className="mt-1 text-xs text-muted-foreground">
              Where the current answer&apos;s evidence comes from. Nepal-first ordering is the flagship locality claim.
            </p>
          </CardContent>
        </Card>

        <Card className="card-interactive">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Gesture smoothness (C3)</CardTitle>
            <SourceBadge live />
          </CardHeader>
          <CardContent>
            <JerkBars />
            <p className="mt-1 text-xs text-muted-foreground">
              Mean absolute jerk of the keyframe baseline, computed live from the real trajectories. ACT/Diffusion
              policies aim to lower these (run notebooks 07/08 to compare).
            </p>
          </CardContent>
        </Card>

        <Card className="card-interactive">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Retrieval ablation (C1)</CardTitle>
            <SourceBadge />
          </CardHeader>
          <CardContent>
            <AblationBars />
            <p className="mt-1 text-xs text-muted-foreground">
              Illustrative shape of the hybrid-vs-dense result. Run{" "}
              <code className="font-mono">scripts/run_evaluation.py --all</code> for your measured numbers.
            </p>
          </CardContent>
        </Card>

        <Card className="card-interactive">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Bias detection P/R/F1 (C2)</CardTitle>
            <SourceBadge />
          </CardHeader>
          <CardContent>
            <BiasBars />
            <p className="mt-1 text-xs text-muted-foreground">
              Illustrative shape across the six biases. The harness (notebook 05) emits the real per-bias scores.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Contribution framework */}
      <section className="space-y-3">
        <SectionHeading
          title="Research contributions"
          description="The four claims this system is built to support and measure."
        />
        <div className="grid gap-3 sm:grid-cols-2">
          {CONTRIBUTIONS.map((c, i) => {
            const accent = [
              "text-brand bg-brand/10",
              "text-tier-international bg-tier-international/10",
              "text-tier-regional bg-tier-regional/10",
              "text-tier-synthetic bg-tier-synthetic/10",
            ][i % 4];
            return (
              <Card key={c.id} className="card-interactive">
                <CardContent className="space-y-2 py-4">
                  <div className="flex items-center gap-2">
                    <span className={`flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${accent}`}>
                      {c.id}
                    </span>
                    <p className="font-semibold">{c.title}</p>
                  </div>
                  <p className="text-sm text-muted-foreground">{c.claim}</p>
                  <p className="text-xs text-muted-foreground/80">{c.technique}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}
