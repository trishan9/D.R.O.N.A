import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: LucideIcon;
  accent?: "brand" | "nepal" | "international" | "regional" | "synthetic" | "muted";
  className?: string;
}

const ACCENTS: Record<NonNullable<StatCardProps["accent"]>, string> = {
  brand: "text-brand bg-brand/10",
  nepal: "text-tier-nepal bg-tier-nepal/10",
  international: "text-tier-international bg-tier-international/10",
  regional: "text-tier-regional bg-tier-regional/10",
  synthetic: "text-tier-synthetic bg-tier-synthetic/10",
  muted: "text-muted-foreground bg-muted",
};

export function StatCard({ label, value, hint, icon: Icon, accent = "brand", className }: StatCardProps) {
  return (
    <Card className={cn("flex items-center gap-4 p-4 shadow-soft", className)}>
      {Icon && (
        <span className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-xl", ACCENTS[accent])}>
          <Icon className="h-5 w-5" />
        </span>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="truncate text-2xl font-bold leading-tight tracking-tight">{value}</p>
        {hint && <p className="truncate text-xs text-muted-foreground">{hint}</p>}
      </div>
    </Card>
  );
}
