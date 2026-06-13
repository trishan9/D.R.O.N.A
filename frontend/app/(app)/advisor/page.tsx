"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Route } from "lucide-react";

import { useStore } from "@/lib/store";
import { ChatPanel } from "@/components/chat/chat-panel";
import { ProfileBuilder } from "@/components/profile/profile-builder";
import { DiversityMeter } from "@/components/gamification/diversity-meter";
import { BiasFlags } from "@/components/bias/bias-flags";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function AdvisorPage() {
  const { profile, setProfile, resetProfile, response, recordQuery, bumpExploration } = useStore();
  const lastQuery = React.useRef("");

  return (
    <div className="grid gap-4 animate-fade-in lg:grid-cols-12">
      <section className="space-y-4 lg:col-span-3">
        <ProfileBuilder profile={profile} onChange={setProfile} onReset={resetProfile} />
      </section>

      <section className="lg:col-span-6">
        <div className="flex h-[calc(100vh-9rem)] min-h-[34rem] flex-col">
          <ChatPanel
            profile={profile}
            onResponse={(r) => recordQuery(lastQuery.current, r)}
            onQuerySent={(q) => {
              lastQuery.current = q;
              bumpExploration((e) => ({ ...e, queriesAsked: e.queriesAsked + 1 }));
            }}
          />
        </div>
      </section>

      <section className="space-y-4 lg:col-span-3">
        <DiversityMeter response={response} />
        <BiasFlags flags={response?.bias_flags ?? []} />
        {response && !response.refusal && response.pathways.length > 0 && (
          <Card className="border-brand/30 bg-brand/5">
            <CardContent className="space-y-3 py-4">
              <p className="text-sm">
                <strong>{response.pathways.length}</strong> evidence-backed pathway
                {response.pathways.length === 1 ? "" : "s"} ready to explore.
              </p>
              <Button asChild size="sm" className="w-full">
                <Link href="/pathways">
                  <Route className="h-4 w-4" /> View pathways <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
