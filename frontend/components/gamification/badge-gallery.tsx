"use client";

import {
  Compass,
  Scale,
  Search,
  Shuffle,
  Globe,
  Sparkles,
  Download,
  Lock,
  type LucideIcon,
} from "lucide-react";

import type { Badge as BadgeModel } from "@/lib/gamification";
import { badgeEmblemSvg } from "@/lib/certificate";
import { downloadPng, slug } from "@/lib/download";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ICONS: Record<BadgeModel["icon"], LucideIcon> = {
  compass: Compass,
  scale: Scale,
  search: Search,
  shuffle: Shuffle,
  globe: Globe,
  sparkles: Sparkles,
};

export function BadgeGallery({ badges }: { badges: BadgeModel[] }) {
  const earned = badges.filter((b) => b.earned).length;
  const download = (b: BadgeModel) =>
    downloadPng(badgeEmblemSvg(b.title, b.description, b.earned), `${slug(b.title)}-badge.png`, 2);

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0 border-b py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Sparkles className="h-4 w-4 text-brand" /> Exploration badges
        </CardTitle>
        <span className="text-xs tabular-nums text-muted-foreground">{earned}/{badges.length} earned</span>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 pt-4 sm:grid-cols-3">
        {badges.map((b) => {
          const Icon = ICONS[b.icon];
          return (
            <div
              key={b.id}
              className={cn(
                "group flex flex-col items-center gap-2 rounded-xl border p-4 text-center transition-all",
                b.earned
                  ? "border-brand/40 bg-brand/5 hover:-translate-y-0.5 hover:shadow-card"
                  : "opacity-60",
              )}
            >
              <span
                className={cn(
                  "flex h-14 w-14 items-center justify-center rounded-full ring-1 ring-inset ring-foreground/5",
                  b.earned
                    ? "bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-soft"
                    : "bg-muted text-muted-foreground",
                )}
              >
                {b.earned ? <Icon className="h-6 w-6" /> : <Lock className="h-5 w-5" />}
              </span>
              <div>
                <p className="text-sm font-semibold">{b.title}</p>
                <p className="text-[11px] leading-tight text-muted-foreground">{b.description}</p>
              </div>
              {b.earned ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-xs text-muted-foreground hover:text-brand"
                  onClick={() => download(b)}
                >
                  <Download className="h-3.5 w-3.5" /> Download
                </Button>
              ) : (
                <span className="h-7 text-[11px] leading-7 text-muted-foreground">Locked</span>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
