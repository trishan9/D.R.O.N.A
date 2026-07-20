"use client";

/**
 * Model registry - every model in the D.R.O.N.A. stack, what it does, and why it
 * was chosen over the alternatives.
 *
 * The fine-tuning loss curve is read from reports/sft_metrics.json via
 * /evaluation, so the one chart on this page is measured. The model cards
 * themselves are documentation: they describe the deployed stack and the
 * selection rationale, which is exactly what a viva asks about.
 */

import { useEffect, useState } from "react";
import {
  Boxes,
  Brain,
  Cpu,
  Eye,
  Languages,
  Layers,
  MessageSquare,
  Search,
  TrendingDown,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getEvaluation, type EvaluationData } from "@/lib/api";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface ModelCard {
  icon: typeof Brain;
  name: string;
  role: string;
  stage: "Advising" | "Retrieval" | "Perception" | "Motion" | "Speech";
  params?: string;
  why: string;
  notes?: string;
}

/**
 * The deployed stack. Kept in sync with docs/SYSTEM_REFERENCE.md section 2 -
 * that document is the source of truth, this is its interactive view.
 */
const MODELS: ModelCard[] = [
  {
    icon: Brain,
    name: "Qwen3-4B-Instruct-2507 + LoRA",
    role: "Primary English advising model",
    stage: "Advising",
    params: "4B + adapter",
    why: "Strongest ~4B open instruct model under Apache-2.0, and it runs at Q4 on modest hardware - which the local-only constraint (C4) requires. Fine-tuned with an all-linear LoRA on the Softwarica goal x bias corpus.",
    notes: "Adapter at models/advising-lora",
  },
  {
    icon: Languages,
    name: "Himalaya Gemma 4 E2B (Q4_K_M)",
    role: "Nepali advising model",
    stage: "Advising",
    params: "~4B, quantised",
    why: "Purpose-built for Nepali, so Devanagari questions are answered natively rather than translated back and forth. Served through Ollama and given the SAME retrieved curriculum context as the English path.",
    notes: "Q4_K_M deliberately: the bf16 build is 9.3 GB and crashes when split across GPU/CPU",
  },
  {
    icon: Search,
    name: "BGE-M3 + BM25 (hybrid, RRF)",
    role: "Retrieval over the local corpus",
    stage: "Retrieval",
    why: "Lexical and dense retrieval fail differently - BM25 nails exact module codes, dense catches paraphrase. Reciprocal rank fusion combines them, and the ablation (C1) is what justifies the hybrid over either alone.",
  },
  {
    icon: Layers,
    name: "bge-reranker-v2-m3",
    role: "Cross-encoder reranking",
    stage: "Retrieval",
    why: "Scores query-document pairs jointly, so it is far more accurate than the bi-encoder that produced the candidates. Affordable because it only ever sees the top-k, not the whole corpus.",
  },
  {
    icon: Boxes,
    name: "paraphrase-multilingual-MiniLM-L12-v2",
    role: "Bias exemplar retrieval",
    stage: "Advising",
    params: "~470 MB",
    why: "Multilingual, so Nepali and code-switched questions retrieve labelled exemplars through the same mechanism. Used ONLY to select few-shot examples for the bias classifier - as a standalone bias detector it measured worse than regexes (F1 0.292).",
  },
  {
    icon: Eye,
    name: "MediaPipe BlazeFace (Tasks API)",
    role: "Face detection and engagement",
    stage: "Perception",
    why: "Runs in real time on CPU, which matters because perception may end up on a Raspberry Pi at the edge rather than the workstation.",
    notes: "Tasks API - the legacy mp.solutions interface was removed in 0.10.35",
  },
  {
    icon: Cpu,
    name: "Behaviour-cloning policy (ONNX)",
    role: "Gesture generation",
    stage: "Motion",
    why: "Learned from demonstrations rather than hand-scripted, which is the C3 contribution. Exported to ONNX so the robot runs it without a Python ML stack, with a keyframe fallback tier if the policy is unavailable.",
  },
  {
    icon: MessageSquare,
    name: "ElevenLabs TTS",
    role: "Speech output",
    stage: "Speech",
    why: "Natural prosody in both English and Nepali. The API key is read from the environment only and never written into launch files or params.",
  },
];

