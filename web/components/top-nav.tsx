"use client";

import { Bell, User } from "lucide-react";
import { Button } from "@/components/ui/button";

export function TopNav() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b border-border bg-background/80 backdrop-blur-md px-6">
      <div className="flex-1" />

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