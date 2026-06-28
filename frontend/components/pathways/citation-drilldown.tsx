"use client";

import * as React from "react";
import { ChevronDown, Quote } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { TIER_META } from "@/lib/gamification";
import type { RetrievalCitation } from "@/lib/types";
import { cn } from "@/lib/utils";

interface CitationDrilldownProps {
  citations: RetrievalCitation[];
  onOpen?: () => void;
}

export function CitationDrilldown({ citations, onOpen }: CitationDrilldownProps) {
  const [open, setOpen] = React.useState(false);

  if (citations.length === 0) {
    return (
      <p className="text-xs italic text-muted-foreground">
        No citations attached - treat this with caution.
      </p>
    );
  }

  const toggle = () => {
    setOpen((o) => {
      if (!o) onOpen?.();
      return !o;
    });
  };

  return (
    <div className="rounded-md border bg-muted/20">
      <button
        onClick={toggle}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium"
      >
        <span className="flex items-center gap-1.5">
          <Quote className="h-3.5 w-3.5" />
          {citations.length} citation{citations.length === 1 ? "" : "s"} - see the evidence
        </span>
        <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="space-y-2 border-t px-3 py-2.5">
          {citations.map((c, i) => {
            const meta = TIER_META[c.tier];
            return (
              <li key={`${c.source_id}-${i}`} className="space-y-1 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className={cn("gap-1", meta.className)}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
                    {meta.label}
                  </Badge>
                  <span className="text-muted-foreground">{c.source_type.replace("_", " ")}</span>
                  <span className="ml-auto tabular-nums text-muted-foreground">
                    {(c.relevance_score * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="border-l-2 border-border pl-2 italic text-muted-foreground">
                  &ldquo;{c.excerpt}&rdquo;
                </p>
                <p className="text-[10px] text-muted-foreground/70">{c.source_id}</p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
