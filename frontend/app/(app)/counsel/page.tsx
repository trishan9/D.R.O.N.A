"use client";

/**
 * Voice counselling session - talk to the advisor in the browser.
 *
 * The robot speaks through speech_node inside WSL, which a student on their own
 * laptop cannot reach. This gives the same counselling loop - speak, retrieve,
 * debias, advise, speak back - using only the browser's Web Speech API: no key,
 * no network service, no install.
 *
 * Language routing is the same rule the backend uses (see lib/language.ts):
 * Devanagari OR Romanised-Nepali markers route to Nepali. That matters here
 * because students speak code-switched Nepali, and the transcript comes back in
 * Latin script - so the Romanised detector, not the script test, is what catches
 * "malai data science ramro lagcha".
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Ear,
  Loader2,
  Mic,
  MicOff,
  Send,
  ShieldAlert,
  Volume2,
  VolumeX,
} from "lucide-react";

import { advise } from "@/lib/api";
import type { AdviseRequest, AdvisingResponse } from "@/lib/types";
import { useStore } from "@/lib/store";
import { detectLanguage, romanNepaliMarkers, LANGUAGE_LABEL } from "@/lib/language";
import {
  listen,
  recognitionLang,
  speak,
  speechSupport,
  stopSpeaking,
  type SpeechSupport,
} from "@/lib/speech";
import { SectionHeading } from "@/components/shared/section-heading";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EvidenceKindBadge, EvidenceSpan } from "@/components/bias/evidence-span";

interface Turn {
  id: string;
  role: "student" | "counsellor";
  text: string;
  lang?: "en" | "ne";
  response?: AdvisingResponse;
}

const OPENERS = [
  "malai data science ramro lagcha, kun module ramro cha?",
  "Which modules prepare me for data engineering?",
  "मलाई डेटा साइन्समा जान मन छ, कहाँबाट सुरु गरौं?",
  "mero career kasari banaune?",
];

export default function CounselPage() {
  const { profile, recordQuery } = useStore();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [partial, setPartial] = useState("");
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [support, setSupport] = useState<SpeechSupport | null>(null);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const stopListenRef = useRef<(() => void) | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Voices load asynchronously in Chromium; probing once on mount can report an
  // empty list, so re-probe when the browser fires voiceschanged.
  useEffect(() => {
    const probe = () => setSupport(speechSupport());
    probe();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.addEventListener("voiceschanged", probe);
      return () => window.speechSynthesis.removeEventListener("voiceschanged", probe);
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, partial]);

  useEffect(() => () => stopSpeaking(), []);

  const ask = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || busy) return;
      const lang = detectLanguage(q);

      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "student", text: q, lang },
      ]);
      setDraft("");
      setPartial("");
      setBusy(true);
      setError(null);

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

      try {
        const response = await advise(req);
        setTurns((t) => [
          ...t,
          {
            id: crypto.randomUUID(),
            role: "counsellor",
            text: response.summary,
            lang,
            response,
          },
        ]);
        recordQuery(q, response);
        if (autoSpeak) {
          // speak_text is written for the robot's voice - shorter and without
          // citation markup - so it is what should be read aloud.
          setSpeaking(true);
          speak(response.speak_text || response.summary, lang, () => setSpeaking(false));
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [busy, profile, recordQuery, autoSpeak],
  );

  const toggleMic = useCallback(() => {
    if (listening) {
      stopListenRef.current?.();
      stopListenRef.current = null;
      setListening(false);
      return;
    }
    setError(null);
    stopSpeaking();
    const stop = listen({
      lang: recognitionLang("auto"),
      onPartial: setPartial,
      onFinal: (text) => void ask(text),
      onError: (err) =>
        setError(
          err === "not-allowed"
            ? "Microphone permission denied. Allow mic access, or type instead."
            : `Speech recognition: ${err}`,
        ),
      onEnd: () => {
        setListening(false);
        setPartial("");
      },
    });
    if (!stop) {
      setError("This browser has no speech recognition. Chrome or Edge supports it; typing works everywhere.");
      return;
    }
    stopListenRef.current = stop;
    setListening(true);
  }, [listening, ask]);

  const draftLang = draft.trim() ? detectLanguage(draft) : null;
  const draftMarkers = draft.trim() ? romanNepaliMarkers(draft) : [];

  return (
    <div className="flex flex-col gap-5">
      <SectionHeading
        title="Counselling session"
        description="Speak or type - in English, Nepali, or a mix. The advisor answers in the language you used."
      />

      {support && !support.recognition && (
        <Card className="border-amber-500/40 bg-amber-500/5">
          <CardContent className="flex gap-3 py-3 text-sm">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <p className="text-muted-foreground">
              This browser cannot do speech recognition (it is Chromium-only — Chrome or Edge).
              Typing works everywhere, and replies are still spoken aloud
              {support.synthesis ? "" : " — though this browser cannot speak either"}.
            </p>
          </CardContent>
        </Card>
      )}

      {support?.synthesis && !support.hasNepaliVoice && (
        <Card className="border-border">
          <CardContent className="py-3 text-xs text-muted-foreground">
            No Nepali (<code>ne-NP</code>) voice is installed on this system, so Nepali replies are
            read by the closest available voice. The text is always correct; only the accent is
            approximate.
          </CardContent>
        </Card>
      )}

      {/* Conversation */}
      <Card className="min-h-[320px]">
        <CardContent className="space-y-3 py-4">
          {turns.length === 0 && !partial && (
            <div className="py-6 text-center">
              <Ear className="mx-auto mb-3 h-8 w-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">
                Tap the mic and talk, or pick an opener:
              </p>
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {OPENERS.map((o) => (
                  <button
                    key={o}
                    onClick={() => void ask(o)}
                    className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {o}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((t) => (
            <div
              key={t.id}
              className={`flex ${t.role === "student" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-lg px-3 py-2 ${
                  t.role === "student"
                    ? "bg-brand/10 text-foreground"
                    : "border border-border bg-card"
                }`}
              >
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {t.role === "student" ? "You" : "D.R.O.N.A."}
                  </span>
                  {t.lang && (
                    <Badge variant="outline" className="px-1 py-0 text-[9px]">
                      {LANGUAGE_LABEL[t.lang]}
                    </Badge>
                  )}
                </div>
                <p className="text-sm leading-relaxed">{t.text}</p>

                {t.response && t.response.bias_flags.length > 0 && (
                  <div className="mt-2 space-y-1.5 rounded border border-amber-500/30 bg-amber-500/5 p-2">
                    <p className="flex items-center gap-1 text-[10px] font-medium text-amber-700">
                      <ShieldAlert className="h-3 w-3" />
                      Thinking pattern noticed — not a judgement, just worth seeing
                    </p>
                    {t.response.bias_flags.map((b, i) => (
                      <div key={i} className="text-[11px]">
                        <div className="flex flex-wrap items-center gap-1">
                          <Badge variant="secondary" className="text-[9px]">
                            {b.bias_type.replace(/_/g, " ")}
                          </Badge>
                          <EvidenceKindBadge signal={b.detected_signal} />
                        </div>
                        <p className="mt-0.5 leading-snug text-muted-foreground">
                          <EvidenceSpan signal={b.detected_signal} queryText={t.text} />
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {t.response && t.response.pathways.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {t.response.pathways.map((p, i) => (
                      <div key={i} className="rounded border border-border/60 p-2 text-[11px]">
                        <div className="flex items-start gap-1.5">
                          <p className="font-medium">{p.pathway_title}</p>
                          <Badge variant="outline" className="ml-auto shrink-0 text-[9px]">
                            {p.confidence}
                          </Badge>
                        </div>
                        <p className="mt-0.5 leading-snug text-muted-foreground">{p.rationale}</p>
                        {p.matched_softwarica_modules.length > 0 && (
                          <p className="mt-1 text-[10px] text-muted-foreground">
                            Modules: {p.matched_softwarica_modules.slice(0, 4).join(", ")}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {partial && (
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-lg border border-dashed border-brand/40 px-3 py-2">
                <p className="text-sm italic text-muted-foreground">{partial}</p>
              </div>
            </div>
          )}

          {busy && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Retrieving curriculum, checking for bias, composing advice…
            </div>
          )}

          <div ref={bottomRef} />
        </CardContent>
      </Card>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Controls */}
      <Card>
        <CardContent className="space-y-2 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={toggleMic}
              variant={listening ? "destructive" : "default"}
              disabled={busy || (support ? !support.recognition : false)}
              className="gap-1.5"
            >
              {listening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
              {listening ? "Stop" : "Speak"}
            </Button>

            <Input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void ask(draft)}
              placeholder="…or type in English, Nepali, or a mix"
              className="min-w-[200px] flex-1"
              disabled={busy}
            />
            <Button onClick={() => void ask(draft)} disabled={busy || !draft.trim()} size="icon">
              <Send className="h-4 w-4" />
            </Button>

            <Button
              variant="outline"
              size="icon"
              title={autoSpeak ? "Replies are spoken aloud" : "Replies are silent"}
              onClick={() => {
                if (autoSpeak) stopSpeaking();
                setAutoSpeak((v) => !v);
              }}
            >
              {autoSpeak ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </Button>
          </div>

          {draftLang && (
            <p className="text-[11px] text-muted-foreground">
              Detected <span className="font-medium text-foreground">{LANGUAGE_LABEL[draftLang]}</span>
              {draftMarkers.length > 0 && (
                <> — Romanised Nepali markers: {draftMarkers.slice(0, 6).join(", ")}</>
              )}
              . The reply will use this language.
            </p>
          )}
          {speaking && (
            <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Volume2 className="h-3 w-3" /> speaking…
              <button onClick={() => { stopSpeaking(); setSpeaking(false); }} className="underline">
                stop
              </button>
            </p>
          )}
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        Speech is processed by your browser. Nothing is recorded or stored, and the session carries
        no identity — the advising request is the same session-scoped, PII-free payload the robot
        sends.
      </p>
    </div>
  );
}
