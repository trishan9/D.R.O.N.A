"use client";

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

import type { AdvisingResponse, DataTier } from "@/lib/types";
import {
  BIAS_DETECTION_REFERENCE,
  RETRIEVAL_ABLATION_REFERENCE,
  keyframeJerks,
  tierDistribution,
} from "@/lib/analytics";

const TIER_VAR: Record<DataTier, string> = {
  nepal: "hsl(var(--tier-nepal))",
  regional: "hsl(var(--tier-regional))",
  international: "hsl(var(--tier-international))",
  synthetic: "hsl(var(--tier-synthetic))",
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

export function TierDonut({ response }: { response: AdvisingResponse | null }) {
  const data = tierDistribution(response).filter((d) => d.count > 0);
  if (data.length === 0) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Ask a question to populate the citation tier mix.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="label" innerRadius={55} outerRadius={90} paddingAngle={2} strokeWidth={0}>
          {data.map((d) => (
            <Cell key={d.tier} fill={TIER_VAR[d.tier]} />
          ))}
        </Pie>
        <Tooltip {...tooltipStyle} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function AblationBars() {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={RETRIEVAL_ABLATION_REFERENCE} margin={{ left: -18, right: 8, top: 8 }}>
        <XAxis dataKey="method" {...axisProps} interval={0} />
        <YAxis domain={[0, 1]} {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="ndcg5" name="NDCG@5" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
        <Bar dataKey="mrr" name="MRR" fill="hsl(var(--chart-2))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function BiasBars() {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={BIAS_DETECTION_REFERENCE} margin={{ left: -18, right: 8, top: 8 }}>
        <XAxis dataKey="bias" {...axisProps} interval={0} angle={-18} textAnchor="end" height={60} />
        <YAxis domain={[0, 1]} {...axisProps} />
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="precision" name="Precision" fill="hsl(var(--chart-1))" radius={[3, 3, 0, 0]} />
        <Bar dataKey="recall" name="Recall" fill="hsl(var(--chart-3))" radius={[3, 3, 0, 0]} />
        <Bar dataKey="f1" name="F1" fill="hsl(var(--chart-4))" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function JerkBars() {
  const data = keyframeJerks();
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ left: -10, right: 8, top: 8 }}>
        <XAxis dataKey="gesture" {...axisProps} interval={0} />
        <YAxis {...axisProps} />
        <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v} rad/s³`, "mean |jerk|"]} />
        <Bar dataKey="keyframeJerk" name="Keyframe baseline jerk" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
