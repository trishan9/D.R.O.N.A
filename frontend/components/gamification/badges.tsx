"use client";

import {
  Compass,
  Scale,
  Search,
  Shuffle,
  Globe,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { computeBadges, type Badge as BadgeModel, type ExplorationState } from "@/lib/gamification";
import type { AdvisingResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICONS: Record<BadgeModel["icon"], LucideIcon> = {
  compass: Compass,
  scale: Scale,
  search: Search,
  shuffle: Shuffle,
  globe: Globe,
  sparkles: Sparkles,
};

interface ExplorationBadgesProps {
  exploration: ExplorationState;
  response: AdvisingResponse | null;
}

export function ExplorationBadges({ exploration, response }: ExplorationBadgesProps) {
  const badges = computeBadges(exploration, response);
  const earned = badges.filter((b) => b.earned).length;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-tier-nepal" /> Exploration badges
          </span>
          <span className="text-sm tabular-nums text-muted-foreground">{earned}/{badges.length}</span>
        </CardTitle>
        <CardDescription>
          Earned by exploring widely and checking evidence — not by committing fast.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TooltipProvider delayDuration={150}>
          <div className="grid grid-cols-3 gap-2.5">
            {badges.map((b) => {
              const Icon = ICONS[b.icon];
              return (
                <Tooltip key={b.id}>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        "flex cursor-default flex-col items-center gap-1.5 rounded-lg border p-2.5 text-center transition-colors",
                        b.earned
                          ? "border-tier-nepal/40 bg-tier-nepal/10"
                          : "border-dashed bg-muted/30 opacity-55",
                      )}
                    >
                      <Icon
                        className={cn("h-5 w-5", b.earned ? "text-tier-nepal" : "text-muted-foreground")}
                      />
                      <span className="text-[11px] font-medium leading-tight">{b.title}</span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="font-medium">{b.title}</p>
                    <p className="opacity-90">{b.description}</p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </TooltipProvider>
      </CardContent>
    </Card>
  );
}
