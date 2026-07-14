"use client";

import * as React from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  AlertTriangle,
  Sparkles,
  ShieldQuestion,
  MapPin,
  Lock,
  Route,
  Clock,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { streamAdvise } from "@/lib/api";
import type { AdviseRequest, AdvisingResponse, ProfileDraft } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: AdvisingResponse;
}

interface ChatPanelProps {
  profile: ProfileDraft;
  onResponse: (response: AdvisingResponse) => void;
  /** Fired when a query is submitted; receives the query text (for history). */
  onQuerySent: (query: string) => void;
}

const SUGGESTED = [
  { icon: Sparkles, text: "I think AI is the only field worth going into. Am I right?" },
  { icon: MapPin, text: "Everyone says I should go abroad. What are my options in Nepal?" },
  { icon: ShieldQuestion, text: "I'm good at coding so I'll definitely get a top job. What next?" },
];

export function ChatPanel({ profile, onResponse, onQuerySent }: ChatPanelProps) {
  const [turns, setTurns] = React.useState<ChatTurn[]>([]);
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [progress, setProgress] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const cancelRef = React.useRef<(() => void) | null>(null);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, progress]);

  React.useEffect(() => () => cancelRef.current?.(), []);

  const send = (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setError(null);
    setBusy(true);
    setProgress("Connecting to D.R.O.N.A…");
    onQuerySent(q);

    const userTurn: ChatTurn = { id: crypto.randomUUID(), role: "user", text: q };
    const assistantId = crypto.randomUUID();
    setTurns((t) => [...t, userTurn]);
    setDraft("");

    const req: AdviseRequest = {
      query_text: q,
      session_id: profile.session_id,
      programme: profile.programme,
      year_of_study: profile.year_of_study,
      completed_modules: profile.completed_modules,
      declared_interests: profile.declared_interests,
      declared_skills: profile.declared_skills,
      self_assessed_skill_levels: profile.self_assessed_skill_levels,
      aspirations: profile.aspirations,
      aspiration_geography: profile.aspiration_geography,
      goal: profile.goal,
      target_institutions: profile.target_institutions,
      timeline_years: profile.timeline_years,
      max_pathways: profile.max_pathways,
      require_local_first: profile.require_local_first,
    };

    cancelRef.current = streamAdvise(req, {
      onNode: (_node, label) => setProgress(label),
      onResult: (response) => {
        setTurns((t) => [
          ...t,
          {
            id: assistantId,
            role: "assistant",
            text: response.refusal ? response.refusal_reason || "I can't answer that confidently." : response.summary,
            response,
          },
        ]);
        onResponse(response);
        setBusy(false);
        setProgress(null);
      },
      onError: (detail) => {
        setError(detail);
        setBusy(false);
        setProgress(null);
      },
    });
  };

  const empty = turns.length === 0 && !busy;

  return (
    <Card className="flex h-full flex-col overflow-hidden shadow-card">
      {/* Header */}
      <div className="flex items-center gap-3 border-b bg-gradient-to-r from-brand/5 via-transparent to-transparent px-4 py-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-soft">
          <Bot className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold leading-tight">Ask D.R.O.N.A.</p>
          <p className="flex items-center gap-1.5 truncate text-xs text-muted-foreground">
            <span className={cn("pulse-dot", busy ? "text-warning" : "text-success")} />
            {busy ? "Thinking…" : "Bias-aware · evidence-backed · local LLM"}
          </p>
        </div>
        <span className="ml-auto flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
          <Lock className="h-3 w-3 text-success" /> On-device
        </span>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-5">
        {empty && (
          <div className="flex h-full flex-col justify-center">
            <div className="mx-auto max-w-md text-center">
              <span className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-card">
                <Bot className="h-7 w-7" />
              </span>
              <h3 className="text-base font-semibold">What would you like to explore?</h3>
              <p className="mt-1 text-sm text-muted-foreground text-balance">
                Ask about your studies, skills, or career direction. You&apos;ll get several
                evidence-backed pathways - and a heads-up where a question hides a cognitive bias.
              </p>
            </div>
            <div className="mx-auto mt-5 w-full max-w-md space-y-2">
              <p className="px-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Try one of these
              </p>
              {SUGGESTED.map((s) => {
                const Icon = s.icon;
                return (
                  <button
                    key={s.text}
                    onClick={() => send(s.text)}
                    className="group flex w-full items-center gap-3 rounded-xl border bg-card px-3.5 py-3 text-left text-sm shadow-soft transition-all hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-card"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="flex-1">{s.text}</span>
                    <Send className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {turns.map((turn) => (
          <MessageBubble key={turn.id} turn={turn} />
        ))}

        {busy && progress && (
          <div className="flex gap-2.5 animate-fade-in">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand/15 text-brand">
              <Bot className="h-4 w-4 animate-pulse" />
            </span>
            <div className="flex items-center gap-2.5 rounded-2xl rounded-tl-sm border bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground">
              <span className="flex items-end gap-1" aria-hidden>
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand" />
              </span>
              <span>{progress}</span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Couldn&apos;t reach the advising backend.</p>
              <p className="text-xs opacity-90">{error}</p>
              <p className="mt-1 text-xs opacity-90">
                Is the FastAPI server running? Start it with{" "}
                <code className="rounded bg-background px-1 font-mono">python scripts/run_api.py</code>.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t bg-muted/30 p-3">
        <div className="flex items-end gap-2 rounded-xl border bg-background p-2 shadow-soft focus-within:border-brand/50 focus-within:ring-2 focus-within:ring-brand/20">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(draft);
              }
            }}
            placeholder="Type your question…  (Enter to send, Shift+Enter for a new line)"
            className="max-h-40 min-h-[2.5rem] resize-none border-0 bg-transparent px-2 py-1.5 shadow-none focus-visible:ring-0"
            rows={1}
            disabled={busy}
          />
          <Button size="icon" className="h-9 w-9 shrink-0 rounded-lg" onClick={() => send(draft)} disabled={busy || !draft.trim()}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex gap-2.5 animate-fade-in", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-secondary text-secondary-foreground" : "bg-brand/15 text-brand",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[82%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "rounded-tr-sm bg-primary text-primary-foreground"
            : "rounded-tl-sm border bg-card shadow-soft",
        )}
      >
        {turn.response?.refusal && (
          <span className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-destructive">
            <ShieldQuestion className="h-3.5 w-3.5" /> Held back - insufficient evidence
          </span>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{turn.text}</p>
        {turn.response && !turn.response.refusal && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="chip">
              <Route className="h-3 w-3 text-brand" />
              {turn.response.pathways.length} pathway{turn.response.pathways.length === 1 ? "" : "s"}
            </span>
            <span className="chip">
              <ShieldQuestion className="h-3 w-3 text-brand" />
              {turn.response.bias_flags.length} bias check{turn.response.bias_flags.length === 1 ? "" : "s"}
            </span>
            {turn.response.generation_time_ms ? (
              <span className="chip">
                <Clock className="h-3 w-3 text-brand" />
                {(turn.response.generation_time_ms / 1000).toFixed(1)}s
              </span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
