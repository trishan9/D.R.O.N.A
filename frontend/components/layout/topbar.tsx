"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";

import { navItemForPath } from "@/lib/nav";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Brand } from "./brand";
import { SidebarNav } from "./sidebar-nav";
import { ThemeToggle } from "./theme-toggle";
import { UserMenu } from "./user-menu";
import { HealthStatus } from "@/components/health-status";

export function Topbar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const item = navItemForPath(pathname);
  const title = item?.title ?? "D.R.O.N.A.";
  const description = item?.description ?? "";

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-md lg:px-8">
      {/* Mobile nav trigger */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-16 items-center border-b border-sidebar-border px-5">
            <Brand />
          </div>
          <div className="overflow-y-auto">
            <SidebarNav onNavigate={() => setOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>

      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold leading-tight tracking-tight">{title}</h1>
        {description && (
          <p className="hidden truncate text-xs text-muted-foreground sm:block">{description}</p>
        )}
      </div>

      <div className="hidden md:block">
        <HealthStatus />
      </div>
      <ThemeToggle />
      <UserMenu />
    </header>
  );
}
