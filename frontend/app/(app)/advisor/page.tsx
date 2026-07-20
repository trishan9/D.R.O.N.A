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
  const { profile, setProfile, resetProfile, response, recordQuery, bumpExploration, history } =
    useStore();
  const lastQuery = React.useRef("");

  return (
    <div className="grid gap-4 animate-fade-in lg:grid-cols-12">
      {/* Chat - hero. First on mobile, centre on desktop. */}
      <section className="order-1 lg:order-2 lg:col-span-6">
        <div className="flex h-[70vh] min-h-[30rem] flex-col lg:h-[calc(100vh-8.5rem)]">
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

      {/* Profile - left rail on desktop, second on mobile. */}
      <section className="order-3 space-y-4 lg:order-1 lg:col-span-3">
        <ProfileBuilder profile={profile} onChange={setProfile} onReset={resetProfile} />
      </section>

      {/* Live insights - right rail. */}
      <section className="order-2 space-y-4 lg:order-3 lg:col-span-3">
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
        <DiversityMeter response={response} />
        <BiasFlags flags={response?.bias_flags ?? []} queryText={history?.[0]?.query} />
        {!response && (
          <Card className="border-dashed">
            <CardContent className="py-6 text-center text-sm text-muted-foreground">
              Your evidence-diversity meter and bias checks appear here after you ask a question.
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}
