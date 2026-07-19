"use client";

import { useEffect, useState } from "react";
import { Activity, ShieldAlert, Route, MapPin, Timer, Gauge, Trophy } from "lucide-react";

import { useStore } from "@/lib/store";
import { CONTRIBUTIONS, liveSummary } from "@/lib/analytics";
import { getEvaluation, type EvaluationData } from "@/lib/api";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AblationBars,
  BiasBars,
  JerkBars,
  LlmLossBars,
  PolicyBars,
  TierDonut,
} from "@/components/analytics/charts";
import { ValidationPanel } from "@/components/analytics/validation-panel";

function SourceBadge({ live, thesis }: { live?: boolean; thesis?: boolean }) {
  if (thesis) {
    return (
      <Badge className="gap-1 bg-tier-nepal/15 text-[10px] text-tier-nepal hover:bg-tier-nepal/15">
        Thesis run (measured)
      </Badge>
    );
  }
  return (
    <Badge variant={live ? "default" : "outline"} className="gap-1 text-[10px]">
      {live ? "Live (this session)" : "Reference shape"}
    </Badge>
  );
}

export default function AnalyticsPage() {
  const { response } = useStore();
  const s = liveSummary(response);
  const [evalData, setEvalData] = useState<EvaluationData | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEvaluation(ctrl.signal)
      .then((d) => setEvalData(d.available ? d : null))
      .catch(() => setEvalData(null));
    return () => ctrl.abort();
  }, []);

  const hasC1 = Boolean(evalData?.c1_ablation?.length);
  const hasC2 = Boolean(evalData?.c2_per_type?.length);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Live session metrics */}
      <section className="space-y-3">
        <SectionHeading
          title="Live session metrics"
          description="Computed in-browser from your most recent advising response - fully reproducible, not placeholders."
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <StatCard label="Pathways" value={s.pathwayCount} icon={Route} accent="brand" />
          <StatCard label="Diversity" value={s.hasResponse ? s.diversityScore : "-"} hint={s.diversityLabel} icon={Gauge} accent="international" />
          <StatCard label="Bias checks" value={s.biasFlagCount} icon={ShieldAlert} accent="regional" />
          <StatCard label="Citations" value={s.citationCount} icon={Activity} accent="synthetic" />
          <StatCard label="Nepal-first" value={s.hasResponse ? `${s.nepalRate}%` : "-"} icon={MapPin} accent="nepal" />
          <StatCard
            label="Latency"
            value={s.generationMs ? `${(s.generationMs / 1000).toFixed(1)}s` : "-"}
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
            <SourceBadge thesis={hasC1} />
          </CardHeader>
          <CardContent>
            <AblationBars data={evalData?.c1_ablation} />
            <p className="mt-1 text-xs text-muted-foreground">
              {hasC1
                ? "Measured on the labelled query bank: hybrid (BM25 + dual dense + RRF) vs single-system baselines."
                : "Illustrative shape - run notebook 05 (or scripts/run_evaluation.py --all) for measured numbers."}
            </p>
          </CardContent>
        </Card>

        <Card className="card-interactive">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Bias detection P/R/F1 (C2)</CardTitle>
            <SourceBadge thesis={hasC2} />
          </CardHeader>
          <CardContent>
            <BiasBars data={evalData?.c2_per_type} />
            <p className="mt-1 text-xs text-muted-foreground">
              {hasC2
                ? `Measured per bias type - macro-F1 ${evalData?.c2_macro_f1?.toFixed(2)} across the labelled query bank.`
                : "Illustrative shape across the six biases. The harness (notebook 05) emits the real per-bias scores."}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* System-level validation: the advice itself, not the components */}
      <div className="space-y-3">
        <SectionHeading
          title="System-level validation (the advice, not the components)"
          description="Hallucination resistance, whether the response actually counters the detected bias, and the debiasing ON/OFF ablation. Generated by scripts/run_validation.py."
        />
        <ValidationPanel data={evalData} />
      </div>

      {/* Thesis model evaluation (real artifacts from notebooks 04/05) */}
      {evalData && (
        <section className="space-y-3">
          <SectionHeading
            title="Model evaluation - thesis run"
            description={`Loaded from reports/ (generated ${evalData.generated ?? "n/a"}) - the same numbers as notebook 05.`}
          />
          <div className="grid gap-4 lg:grid-cols-2">
            {evalData.c3_policies && evalData.c3_policies.length > 0 && (
              <Card className="card-interactive">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-base">Gesture policy comparison (C3)</CardTitle>
                  <SourceBadge thesis />
                </CardHeader>
                <CardContent>
                  <PolicyBars data={evalData.c3_policies} />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Success rate per policy across all six gestures; hover for smoothness (mean |jerk|).
                  </p>
                </CardContent>
              </Card>
            )}
            {evalData.llm?.base_eval_loss != null && evalData.llm?.final_eval_loss != null && (
              <Card className="card-interactive">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-base">Advising LLM fine-tune</CardTitle>
                  <SourceBadge thesis />
                </CardHeader>
                <CardContent>
                  <LlmLossBars base={evalData.llm.base_eval_loss} tuned={evalData.llm.final_eval_loss} />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Validation cross-entropy, {evalData.llm.base_model ?? "base model"} before vs after LoRA
                    fine-tuning (notebook 04).
                  </p>
                </CardContent>
              </Card>
            )}
            {evalData.verdict && evalData.verdict.length > 0 && (
              <Card className="card-interactive lg:col-span-2">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <CardTitle className="text-base">Model selection verdict</CardTitle>
                  <SourceBadge thesis />
                </CardHeader>
                <CardContent className="space-y-2">
                  {evalData.verdict.map((v) => (
                    <div key={v.component} className="flex flex-wrap items-center gap-2 text-sm">
                      <Trophy className="h-3.5 w-3.5 text-tier-nepal" />
                      <span className="font-medium">{v.component}:</span>
                      <Badge variant="secondary" className="text-[11px]">{v.winner}</Badge>
                      <span className="text-xs text-muted-foreground">{v.evidence}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        </section>
      )}

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
