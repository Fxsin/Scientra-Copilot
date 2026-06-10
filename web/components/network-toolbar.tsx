"use client";

import { Search, RotateCcw } from "lucide-react";

import type { EdgeDensity, LabelMode } from "@/components/network-graph";

interface NetworkToolbarProps {
  search: string;
  onSearchChange: (v: string) => void;
  nodeTypes: string[];
  activeTypes: string[];
  onTypeToggle: (t: string) => void;
  onReset: () => void;
  stats: { node_count: number; link_count: number };
  edgeDensity: EdgeDensity;
  onEdgeDensityChange: (d: EdgeDensity) => void;
  labelMode: LabelMode;
  onLabelModeChange: (m: LabelMode) => void;
}

const TYPE_LABELS: Record<string, string> = {
  paper: "Papers",
  toxin: "Toxins",
  host: "Hosts",
  mechanism: "Mechanisms",
  method: "Methods",
};

const DENSITY_OPTS: EdgeDensity[] = ["sparse", "medium", "dense"];
const LABEL_OPTS: LabelMode[] = ["off", "concepts", "important", "all"];
const LABEL_NAMES: Record<LabelMode, string> = { off: "Off", concepts: "Concepts", important: "Important", all: "All" };

export function NetworkToolbar({
  search, onSearchChange, nodeTypes, activeTypes, onTypeToggle, onReset, stats,
  edgeDensity, onEdgeDensityChange, labelMode, onLabelModeChange,
}: NetworkToolbarProps) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative flex-1 min-w-[140px] max-w-[220px]">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 size-3 text-muted-foreground" />
          <input type="text" value={search} onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search…" className="h-7 w-full rounded-md border border-border bg-background pl-7 pr-2 text-xs outline-none focus-visible:border-ring" />
        </div>

        {/* Type toggles */}
        {nodeTypes.map((t) => {
          const active = activeTypes.includes(t);
          return (
            <button key={t} onClick={() => onTypeToggle(t)}
              className={`rounded px-1.5 py-0.5 text-[10px] font-medium border transition-colors ${active ? "bg-primary/10 border-primary/30 text-primary" : "bg-muted border-border text-muted-foreground hover:text-foreground"}`}>
              {TYPE_LABELS[t] ?? t}
            </button>
          );
        })}

        <span className="text-[10px] text-muted-foreground/40">|</span>

        {/* Edge Density */}
        {DENSITY_OPTS.map((d) => (
          <button key={d} onClick={() => onEdgeDensityChange(d)}
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors capitalize ${edgeDensity === d ? "bg-accent/15 text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            {d}
          </button>
        ))}

        <span className="text-[10px] text-muted-foreground/40">|</span>

        {/* Label Mode */}
        {LABEL_OPTS.map((m) => (
          <button key={m} onClick={() => onLabelModeChange(m)}
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors ${labelMode === m ? "bg-accent/15 text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>
            {LABEL_NAMES[m]}
          </button>
        ))}

        {/* Reset */}
        <button onClick={onReset} className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <RotateCcw className="size-3" /> Reset
        </button>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground/50">
        <span>{stats.node_count} nodes · {stats.link_count} links</span>
        <span>Density: {edgeDensity}</span>
        <span>Labels: {LABEL_NAMES[labelMode]}</span>
      </div>
    </div>
  );
}
