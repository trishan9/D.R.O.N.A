"use client";

import * as React from "react";
import { Send, Bot, User, Loader2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  "I think AI is the only field worth going into. Am I right?",
  "Everyone says I should go abroad. What are my options in Nepal?",
  "I'm good at coding so I'll definitely get a top job. What next?",
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
      year_of_study: profile.year_of_study,
      completed_modules: profile.completed_modules,
      declared_interests: profile.declared_interests,
      declared_skills: profile.declared_skills,
      self_assessed_skill_levels: profile.self_assessed_skill_levels,
      aspirations: profile.aspirations,
      aspiration_geography: profile.aspiration_geography,
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

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2 text-base">
          <Bot className="h-5 w-5 text-tier-nepal" />
          Ask D.R.O.N.A.
        </CardTitle>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-4 p-4">
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {turns.length === 0 && !busy && (
            <div className="space-y-3 py-6 text-center">
              <p className="text-sm text-muted-foreground">
                Ask about your studies, skills, or career direction. D.R.O.N.A. answers
                with multiple evidence-backed pathways — and points out where a question
                might hide a cognitive bias.
              </p>
              <div className="space-y-2">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s)}
                    className="block w-full rounded-md border bg-muted/30 px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <MessageBubble key={turn.id} turn={turn} />
          ))}

          {busy && progress && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="animate-pulse-soft">{progress}</span>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Couldn&apos;t reach the advising backend.</p>
                <p className="text-xs opacity-90">{error}</p>
                <p className="mt-1 text-xs opacity-90">
                  Is the FastAPI server running? Start it with{" "}
                  <code className="rounded bg-background px-1">python scripts/run_api.py</code>.
                </p>
              </div>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(draft);
              }
            }}
            placeholder="Type your question…  (Enter to send, Shift+Enter for newline)"
            className="resize-none"
            rows={2}
            disabled={busy}
          />
          <div className="flex justify-end">
            <Button onClick={() => send(draft)} disabled={busy || !draft.trim()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function MessageBubble({ turn }: { turn: ChatTurn }) {
  const isUser = turn.role === "user";
  return (
    <div className={cn("flex gap-2.5", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-secondary" : "bg-tier-nepal/15 text-tier-nepal",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "rounded-tr-sm bg-primary text-primary-foreground"
            : "rounded-tl-sm border bg-muted/40",
        )}
      >
        {turn.response?.refusal && (
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-destructive">
            Held back — insufficient evidence
          </span>
        )}
        <p className="whitespace-pre-wrap leading-relaxed">{turn.text}</p>
        {turn.response && !turn.response.refusal && (
          <p className="mt-1.5 text-xs text-muted-foreground">
            {turn.response.pathways.length} pathway
            {turn.response.pathways.length === 1 ? "" : "s"} below ·{" "}
            {turn.response.bias_flags.length} bias check
            {turn.response.bias_flags.length === 1 ? "" : "s"}
            {turn.response.generation_time_ms
              ? ` · ${(turn.response.generation_time_ms / 1000).toFixed(1)}s`
              : ""}
          </p>
        )}
      </div>
    </div>
  );
}
