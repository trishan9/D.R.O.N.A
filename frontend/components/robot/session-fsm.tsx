import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export const SESSION_STATES = [
  { id: "IDLE", label: "Idle", blurb: "Waiting for a student" },
  { id: "GREETING", label: "Greeting", blurb: "Greet gesture" },
  { id: "NEEDS_ASSESSMENT", label: "Assess", blurb: "Listen + understand" },
  { id: "ADVISING", label: "Advise", blurb: "Retrieve + respond" },
  { id: "CLOSURE", label: "Close", blurb: "Farewell gesture" },
] as const;

export type SessionStateId = (typeof SESSION_STATES)[number]["id"];

export function SessionFsm({ current }: { current: SessionStateId }) {
  const idx = SESSION_STATES.findIndex((s) => s.id === current);
  return (
    <ol className="flex items-stretch gap-1">
      {SESSION_STATES.map((s, i) => {
        const done = i < idx;
        const active = i === idx;
        return (
          <li key={s.id} className="flex flex-1 flex-col items-center text-center">
            <div className="flex w-full items-center">
              <span className={cn("h-0.5 flex-1", i === 0 ? "opacity-0" : done || active ? "bg-brand" : "bg-border")} />
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold transition-colors",
                  active && "border-brand bg-brand text-brand-foreground shadow-soft",
                  done && "border-brand bg-brand/15 text-brand",
                  !active && !done && "border-border bg-background text-muted-foreground",
                )}
              >
                {done ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span
                className={cn(
                  "h-0.5 flex-1",
                  i === SESSION_STATES.length - 1 ? "opacity-0" : done ? "bg-brand" : "bg-border",
                )}
              />
            </div>
            <span className={cn("mt-1.5 text-xs font-medium", active ? "text-foreground" : "text-muted-foreground")}>
              {s.label}
            </span>
            <span className="hidden text-[10px] text-muted-foreground sm:block">{s.blurb}</span>
          </li>
        );
      })}
    </ol>
  );
}
