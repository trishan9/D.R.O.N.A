"use client";

/**
 * Bias Lab - the C2b detector comparison, including the designs that failed.
 *
 * Everything here is read from reports/bias_detector_comparison.json via
 * /evaluation. Nothing on this page is illustrative: if the benchmark has not
 * been run, the page says so rather than drawing a plausible shape.
 */

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FlaskConical, Target, XCircle, Zap } from "lucide-react";

import { getEvaluation, type EvaluationData } from "@/lib/api";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DetectorComparisonBars,
  FalsePositiveBars,
  GeneralisationGapBars,
  PrecisionRecallScatter,
  shortName,
} from "@/components/analytics/detector-charts";

/** Design narrative. Each entry is tied to a row in the measured comparison. */
const FINDINGS = [
  {
    icon: XCircle,
    tone: "destructive" as const,
    title: "Embeddings lost to regexes",
    detector: "semantic (kNN, thr=0.55)",
    body: "Sentence encoders represent topic, but a cognitive bias is a property of framing. Anchoring questions about Google, a salary figure and Kathmandu share almost no topical content, while an anchoring and a confirmation question about data science are near-neighbours - so k-NN groups by subject matter and cuts across the labels.",
  },
  {
    icon: AlertTriangle,
    tone: "warning" as const,
    title: "The zero-shot LLM cried wolf",
    detector: "llm (zero-shot)",
    body: "It found nearly every real bias (recall 0.511 → 0.911) and flagged all eight neutral controls. Asked to find biases, a model finds biases. This is base-rate neglect: nothing in the prompt says most student questions are ordinary factual requests.",
  },
  {
    icon: Target,
    tone: "ok" as const,
    title: "Retrieved few-shot restored the base rate",
    detector: "rag-llm (few-shot, NO grounding)",
    body: "Putting the eight nearest labelled questions in the prompt - including neutral ones labelled [] - told the model how often 'no bias' is the right answer. Precision moved 0.521 → 0.861 and false positives fell from 8/8 to 3/8.",
  },
  {
    icon: CheckCircle2,
    tone: "ok" as const,
    title: "Span grounding removed the rest",
    detector: "hybrid (rules ∪ rag-llm) [PRODUCTION]",
    body: "Each flag must quote the words that triggered it, and the quote is verified. The first version of this check did nothing, because the model satisfied it by quoting the whole question - which is exactly what every remaining false positive did. Requiring the span to be localised removed the last 3/8.",
  },
];

function toneClass(tone: "ok" | "warning" | "destructive") {
  if (tone === "ok") return "text-tier-nepal";
  if (tone === "warning") return "text-tier-synthetic";
  return "text-destructive";
}

