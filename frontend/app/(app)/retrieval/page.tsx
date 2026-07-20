"use client";

/**
 * Retrieval explorer - the hybrid RAG pipeline, stage by stage, on a live query.
 *
 * The C1 ablation reports that hybrid retrieval beats BM25 or dense alone. An
 * aggregate NDCG proves that but does not SHOW it. This page runs one query
 * through each stage and puts the four rankings side by side, so the reader can
 * see which documents only lexical search found, which only the embeddings
 * found, what fusion did to the order, and what reranking moved.
 *
 * It calls the same Retriever the advising path uses, so the timings are the
 * real latency budget - including the cross-encoder, which is genuinely slow on
 * CPU and is shown rather than hidden.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowRight, Layers, Search, Sparkles, Timer } from "lucide-react";

import {
  getRetrievalTrace,
  type RetrievalTrace,
  type TraceDoc,
  type TraceStage,
} from "@/lib/api";
import { SectionHeading } from "@/components/shared/section-heading";
import { StatCard } from "@/components/shared/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EXAMPLES = [
  "Which modules prepare me for data engineering in Kathmandu?",
  "What does the ethical hacking programme cover in year 2?",
  "I want to work in AI research - what should I take?",
  "Data science नै सबैभन्दा राम्रो हो?",
];

const STAGE_ACCENT: Record<string, string> = {
  bm25: "border-tier-synthetic/50",
  dense: "border-tier-international/50",
  rrf: "border-tier-regional/50",
  rerank: "border-tier-nepal/50",
};

const TIER_CLASS: Record<string, string> = {
  nepal: "bg-tier-nepal/15 text-tier-nepal",
  regional: "bg-tier-regional/15 text-tier-regional",
  international: "bg-tier-international/15 text-tier-international",
  synthetic: "bg-tier-synthetic/15 text-tier-synthetic",
};

function DocRow({ doc, isNew }: { doc: TraceDoc; isNew: boolean }) {
  return (
    <div className="rounded-md border border-border/60 p-2">
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-[10px] text-muted-foreground">#{doc.rank}</span>
        <span
          className={`rounded px-1 py-0.5 text-[9px] font-medium ${
            TIER_CLASS[doc.tier] ?? "bg-muted text-muted-foreground"
          }`}
        >
          {doc.tier}
        </span>
        {isNew && (
          <span
            className="rounded bg-brand/15 px-1 py-0.5 text-[9px] font-medium text-brand"
            title="This document was not in the first stage's ranking - the pipeline surfaced it"
          >
            new
          </span>
        )}
        <span className="ml-auto truncate font-mono text-[9px] text-muted-foreground">
          {doc.title || doc.id}
        </span>
      </div>
      <p className="mt-1 line-clamp-3 text-[11px] leading-snug text-muted-foreground">
        {doc.excerpt}
      </p>
    </div>
  );
}

function StageColumn({ stage, firstIds }: { stage: TraceStage; firstIds: Set<string> }) {
  return (
    <Card className={`border-t-2 ${STAGE_ACCENT[stage.key] ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {stage.label}
          {stage.elapsed_ms !== undefined && (
            <span className="ml-auto font-mono text-[10px] font-normal text-muted-foreground">
              {stage.elapsed_ms >= 1000
                ? `${(stage.elapsed_ms / 1000).toFixed(1)}s`
                : `${stage.elapsed_ms}ms`}
            </span>
          )}
        </CardTitle>
        <p className="text-[11px] leading-snug text-muted-foreground">{stage.description}</p>
      </CardHeader>
      <CardContent className="space-y-1.5">
        {stage.docs.length === 0 ? (
          <p className="text-xs text-muted-foreground">No documents.</p>
        ) : (
          stage.docs.map((d) => (
            <DocRow key={`${stage.key}-${d.id}`} doc={d} isNew={!firstIds.has(d.id)} />
          ))
        )}
      </CardContent>
    </Card>
  );
}

export default function RetrievalPage() {
  const [query, setQuery] = useState(EXAMPLES[0]);
  const [trace, setTrace] = useState<RetrievalTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback((q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    getRetrievalTrace(q, 6)
      .then((t) => {
        setTrace(t);
        if (!t.available) setError(t.reason ?? "retrieval unavailable");
      })
      .catch((e: Error) => {
        setTrace(null);
        setError(e.message);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    run(EXAMPLES[0]);
    // Intentionally once on mount - re-running on every keystroke would hammer
    // the cross-encoder, which takes seconds per call.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stages = trace?.stages ?? [];
  const firstIds = new Set((stages[0]?.docs ?? []).map((d) => d.id));
  const totalMs = stages.reduce((sum, s) => sum + (s.elapsed_ms ?? 0), 0);
  const surfaced = trace?.summary?.surfaced_by_pipeline?.length ?? 0;
  const slowest = stages.reduce<TraceStage | null>(
    (a, b) => ((b.elapsed_ms ?? 0) > (a?.elapsed_ms ?? 0) ? b : a),
    null,
  );

  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Retrieval explorer"
        description="One query through every stage of the hybrid RAG pipeline - the C1 design, demonstrated rather than asserted."
      />

      <Card>
        <CardContent className="space-y-3 py-4">
          <div className="flex flex-wrap gap-2">
            <div className="relative min-w-[260px] flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && run(query)}
                placeholder="Ask something the advisor would retrieve for…"
                className="pl-8"
              />
            </div>
            <Button onClick={() => run(query)} disabled={loading}>
              {loading ? "Retrieving…" : "Trace retrieval"}
              {!loading && <ArrowRight className="ml-1 h-4 w-4" />}
            </Button>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => {
                  setQuery(ex);
                  run(ex);
                }}
                className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {ex.length > 46 ? `${ex.slice(0, 46)}…` : ex}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="py-4 text-sm">
            <p className="font-medium text-destructive">Retrieval unavailable</p>
            <p className="mt-1 text-muted-foreground">{error}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              The explorer needs the API running and the Chroma index built. It shows measured
              retrieval only — it will not fabricate a ranking.
            </p>
          </CardContent>
        </Card>
      )}

      {loading && (
        <p className="text-sm text-muted-foreground">
          Running the real pipeline — the cross-encoder rerank takes several seconds on CPU.
        </p>
      )}

      {stages.length > 0 && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard icon={Layers} label="Stages" value={stages.length} accent="brand" />
            <StatCard
              icon={Sparkles}
              label="Surfaced by pipeline"
              value={surfaced}
              hint="docs the first stage missed"
              accent="nepal"
            />
            <StatCard
              icon={Timer}
              label="Total retrieval"
              value={totalMs >= 1000 ? `${(totalMs / 1000).toFixed(1)}s` : `${totalMs.toFixed(0)}ms`}
              accent="regional"
            />
            <StatCard
              icon={Timer}
              label="Slowest stage"
              value={slowest?.label.split(" ")[0] ?? "—"}
              hint={
                slowest?.elapsed_ms
                  ? `${(slowest.elapsed_ms / 1000).toFixed(1)}s of the budget`
                  : undefined
              }
              accent="synthetic"
            />
          </div>

          {surfaced > 0 && (
            <Card className="border-brand/40 bg-brand/5">
              <CardContent className="py-4 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">
                  {surfaced} document{surfaced === 1 ? "" : "s"} in the final ranking
                </span>{" "}
                {surfaced === 1 ? "was" : "were"} not returned by the first stage at all — marked{" "}
                <Badge variant="secondary" className="mx-0.5 text-[10px]">
                  new
                </Badge>{" "}
                below. That gap is the argument for the hybrid: either retriever alone would have
                answered from a strictly worse set of evidence.
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {stages.map((s) => (
              <StageColumn key={s.key} stage={s} firstIds={firstIds} />
            ))}
          </div>

          <p className="text-xs text-muted-foreground">
            This calls the same Retriever and Reranker as the advising path, so the timings are the
            real latency budget rather than a benchmark. The cross-encoder dominates it, which is
            exactly why it only ever scores the shortlist instead of the corpus.
          </p>
        </>
      )}
    </div>
  );
}
