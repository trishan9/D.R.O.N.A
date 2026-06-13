import Link from "next/link";
import { Bot } from "lucide-react";

import { cn } from "@/lib/utils";

export function Brand({ className, href = "/" }: { className?: string; href?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5", className)}>
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand to-tier-international text-brand-foreground shadow-soft">
        <Bot className="h-5 w-5" />
      </span>
      <span className="flex flex-col leading-none">
        <span className="text-[15px] font-bold tracking-tight">D.R.O.N.A.</span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Advising Platform
        </span>
      </span>
    </Link>
  );
}
