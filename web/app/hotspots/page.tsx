"use client";

import {
  Flame,
  TrendingUp,
  TrendingDown,
  Calendar,
  Beaker,
  Lightbulb,
} from "lucide-react";
import { DemoBanner } from "@/components/demo-banner";
import {
  mockHotspots,
  type HotspotItem,
  type TrendLabel,
} from "@/lib/data/researchIntelligenceMock";

const trendConfig: Record<
  TrendLabel,
  { color: string; bg: string; icon: typeof TrendingUp }
> = {
  Emerging: {
    color: "text-emerald-700",
    bg: "bg-emerald-50",
    icon: TrendingUp,
  },
  Growing: {
    color: "text-blue-700",
    bg: "bg-blue-50",
    icon: TrendingUp,
  },
  Stable: {
    color: "text-slate-600",
    bg: "bg-slate-100",
    icon: Calendar,
  },
  Declining: {
    color: "text-amber-700",
    bg: "bg-amber-50",
    icon: TrendingDown,
  },
};

export default function HotspotsPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Flame className="size-5 text-orange-500" />
          <h1 className="text-2xl font-bold tracking-tight">Hotspots</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Research topics with the highest recent activity and growth potential.
        </p>
      </div>

      <DemoBanner />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {mockHotspots.map((hs) => (
          <HotspotCard key={hs.id} hotspot={hs} />
        ))}
      </div>
    </div>
  );
}

function HotspotCard({ hotspot }: { hotspot: HotspotItem }) {
  const cfg = trendConfig[hotspot.trend];
  const TrendIcon = cfg.icon;

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow space-y-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-base font-semibold leading-snug">{hotspot.name}</h3>
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.color} ${cfg.bg}`}
        >
          <TrendIcon className="size-3" />
          {hotspot.trend}
        </span>
      </div>

      <p className="text-sm text-muted-foreground leading-relaxed">
        {hotspot.whyItMatters}
      </p>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Calendar className="size-3" />
          {hotspot.recentPaperCount} recent papers
        </span>
        <span className="flex items-center gap-1">
          <TrendingUp className="size-3" />
          Growth: {hotspot.growthScore}%
        </span>
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
          <Beaker className="size-3" />
          Key Methods
        </p>
        <div className="flex flex-wrap gap-1.5">
          {hotspot.keyMethods.map((m) => (
            <span
              key={m}
              className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium"
            >
              {m}
            </span>
          ))}
        </div>
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
          <Lightbulb className="size-3" />
          Representative Papers
        </p>
        <ul className="space-y-1">
          {hotspot.representativePapers.map((p, i) => (
            <li
              key={i}
              className="text-xs text-muted-foreground pl-3 border-l-2 border-muted-foreground/20"
            >
              {p}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
