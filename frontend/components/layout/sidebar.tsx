import { ShieldCheck } from "lucide-react";

import { Brand } from "./brand";
import { SidebarNav } from "./sidebar-nav";
import { ScrollArea } from "@/components/ui/scroll-area";

/** Desktop sidebar (hidden below lg; the mobile Sheet renders the same nav). */
export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-16 items-center border-b border-sidebar-border px-5">
        <Brand />
      </div>
      <ScrollArea className="flex-1">
        <SidebarNav />
      </ScrollArea>
      <div className="border-t border-sidebar-border p-4">
        <div className="flex items-start gap-2 rounded-lg bg-accent/60 p-3 text-[11px] leading-relaxed text-accent-foreground">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Zero PII. Your profile stays on this device and advising runs on a local LLM only.
          </span>
        </div>
      </div>
    </aside>
  );
}
