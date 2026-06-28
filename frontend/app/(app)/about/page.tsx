import type { Metadata } from "next";
import { Bot, ShieldCheck, Cpu, Database, Brain, Boxes } from "lucide-react";

import { CONTRIBUTIONS } from "@/lib/analytics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SectionHeading } from "@/components/shared/section-heading";

export const metadata: Metadata = { title: "About" };

const STACK: { group: string; icon: typeof Cpu; items: string[] }[] = [
  { group: "Advising AI", icon: Brain, items: ["Ollama · Phi-3.5-mini (local)", "LangGraph orchestration", "Hybrid retrieval + reranker", "Rule-based bias detector"] },
  { group: "Data & retrieval", icon: Database, items: ["ChromaDB / pgvector / Pinecone", "bge-small + JobBERT-v3", "O*NET · ESCO · BLS · NLFS", "Nepal-first provenance tiers"] },
  { group: "Robotics", icon: Cpu, items: ["ROS2 Humble (WSL2)", "LeRobot ACT / Diffusion", "Gazebo Harmonic · URDF", "6-DOF gesture policies"] },
  { group: "Platform", icon: Boxes, items: ["FastAPI + WebSocket streaming", "Next.js 14 App Router", "Tailwind + shadcn/ui", "rosbridge live control"] },
];

export default function AboutPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <Card className="overflow-hidden border-brand/30">
        <CardContent className="flex flex-col gap-4 py-6 sm:flex-row sm:items-center">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-soft">
            <Bot className="h-7 w-7" />
          </span>
          <div>
            <h2 className="text-lg font-bold tracking-tight">D.R.O.N.A.</h2>
            <p className="text-sm text-muted-foreground">
              <strong>D</strong>emonstration-learned <strong>R</strong>obotic <strong>O</strong>racle for{" "}
              <strong>N</strong>urturing <strong>A</strong>spirations - an embodied, bias-aware, locally-grounded
              academic and career advising system for Nepali computing students. BSc (Hons) Computing thesis,
              Softwarica College / Coventry University.
            </p>
          </div>
        </CardContent>
      </Card>

      <section className="space-y-3">
        <SectionHeading title="Research contributions" description="Four original claims this platform supports and measures." />
        <div className="grid gap-3 sm:grid-cols-2">
          {CONTRIBUTIONS.map((c) => (
            <Card key={c.id}>
              <CardContent className="space-y-2 py-4">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand/10 text-xs font-bold text-brand">
                    {c.id}
                  </span>
                  <p className="font-semibold">{c.title}</p>
                </div>
                <p className="text-sm text-muted-foreground">{c.claim}</p>
                <p className="text-xs text-muted-foreground/80">{c.technique}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeading title="Technology" description="A fully open-source, local-first stack." />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STACK.map((s) => {
            const Icon = s.icon;
            return (
              <Card key={s.group}>
                <CardHeader className="py-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Icon className="h-4 w-4 text-brand" /> {s.group}
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  <ul className="space-y-1.5 text-xs text-muted-foreground">
                    {s.items.map((i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand" /> {i}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <Card className="border-brand/30 bg-brand/5">
        <CardContent className="flex items-start gap-3 py-5">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
          <div className="space-y-1 text-sm">
            <p className="font-semibold">Ethics &amp; data policy</p>
            <p className="text-muted-foreground">
              Zero PII is collected, stored, or transmitted. Advising runs on a local LLM only - no paid cloud APIs in
              the request path, preserving the local-only claim. Synthetic data is always labelled and never silently
              mixed with real data. Job postings are manually collected within each portal&apos;s terms of service;
              LinkedIn and ToS-restricted portals are never scraped.
            </p>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {["No PII", "Local-only LLM", "Open-source models", "ToS-compliant data"].map((t) => (
                <Badge key={t} variant="secondary">{t}</Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
