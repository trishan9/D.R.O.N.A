"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="flex flex-col gap-5 px-3 py-4">
      {NAV.map((section) => (
        <div key={section.label} className="flex flex-col gap-1">
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            {section.label}
          </p>
          {section.items.map((item) => {
            const active = isActive(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                title={item.description}
                className={cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                )}
              >
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand" />
                )}
                <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-brand" : "opacity-80")} />
                <span className="flex-1 truncate">{item.title}</span>
                {item.badge && (
                  <Badge
                    variant={active ? "default" : "secondary"}
                    className="px-1.5 py-0 text-[10px] font-semibold"
                  >
                    {item.badge}
                  </Badge>
                )}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
