"use client";

import { DecisionTrace } from "@/components/reasoning/decision-trace";
import { SectionHeading } from "@/components/shared/section-heading";
import { useStore } from "@/lib/store";

export default function ReasoningPage() {
  const { response, profile, history } = useStore();
  const lastQuestion = history?.[0]?.query;

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeading
        title="AI reasoning trace"
        description="Why D.R.O.N.A. gave that answer - the student context it had, the cognitive bias it found, the evidence it retrieved, and how those produced the ranked pathways. Every value is read from the actual response, not a reconstruction."
      />
      <DecisionTrace response={response} profile={profile} question={lastQuestion} />
    </div>
  );
}
