"use client";

import { Search, Bell, User } from "lucide-react";
import { Button } from "@/components/ui/button";

export function TopNav() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-background/80 backdrop-blur-md px-6">
      {/* Page title area — can be overridden via slot */}
      <div className="flex-1" />

      {/* Global search trigger */}
      <Button
        variant="outline"
        size="sm"
        className="hidden md:inline-flex h-8 w-64 justify-start gap-2 text-muted-foreground text-xs font-normal"
      >
        <Search className="size-3.5" strokeWidth={2} />
        <span>Search papers, notes, tags…</span>
        <kbd className="ml-auto inline-flex h-5 items-center gap-0.5 rounded border border-border bg-muted px-1.5 font-mono text-[10px] text-muted-foreground">
          ⌘K
        </kbd>
      </Button>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="size-8" aria-label="Notifications">
          <Bell className="size-4" strokeWidth={1.5} />
        </Button>
        <Button variant="ghost" size="icon" className="size-8" aria-label="User menu">
          <User className="size-4" strokeWidth={1.5} />
        </Button>
      </div>
    </header>
  );
}
