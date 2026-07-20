"use client";

/**
 * Charts for the C2b bias-detector comparison.
 *
 * These render a result that is deliberately awkward: the design with the best
 * F1 is NOT the one that ships. Every chart here therefore carries the
 * false-positive count alongside the quality metric, because that column is what
 * the shipping decision actually turned on.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import type { DetectorRow, HeldoutRow, LatencyStage } from "@/lib/api";

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

/** Compact detector label - the full names carry parenthetical detail. */
export function shortName(name: string): string {
  return name
    .replace(" [PRODUCTION]", "")
    .replace("hybrid (rules ∪ ", "rules ∪ ")
    .replace("(kNN, thr=0.55)", "kNN")
    .replace("(few-shot, NO grounding)", "few-shot")
    .replace("(few-shot + grounding)", "few-shot + span")
    .replace("(zero-shot)", "zero-shot")
    .replace("(regex)", "")
    .replace(/\)$/, "")
    .trim();
}

/**
 * Grouped P/R/F1 per detector. Rows that falsely flagged neutral questions are
 * drawn at reduced opacity - a high bar that cries wolf is not a good result.
 */
export function DetectorComparisonBars({ rows }: { rows: DetectorRow[] }) {
  const data = rows.map((r) => ({
    name: shortName(r.detector),
    precision: r.precision,
    recall: r.recall,
    f1: r.f1,
    clean: r.false_positives === 0,
    shipped: r.shipped,
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 46)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }} barGap={2}>
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, 1]} {...axisProps} />
        <YAxis type="category" dataKey="name" width={132} {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="precision" fill="hsl(var(--tier-nepal))" radius={[0, 3, 3, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fillOpacity={d.clean ? 1 : 0.4} />
          ))}
        </Bar>
        <Bar dataKey="recall" fill="hsl(var(--tier-regional))" radius={[0, 3, 3, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fillOpacity={d.clean ? 1 : 0.4} />
          ))}
        </Bar>
        <Bar dataKey="f1" fill="hsl(var(--brand))" radius={[0, 3, 3, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fillOpacity={d.clean ? 1 : 0.4} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * The trade-off itself: precision against recall, one point per design.
 *
 * This is the chart that justifies the shipping decision. The regex baseline sits
 * at the top-left (perfect precision, poor recall); the zero-shot LLM sits at the
 * bottom-right (finds everything, trusts nothing). The shipped detector is the
 * point that moved right without falling off the top.
 */
export function PrecisionRecallScatter({ rows }: { rows: DetectorRow[] }) {
  const clean = rows
    .filter((r) => r.false_positives === 0 && !r.shipped)
    .map((r) => ({ ...r, name: shortName(r.detector), z: 100 }));
  const dirty = rows
    .filter((r) => r.false_positives > 0)
    .map((r) => ({ ...r, name: shortName(r.detector), z: 100 }));
  const shipped = rows
    .filter((r) => r.shipped)
    .map((r) => ({ ...r, name: shortName(r.detector), z: 260 }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ScatterChart margin={{ top: 12, right: 24, bottom: 20, left: 0 }}>
        <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" />
        <XAxis
          type="number"
          dataKey="recall"
          name="Recall"
          domain={[0, 1]}
          label={{ value: "Recall →", position: "insideBottom", offset: -12, fontSize: 11 }}
          {...axisProps}
        />
        <YAxis
          type="number"
          dataKey="precision"
          name="Precision"
          domain={[0, 1]}
          label={{ value: "Precision →", angle: -90, position: "insideLeft", fontSize: 11 }}
          {...axisProps}
        />
        <ZAxis type="number" dataKey="z" range={[80, 300]} />
        <ReferenceLine
          y={1}
          stroke="hsl(var(--tier-nepal))"
          strokeDasharray="4 4"
          label={{ value: "never false-accuses", fontSize: 10, position: "insideTopRight" }}
        />
        <Tooltip
          {...tooltipStyle}
          formatter={(v: number | string, key: string) =>
            typeof v === "number" ? [v.toFixed(3), key] : [v, key]
          }
          labelFormatter={() => ""}
          content={({ payload }) => {
            const p = payload?.[0]?.payload as (DetectorRow & { name: string }) | undefined;
            if (!p) return null;
            return (
              <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
                <p className="font-semibold">{p.name}</p>
                <p>precision {p.precision.toFixed(3)}</p>
                <p>recall {p.recall.toFixed(3)}</p>
                <p>F1 {p.f1.toFixed(3)}</p>
                <p className={p.false_positives ? "text-destructive" : "text-tier-nepal"}>
                  {p.false_positives}/{p.n_neutral} neutral questions falsely flagged
                </p>
              </div>
            );
          }}
        />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Scatter name="No false positives" data={clean} fill="hsl(var(--tier-regional))" />
        <Scatter name="Falsely flags neutrals" data={dirty} fill="hsl(var(--destructive))" />
        <Scatter name="Shipped" data={shipped} fill="hsl(var(--brand))" shape="star" />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

/**
 * False positives on the neutral controls.
 *
 * The single most important chart on the page: a detector that flags every
 * neutral question has "found" every bias while being useless, and two of the
 * three false positives from the runner-up design were Nepali questions.
 */
export function FalsePositiveBars({ rows }: { rows: DetectorRow[] }) {
  const data = rows.map((r) => ({
    name: shortName(r.detector),
    falsePositives: r.false_positives,
    shipped: r.shipped,
  }));
  const nNeutral = rows[0]?.n_neutral ?? 8;

  return (
    <ResponsiveContainer width="100%" height={Math.max(240, data.length * 40)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 32 }}>
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, nNeutral]} allowDecimals={false} {...axisProps} />
        <YAxis type="category" dataKey="name" width={132} {...axisProps} />
        <Tooltip
          {...tooltipStyle}
          formatter={(v: number) => [`${v} of ${nNeutral} neutral questions`, "Falsely flagged"]}
        />
        <Bar dataKey="falsePositives" radius={[0, 3, 3, 0]}>
          <LabelList dataKey="falsePositives" position="right" fontSize={11} />
          {data.map((d, i) => (
            <Cell
              key={i}
              fill={
                d.falsePositives === 0
                  ? "hsl(var(--tier-nepal))"
                  : d.falsePositives >= nNeutral
                    ? "hsl(var(--destructive))"
                    : "hsl(var(--tier-synthetic))"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/**
 * Tuned-set vs unseen-set performance - the generalisation gap.
 *
 * v1 reads 1.000 across the board because the detector was tuned against it.
 * Showing it next to v2 is the point: the pair is honest where either number
 * alone would be misleading.
 */
export function GeneralisationGapBars({ rows }: { rows: HeldoutRow[] }) {
  const data = rows.map((r) => ({
    name: r.set,
    precision: r.precision,
    recall: r.recall,
    f1: r.f1,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: 0, right: 8 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
        <XAxis dataKey="name" {...axisProps} />
        <YAxis domain={[0, 1]} {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="precision" fill="hsl(var(--tier-nepal))" radius={[3, 3, 0, 0]} />
        <Bar dataKey="recall" fill="hsl(var(--tier-regional))" radius={[3, 3, 0, 0]} />
        <Bar dataKey="f1" fill="hsl(var(--brand))" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Measured per-stage robot reaction latency (median / p95 / max). */
export function LatencyStageBars({ stages }: { stages: LatencyStage[] }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, stages.length * 58)}>
      <BarChart data={stages} layout="vertical" margin={{ left: 8, right: 28 }} barGap={2}>
        <CartesianGrid horizontal={false} stroke="hsl(var(--border))" strokeDasharray="3 3" />
        <XAxis type="number" unit="ms" {...axisProps} />
        <YAxis type="category" dataKey="stage" width={140} {...axisProps} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v} ms`, ""]} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="median_ms" name="median" fill="hsl(var(--tier-nepal))" radius={[0, 3, 3, 0]} />
        <Bar dataKey="p95_ms" name="p95" fill="hsl(var(--tier-regional))" radius={[0, 3, 3, 0]} />
        <Bar dataKey="max_ms" name="max" fill="hsl(var(--tier-synthetic))" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
