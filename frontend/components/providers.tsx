"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";

import { AppStoreProvider } from "@/lib/store";

/** All client-side context providers for the app shell. */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <AppStoreProvider>
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
      </AppStoreProvider>
    </NextThemesProvider>
  );
}
