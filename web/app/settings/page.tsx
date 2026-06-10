"use client";

import { Settings, FlaskConical } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Settings className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Configure your Research OS preferences.
        </p>
      </div>

      <div className="rounded-xl border bg-card p-6 space-y-4 max-w-lg">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-sidebar text-sidebar-primary-foreground">
            <FlaskConical className="size-5" />
          </div>
          <div>
            <h3 className="font-semibold">Scientra Copilot</h3>
            <p className="text-xs text-muted-foreground">
              Research OS v0.2.0 — Intelligence Platform
            </p>
          </div>
        </div>

        <div className="border-t pt-3 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Project</span>
            <span className="font-medium">Bt Toxin Mode of Action</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Papers</span>
            <span className="font-medium">34</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Data Source</span>
            <span className="font-medium">Mock Intelligence Layer</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Last Updated</span>
            <span className="font-medium">2026-06-09</span>
          </div>
        </div>
      </div>
    </div>
  );
}
