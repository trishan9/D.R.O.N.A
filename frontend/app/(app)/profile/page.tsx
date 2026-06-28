"use client";

import { ShieldCheck, History, Trash2 } from "lucide-react";

import { useStore } from "@/lib/store";
import { ProfileBuilder } from "@/components/profile/profile-builder";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ProfilePage() {
  const { profile, setProfile, resetProfile, prefs, setPrefs, history, clearHistory } = useStore();
  const name = prefs.displayName.trim();
  const init = name ? name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase() : "You";

  return (
    <div className="grid gap-4 animate-fade-in lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-base">Your identity (device-local)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-4 pt-5">
            <Avatar className="h-16 w-16 border">
              <AvatarFallback className="bg-gradient-to-br from-brand/15 to-tier-international/15 text-lg font-bold text-brand">
                {init}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-[14rem] flex-1 space-y-1.5">
              <Label htmlFor="nickname">Display name (optional)</Label>
              <Input
                id="nickname"
                value={prefs.displayName}
                onChange={(e) => setPrefs({ displayName: e.target.value })}
                placeholder="A nickname for this device - not your real name"
                maxLength={40}
              />
              <p className="text-xs text-muted-foreground">
                Just a label for this browser. Never transmitted, never used to identify you.
              </p>
            </div>
          </CardContent>
        </Card>

        <ProfileBuilder profile={profile} onChange={setProfile} onReset={resetProfile} />
      </div>

      <div className="space-y-4">
        <Card className="border-brand/30 bg-brand/5">
          <CardContent className="flex items-start gap-3 py-4">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand" />
            <div className="space-y-1 text-sm">
              <p className="font-semibold">Privacy by design</p>
              <p className="text-muted-foreground">
                Zero PII. Your profile lives only in this browser&apos;s storage and is sent only as a
                PII-free request when you ask a question. Clear it any time below.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b py-3">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <History className="h-4 w-4" /> Question history
            </CardTitle>
            {history.length > 0 && (
              <Button variant="ghost" size="sm" className="h-7 text-xs text-muted-foreground" onClick={clearHistory}>
                <Trash2 className="h-3.5 w-3.5" /> Clear
              </Button>
            )}
          </CardHeader>
          <CardContent className="pt-4">
            {history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No questions asked yet this session.</p>
            ) : (
              <ul className="space-y-3">
                {history.map((h) => (
                  <li key={h.id} className="text-sm">
                    <p className="line-clamp-2 font-medium">{h.query}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(h.ts).toLocaleString()} · {h.pathwayCount} pathways
                      {h.refusal ? " · held back" : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
