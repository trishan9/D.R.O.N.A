"use client";

import Link from "next/link";
import {
  Bot,
  CircuitBoard,
  Route,
  BarChart3,
  MessageSquare,
  Trophy,
  Gauge,
  ArrowRight,
  Sparkles,
} from "lucide-react";

import { useStore } from "@/lib/store";
import { computeBadges, computeDiversity } from "@/lib/gamification";
import { StatCard } from "@/components/shared/stat-card";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CONTRIBUTIONS } from "@/lib/analytics";

const ACTIONS = [
  { href: "/advisor", icon: Bot, title: "Ask the Advisor", desc: "Bias-aware, evidence-backed pathways from a local LLM", accent: "from-brand/15 to-brand/5 text-brand" },
  { href: "/robot", icon: CircuitBoard, title: "Robot Control", desc: "Drive the 6-DOF gesture robot - sim or live ROS2", accent: "from-tier-international/15 to-tier-international/5 text-tier-international" },
  { href: "/pathways", icon: Route, title: "Explore Pathways", desc: "Compare options with citation drill-down", accent: "from-tier-regional/15 to-tier-regional/5 text-tier-regional" },
  { href: "/analytics", icon: BarChart3, title: "Analytics", desc: "Retrieval, bias, and contribution metrics", accent: "from-tier-synthetic/15 to-tier-synthetic/5 text-tier-synthetic" },
];

export default function DashboardPage() {
  const { prefs, history, exploration, response, hydrated } = useStore();
  const badges = computeBadges(exploration, response).filter((b) => b.earned).length;
  const diversity = response ? computeDiversity(response).score : null;
  const name = prefs.displayName.trim();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Hero */}
      <Card className="bg-aurora relative overflow-hidden border-brand/20">
        <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
        <CardContent className="relative z-10 flex flex-col gap-5 py-8 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-xl space-y-3">
            <Badge variant="secondary" className="gap-1">
              <Sparkles className="h-3 w-3" /> Bias-aware · locally-grounded · embodied
            </Badge>
            <h1 className="text-2xl font-bold tracking-tight text-balance sm:text-3xl">
              {hydrated && name ? (
                <>Welcome back, <span className="gradient-text">{name}</span>.</>
              ) : (
                <>Welcome to <span className="gradient-text">D.R.O.N.A.</span></>
              )}
            </h1>
            <p className="text-sm text-muted-foreground text-balance">
              Your embodied academic advisor for the Nepali computing context. Ask a question and get multiple
              evidence-backed pathways - with the cognitive biases hiding in the question surfaced, not exploited.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button asChild>
                <Link href="/advisor">
                  <Bot className="h-4 w-4" /> Ask the Advisor <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/robot">
                  <CircuitBoard className="h-4 w-4" /> Robot Control
                </Link>
              </Button>
            </div>
          </div>
          <div className="hidden shrink-0 lg:block">
            <span className="flex h-28 w-28 animate-float items-center justify-center rounded-3xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-glow">
              <Bot className="h-14 w-14" />
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Quick stats */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Questions asked" value={exploration.queriesAsked} icon={MessageSquare} accent="brand" />
        <StatCard label="Badges earned" value={`${badges}/6`} icon={Trophy} accent="regional" />
        <StatCard label="Last diversity" value={diversity ?? "-"} hint={diversity ? "0–100, higher is broader" : "ask a question"} icon={Gauge} accent="international" />
        <StatCard label="Pathways available" value={response?.pathways.length ?? 0} icon={Route} accent="synthetic" />
      </div>

      {/* Quick actions */}
      <section className="space-y-3">
        <SectionHeading title="Jump in" description="Everything the robot does, on the web." />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ACTIONS.map((a) => {
            const Icon = a.icon;
            return (
              <Link key={a.href} href={a.href} className="group">
                <Card className="card-interactive h-full">
                  <CardContent className="space-y-3 py-5">
                    <span className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-inset ring-foreground/5 ${a.accent}`}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <div>
                      <p className="flex items-center gap-1 font-semibold">
                        {a.title}
                        <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                      </p>
                      <p className="text-sm text-muted-foreground">{a.desc}</p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Recent activity */}
        <Card className="lg:col-span-2">
          <CardContent className="py-5">
            <SectionHeading
              title="Recent questions"
              action={
                <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
                  <Link href="/advisor">Ask another <ArrowRight className="h-4 w-4" /></Link>
                </Button>
              }
            />
            {history.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-8 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 text-brand">
                  <MessageSquare className="h-6 w-6" />
                </span>
                <p className="text-sm text-muted-foreground">
                  No questions yet - ask the advisor your first one to see it here.
                </p>
                <Button asChild size="sm">
                  <Link href="/advisor"><Bot className="h-4 w-4" /> Open the Advisor</Link>
                </Button>
              </div>
            ) : (
              <ul className="mt-3 divide-y">
                {history.slice(0, 5).map((h) => (
                  <li key={h.id} className="flex items-start justify-between gap-3 py-2.5">
                    <div className="min-w-0">
                      <p className="line-clamp-1 text-sm font-medium">{h.query}</p>
                      <p className="text-xs text-muted-foreground">{new Date(h.ts).toLocaleString()}</p>
                    </div>
                    <div className="flex shrink-0 gap-1.5">
                      {h.refusal ? (
                        <Badge variant="outline" className="text-[10px]">held back</Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">{h.pathwayCount} pathways</Badge>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Contributions */}
        <Card>
          <CardContent className="py-5">
            <SectionHeading title="What makes it novel" />
            <ul className="mt-3 space-y-1.5">
              {CONTRIBUTIONS.map((c, i) => {
                const accent = [
                  "text-brand bg-brand/10",
                  "text-tier-international bg-tier-international/10",
                  "text-tier-regional bg-tier-regional/10",
                  "text-tier-synthetic bg-tier-synthetic/10",
                ][i % 4];
                return (
                  <li
                    key={c.id}
                    className="flex gap-2.5 rounded-lg p-2 transition-colors hover:bg-accent/40"
                  >
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[11px] font-bold ${accent}`}>
                      {c.id}
                    </span>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{c.title}.</span> {c.claim}
                    </p>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