const STAGE_ACCENT: Record<ModelCard["stage"], string> = {
  Advising: "bg-brand/10 text-brand",
  Retrieval: "bg-tier-international/10 text-tier-international",
  Perception: "bg-tier-regional/10 text-tier-regional",
  Motion: "bg-tier-synthetic/10 text-tier-synthetic",
  Speech: "bg-tier-nepal/10 text-tier-nepal",
};

const axisProps = {
  stroke: "hsl(var(--muted-foreground))",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

export default function ModelsPage() {
  const [evalData, setEvalData] = useState<EvaluationData | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getEvaluation(ctrl.signal)
      .then(setEvalData)
      .catch(() => setEvalData(null));
    return () => ctrl.abort();
  }, []);

  const llm = evalData?.llm;
  const curve = llm?.curve ?? [];
  const improvement =
    llm?.base_eval_loss && llm?.final_eval_loss
      ? ((llm.base_eval_loss - llm.final_eval_loss) / llm.base_eval_loss) * 100
      : undefined;

  const stages = [...new Set(MODELS.map((m) => m.stage))];

  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Model registry"
        description="Every model in the stack, what it does, and why it was chosen over the alternatives."
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Boxes} label="Models deployed" value={MODELS.length} accent="brand" />
        <StatCard
          icon={Layers}
          label="Pipeline stages"
          value={stages.length}
          hint={stages.join(" · ")}
          accent="international"
        />
        <StatCard
          icon={TrendingDown}
          label="Fine-tune eval loss"
          value={llm?.final_eval_loss !== undefined ? llm.final_eval_loss.toFixed(4) : "—"}
          hint={
            llm?.base_eval_loss !== undefined
              ? `from ${llm.base_eval_loss.toFixed(4)} base`
              : "run notebook 04"
          }
          accent="nepal"
        />
        <StatCard
          icon={Brain}
          label="Loss improvement"
          value={improvement !== undefined ? `${improvement.toFixed(1)}%` : "—"}
          hint="LoRA vs base model"
          accent="regional"
        />
      </div>

      {curve.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              LoRA fine-tuning - evaluation loss
              <span className="ml-2 font-normal text-muted-foreground">
                {llm?.base_model}
              </span>
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Measured, from reports/sft_metrics.json. Held-out evaluation loss per step - the
              training-loss curve is not shown because it cannot evidence generalisation.
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={curve} margin={{ left: 0, right: 12, top: 8 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
                <XAxis dataKey="step" {...axisProps} />
                <YAxis domain={["auto", "auto"]} {...axisProps} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--popover))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 10,
                    fontSize: 12,
                    color: "hsl(var(--popover-foreground))",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="eval_loss"
                  stroke="hsl(var(--brand))"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {stages.map((stage) => (
        <div key={stage}>
          <SectionHeading title={stage} />
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {MODELS.filter((m) => m.stage === stage).map((m) => {
              const Icon = m.icon;
              return (
                <Card key={m.name} className="card-interactive">
                  <CardHeader className="pb-2">
                    <div className="flex items-start gap-3">
                      <span
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${STAGE_ACCENT[m.stage]}`}
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0">
                        <CardTitle className="text-sm leading-snug">{m.name}</CardTitle>
                        <p className="text-xs text-muted-foreground">{m.role}</p>
                      </div>
                      {m.params && (
                        <Badge variant="outline" className="ml-auto shrink-0 text-[10px]">
                          {m.params}
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-sm leading-relaxed text-muted-foreground">{m.why}</p>
                    {m.notes && (
                      <p className="rounded bg-muted/60 px-2 py-1 text-[11px] text-muted-foreground">
                        {m.notes}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ))}

      <p className="text-xs text-muted-foreground">
        The advising request path is local-only: no cloud LLM is reachable from it, which the API
        asserts at startup. Speech is the one networked component.
      </p>
    </div>
  );
}