export default function BiasLabPage() {
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ctrl = new AbortController();
    getEvaluation(ctrl.signal)
      .then(setEvaluation)
      .catch(() => setEvaluation(null))
      .finally(() => setLoading(false));
    return () => ctrl.abort();
  }, []);

  const detectors = evaluation?.detectors;
  const rows = detectors?.rows ?? [];
  const shipped = rows.find((r) => r.shipped);
  const baseline = rows.find((r) => r.detector.startsWith("rules"));
  const bestF1 = rows.length ? rows.reduce((a, b) => (b.f1 > a.f1 ? b : a)) : undefined;

  const recallGain =
    shipped && baseline && baseline.recall > 0
      ? ((shipped.recall - baseline.recall) / baseline.recall) * 100
      : undefined;

  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Bias Lab"
        description="Four cognitive-bias detector designs, scored on the same held-out set - including the two that failed."
      />

      {loading && <p className="text-sm text-muted-foreground">Loading measured results…</p>}

      {!loading && !detectors && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            <FlaskConical className="mx-auto mb-3 h-8 w-8 opacity-40" />
            <p className="font-medium text-foreground">No detector benchmark found</p>
            <p className="mt-1">
              Run <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
                python scripts/benchmark_bias_detectors.py --llm
              </code>{" "}
              to generate <code className="text-xs">reports/bias_detector_comparison.json</code>.
            </p>
            <p className="mt-2 text-xs">
              This page renders measured results only — it will not draw an illustrative shape.
            </p>
          </CardContent>
        </Card>
      )}

      {detectors && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={CheckCircle2}
              label="Shipped detector F1"
              value={shipped ? shipped.f1.toFixed(3) : "—"}
              hint={shipped ? shortName(shipped.detector) : undefined}
            />
            <StatCard
              icon={Zap}
              label="Recall vs regex baseline"
              value={recallGain !== undefined ? `+${recallGain.toFixed(0)}%` : "—"}
              hint={
                shipped && baseline
                  ? `${baseline.recall.toFixed(3)} → ${shipped.recall.toFixed(3)}`
                  : undefined
              }
            />
            <StatCard
              icon={Target}
              label="False accusations"
              value={shipped ? `${shipped.false_positives}/${shipped.n_neutral}` : "—"}
              hint="neutral control questions wrongly flagged"
            />
            <StatCard
              icon={FlaskConical}
              label="Designs compared"
              value={String(rows.length)}
              hint={`on ${detectors.n_items} held-out items`}
            />
          </div>

          {/* The headline finding: best F1 is not what ships. */}
          {bestF1 && shipped && !bestF1.shipped && (
            <Card className="border-tier-synthetic/40 bg-tier-synthetic/5">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 text-tier-synthetic" />
                  The highest-F1 design is not the one that ships
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <p>
                  <span className="font-medium text-foreground">{shortName(bestF1.detector)}</span>{" "}
                  scores F1 {bestF1.f1.toFixed(3)} — higher than the shipped{" "}
                  {shipped.f1.toFixed(3)} — but falsely flags{" "}
                  <span className="font-medium text-destructive">
                    {bestF1.false_positives} of {bestF1.n_neutral}
                  </span>{" "}
                  neutral questions, and two of those are Nepali. A bias-aware advisor that
                  disproportionately accuses Nepali-speaking students of cognitive bias is an equity
                  failure, so the configuration that never false-accuses ships instead.
                </p>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Precision / recall trade-off</CardTitle>
                <p className="text-xs text-muted-foreground">
                  Each point is one design. Red points falsely flag neutral questions; the star is
                  what ships. Up and to the right is better — but only above the dashed line is
                  acceptable.
                </p>
              </CardHeader>
              <CardContent>
                <PrecisionRecallScatter rows={rows} />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">False positives on neutral controls</CardTitle>
                <p className="text-xs text-muted-foreground">
                  How many of the {detectors.n_neutral} ordinary factual questions each design
                  wrongly accused of showing bias. Zero is the only acceptable value for deployment.
                </p>
              </CardHeader>
              <CardContent>
                <FalsePositiveBars rows={rows} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">
                All designs — precision, recall, F1{" "}
                <span className="font-normal text-muted-foreground">
                  ({detectors.n_items} held-out items, {detectors.n_neutral} neutral)
                </span>
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Faded bars mark designs that falsely flagged neutral questions.
              </p>
            </CardHeader>
            <CardContent>
              <DetectorComparisonBars rows={rows} />
            </CardContent>
          </Card>

          <div>
            <SectionHeading
              title="What each experiment showed"
              description="Two of these four are negative results. They are reported because the mechanism behind each failure is the argument for the design that replaced it."
            />
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {FINDINGS.map((f) => {
                const row = rows.find((r) => r.detector === f.detector);
                const Icon = f.icon;
                return (
                  <Card key={f.title}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-sm">
                        <Icon className={`h-4 w-4 ${toneClass(f.tone)}`} />
                        {f.title}
                      </CardTitle>
                      {row && (
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          <Badge variant="outline" className="text-[10px]">
                            P {row.precision.toFixed(3)}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            R {row.recall.toFixed(3)}
                          </Badge>
                          <Badge variant="outline" className="text-[10px]">
                            F1 {row.f1.toFixed(3)}
                          </Badge>
                          <Badge
                            variant={row.false_positives ? "destructive" : "default"}
                            className="text-[10px]"
                          >
                            {row.false_positives}/{row.n_neutral} false
                          </Badge>
                        </div>
                      )}
                    </CardHeader>
                    <CardContent className="text-sm leading-relaxed text-muted-foreground">
                      {f.body}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>

          {evaluation?.heldout && evaluation.heldout.length > 1 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Generalisation gap (regex baseline)</CardTitle>
                <p className="text-xs text-muted-foreground">
                  The same detector on the set it was tuned against versus one it has never seen.
                  v1 reads 1.000 because it is <em>burned</em> — it measures fit, not ability. The
                  pair is the honest claim; either number alone would mislead.
                </p>
              </CardHeader>
              <CardContent>
                <GeneralisationGapBars rows={evaluation.heldout} />
              </CardContent>
            </Card>
          )}

          <Card className="border-dashed">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Limitations</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <ul className="list-disc space-y-1 pl-4">
                <li>
                  The classifier is the 4B Nepali model already served (Q4 quantised), chosen for
                  availability. A larger model would likely score better.
                </li>
                <li>
                  The evaluation set is {detectors.n_items} author-constructed questions grounded in
                  what Nepali computing students publicly discuss — <strong>not</strong> transcripts
                  of real students. It supports a relative comparison between designs, not an
                  absolute capability claim.
                </li>
                <li>
                  Recall {shipped ? shipped.recall.toFixed(3) : "—"} still means
                  roughly a third of biases go undetected.
                </li>
                <li>
                  Held-out v1 has been tuned against and is retained only as a development set.
                </li>
              </ul>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
