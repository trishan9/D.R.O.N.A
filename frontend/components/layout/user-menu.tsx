"use client";

import * as React from "react";
import Link from "next/link";
import { UserCircle, SlidersHorizontal, RotateCcw } from "lucide-react";

import { useStore } from "@/lib/store";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function initials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "You";
  const parts = trimmed.split(/\s+/);
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function UserMenu() {
  const { prefs, resetAll, hydrated } = useStore();
  const name = prefs.displayName || "Guest learner";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
        <Avatar className="h-9 w-9 border">
          <AvatarFallback className="bg-gradient-to-br from-brand/15 to-tier-international/15 text-xs font-bold text-brand">
            {hydrated ? initials(prefs.displayName) : "··"}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="flex flex-col">
          <span className="truncate">{name}</span>
          <span className="text-xs font-normal text-muted-foreground">Session-scoped · no PII</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/profile">
            <UserCircle className="text-muted-foreground" /> Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/preferences">
            <SlidersHorizontal className="text-muted-foreground" /> Preferences
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onClick={() => {
            if (confirm("Clear your device-local profile, history, and progress?")) resetAll();
          }}
        >
          <RotateCcw /> Reset session data
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
