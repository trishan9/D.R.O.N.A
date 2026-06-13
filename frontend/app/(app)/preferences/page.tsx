"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor, MapPin, Server, Cpu, AlertTriangle } from "lucide-react";

import { useStore } from "@/lib/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

export default function PreferencesPage() {
  const { theme, setTheme } = useTheme();
  const { profile, setProfile, prefs, setPrefs, resetAll } = useStore();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  return (
    <div className="mx-auto max-w-3xl space-y-4 animate-fade-in">
      {/* Appearance */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Appearance</CardTitle>
        </CardHeader>
        <CardContent className="pt-5">
          <Label className="mb-2 block">Theme</Label>
          <div className="grid max-w-md grid-cols-3 gap-2">
            {THEMES.map((t) => {
              const active = mounted && theme === t.value;
              const Icon = t.icon;
              return (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value)}
                  className={cn(
                    "flex flex-col items-center gap-1.5 rounded-lg border p-3 text-sm transition-colors",
                    active ? "border-brand bg-brand/5 text-foreground" : "hover:bg-accent/50",
                  )}
                >
                  <Icon className={cn("h-4 w-4", active && "text-brand")} />
                  {t.label}
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Advising defaults */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Advising defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-0.5">
              <Label className="flex items-center gap-1.5">
                <MapPin className="h-4 w-4 text-tier-nepal" /> Prioritise Nepal-local evidence
              </Label>
              <p className="text-sm text-muted-foreground">
                Boosts Nepal-tier citations first (the flagship C4 locality claim). Other tiers still appear.
              </p>
            </div>
            <Switch
              checked={profile.require_local_first}
              onCheckedChange={(v) => setProfile((p) => ({ ...p, require_local_first: v }))}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Geography target and number of pathways are set on your <strong>Profile</strong> page.
          </p>
        </CardContent>
      </Card>

      {/* Connectivity */}
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-base">Connectivity</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5 pt-5">
          <div className="space-y-1.5">
            <Label htmlFor="api" className="flex items-center gap-1.5">
              <Server className="h-4 w-4" /> Advising API URL
            </Label>
            <Input
              id="api"
              value={prefs.apiUrl}
              onChange={(e) => setPrefs({ apiUrl: e.target.value })}
              placeholder="http://localhost:8000  (default)"
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Leave blank to use the default. The advising path stays local — point this at your FastAPI server
              (<code className="font-mono">python scripts/run_api.py</code>).
            </p>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ros" className="flex items-center gap-1.5">
              <Cpu className="h-4 w-4" /> rosbridge URL (live robot)
            </Label>
            <Input
              id="ros"
              value={prefs.rosbridgeUrl}
              onChange={(e) => setPrefs({ rosbridgeUrl: e.target.value })}
              placeholder="ws://localhost:9090"
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              For the Robot Control page&apos;s live mode. Run rosbridge in WSL2 — see{" "}
              <code className="font-mono">docs/wsl_setup.md</code>.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-destructive/40">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2 text-base text-destructive">
            <AlertTriangle className="h-4 w-4" /> Data management
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
          <p className="text-sm text-muted-foreground">
            Everything is stored only in this browser. Reset clears your profile, history, progress, and preferences.
          </p>
          <Button
            variant="destructive"
            onClick={() => {
              if (confirm("Clear ALL device-local D.R.O.N.A. data?")) resetAll();
            }}
          >
            Reset all data
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
