"use client";

/**
 * System-level validation panel - the thesis-defence numbers.
 *
 * C1-C4 score *components* (retrieval ranking, detector F1, gesture jerk). This
 * panel scores the ADVICE itself:
 *   - hallucination resistance: is every recommendation traceable to a document
 *     retrieval actually returned?
 *   - bias MITIGATION: does the response counter the bias, or merely flag it?
 *   - ablation: the same queries with debiasing ON vs OFF, which is the
 *     controlled comparison that demonstrates the contribution.
 *
 * Populated by scripts/run_validation.py via /evaluation. Renders an explicit
 * "not run yet" state rather than faking numbers.
 */

import { Bar, BarChart, Cell, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { EvaluationData } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const pct = (v?: number) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
const num = (v?: number, d = 2) => (v == null ? "—" : v.toFixed(d));

function Metric({
  label,
  value,
  hint,
  good,
}: {
  label: string;
  value: string;
  hint: string;
  good?: boolean;
}) {
  return (
    <div className="rounded-md border border-border/60 p-3">
      <p className="text-[11px] uppercase text-muted-foreground">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold ${
          good === true ? "text-tier-nepal" : good === false ? "text-amber-600" : ""
        }`}
      >
        {value}
      </p>
      <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>
    </div>
  );
}

export function ValidationPanel({ data }: { data: EvaluationData | null }) {
  const v = data?.validation;

  if (!v?.hallucination && !v?.bias_mitigation_on) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">System-level validation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Not run yet. These measure the <em>advice</em> (grounding, bias mitigation, and the
            debiasing ablation) rather than the components. Generate them with:
          </p>
          <pre className="mt-3 overflow-x-auto rounded-md bg-muted/50 p-3 text-[11px]">
{`python scripts/run_validation.py                    # local engine
python scripts/run_validation.py --remote-url <T4>  # served brain`}
          </pre>
        </CardContent>
      </Card>
    );
  }

  const h = v.hallucination ?? {};
  const on = v.bias_mitigation_on ?? {};
  const off = v.bias_mitigation_off ?? null;
  const delta = v.ablation_delta ?? null;

  // Ablation: mitigation ON vs OFF on the metrics that encode "less biased".
  const ablationData = off
    ? [
        {
          metric: "pathway diversity",
          on: on.mean_pathway_diversity ?? 0,
          off: off.mean_pathway_diversity ?? 0,
        },
        {
          metric: "multi-pathway rate",
          on: on.multi_pathway_rate ?? 0,
          off: off.multi_pathway_rate ?? 0,
        },
        {
          metric: "counter-recommend",
          on: on.counter_recommendation_rate ?? 0,
          off: off.counter_recommendation_rate ?? 0,
        },
        {
          metric: "hedging",
          on: on.mean_hedge_frequency ?? 0,
          off: off.mean_hedge_frequency ?? 0,
        },
      ]
    : [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-sm">Hallucination resistance</CardTitle>
          <Badge variant="outline" className="text-[10px]">
            {v.n_queries ?? 0} queries · {v.source ?? "—"}
          </Badge>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Grounded pathways"
            value={pct(h.grounded_pathway_rate)}
            hint="≥1 valid citation from the retrieved set"
            good={(h.grounded_pathway_rate ?? 0) >= 0.9}
          />
          <Metric
            label="Hallucinated citations"
            value={pct(h.hallucinated_citation_rate)}
            hint="cited sources NOT in the retrieved set (lower is better)"
            good={(h.hallucinated_citation_rate ?? 1) <= 0.05}
          />
          <Metric
            label="Fully grounded responses"
            value={pct(h.fully_grounded_response_rate)}
            hint="every pathway grounded"
            good={(h.fully_grounded_response_rate ?? 0) >= 0.9}
          />
          <Metric
            label="Citations / pathway"
            value={num(h.mean_citations_per_pathway)}
            hint="mean evidence per recommendation"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Bias mitigation (does the answer counter the bias?)</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Pathway diversity"
            value={num(on.mean_pathway_diversity)}
            hint="options offered - counters anchoring"
          />
          <Metric
            label="Multi-pathway rate"
            value={pct(on.multi_pathway_rate)}
            hint="never a single-answer verdict"
          />
          <Metric
            label="Counter-recommendations"
            value={pct(on.counter_recommendation_rate)}
            hint="offers the non-obvious option - counters confirmation bias"
          />
          <Metric
            label="Hedging"
            value={num(on.mean_hedge_frequency)}
            hint="calibrated uncertainty vs false confidence"
          />
          <Metric
            label="Bias flags surfaced"
            value={pct(on.bias_flag_coverage)}
            hint="named to the student, not silently corrected"
          />
          <Metric
            label="Refusal rate"
            value={pct(on.refusal_rate)}
            hint="honest 'I don't know' instead of guessing"
          />
          <Metric
            label="Nepal-first rate"
            value={pct(on.nepal_first_rate)}
            hint="local evidence ranked top (C4)"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">
            Ablation - debiasing ON vs OFF (the controlled experiment)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!off ? (
            <p className="text-sm text-muted-foreground">
              Ablation not included in this run. Re-run <code>scripts/run_validation.py</code>{" "}
              against the local engine (the prompt is built server-side, so the ablation needs it).
            </p>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={ablationData} margin={{ left: 8, right: 8 }}>
                  <XAxis dataKey="metric" tick={{ fontSize: 10 }} interval={0} angle={-12} dy={8} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip cursor={{ fill: "hsl(var(--muted)/0.3)" }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="on" name="mitigation ON" fill="hsl(var(--tier-nepal))" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="off" name="mitigation OFF" fill="hsl(var(--muted-foreground))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              {delta ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(delta).map(([k, d]) => (
                    <Badge
                      key={k}
                      variant="outline"
                      className={`text-[10px] ${d > 0 ? "text-tier-nepal" : d < 0 ? "text-amber-600" : ""}`}
                    >
                      {k.replace(/_/g, " ")}: {d > 0 ? "+" : ""}
                      {d.toFixed(3)}
                    </Badge>
                  ))}
                </div>
              ) : null}
              <p className="mt-3 text-[11px] text-muted-foreground">
                Positive deltas mean the bias-mitigation prompting measurably changed the advice -
                the evidence that the contribution works, rather than an assertion that it does.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
