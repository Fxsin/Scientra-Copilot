"use client";

import { useState, useEffect, useCallback } from "react";
import { Settings, FlaskConical, Palette, Check } from "lucide-react";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";

/* ── Theme definitions ── */

interface ThemeInfo {
  id: string;
  name: string;
  description: string;
  swatches: string[];
  dark: boolean;
}

const THEMES: ThemeInfo[] = [
  {
    id: "",
    name: "Original",
    description: "Default navy-blue scheme — the classic Scientra look.",
    swatches: ["#0d1f39", "#2563EB", "#EA580C", "#F8FAFC"],
    dark: false,
  },
  {
    id: "ai-platform",
    name: "AI Platform",
    description: "Tech-forward purple with cyan accents. AI-native feel.",
    swatches: ["#1E1B4B", "#7C3AED", "#0891B2", "#FAF5FF"],
    dark: false,
  },
  {
    id: "biotech",
    name: "Biotech / Life Sciences",
    description: "Sky blue + life green. Evokes lab and research environments.",
    swatches: ["#0C4A6E", "#0EA5E9", "#059669", "#F0F9FF"],
    dark: false,
  },
  {
    id: "analytics",
    name: "Analytics Dashboard",
    description: "Deep blue + warm amber. Data-driven, professional tone.",
    swatches: ["#1E3A8A", "#1E40AF", "#D97706", "#F8FAFC"],
    dark: false,
  },
  {
    id: "healthcare",
    name: "Healthcare",
    description: "Clean cyan + green. Calm, credible, journal-editorial feel.",
    swatches: ["#164E63", "#0891B2", "#059669", "#ECFEFF"],
    dark: false,
  },
  {
    id: "education",
    name: "Education",
    description: "Indigo + energetic orange. Academic yet lively — Coursera vibes.",
    swatches: ["#1E1B4B", "#4F46E5", "#EA580C", "#EEF2FF"],
    dark: false,
  },
  {
    id: "knowledge",
    name: "Knowledge Base",
    description: "Neutral grey-blue. Minimal, content-first — GitBook style.",
    swatches: ["#1E293B", "#475569", "#2563EB", "#F8FAFC"],
    dark: false,
  },
  {
    id: "developer",
    name: "Developer (Dark)",
    description: "Dark terminal aesthetic + green accents. IDE-inspired.",
    swatches: ["#0F172A", "#1E293B", "#22C55E", "#0F172A"],
    dark: true,
  },
  {
    id: "premium",
    name: "Premium (Dark Gold)",
    description: "Dark luxury with gold + purple accents. High-end feel.",
    swatches: ["#0F172A", "#F59E0B", "#8B5CF6", "#0F172A"],
    dark: true,
  },
  {
    id: "nature",
    name: "Nature",
    description: "Deep green + earth tones. Environmental science aesthetic.",
    swatches: ["#064E3B", "#059669", "#10B981", "#ECFDF5"],
    dark: false,
  },
];

const STORAGE_KEY = "scientra-theme";

const mockStats: StatsResponse = {
  paper_count: 34,
  metadata_embedding_count: 5,
  summary_embedding_count: 5,
  chunk_embedding_count: 12,
  tag_distribution: {},
  year_distribution: {},
};

export default function SettingsPage() {
  const [activeTheme, setActiveTheme] = useState<string>("");
  const [mounted, setMounted] = useState(false);

  const { data: stats, dataSource } = useApiWithFallback(getStats, mockStats);

  useEffect(() => {
    updateGlobalDataSource(dataSource);
  }, [dataSource]);

  // Read saved theme on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setActiveTheme(saved);
    } catch {}
    setMounted(true);
  }, []);

  const applyTheme = useCallback((themeId: string) => {
    setActiveTheme(themeId);
    try {
      if (themeId) {
        localStorage.setItem(STORAGE_KEY, themeId);
        document.documentElement.setAttribute("data-theme", themeId);
      } else {
        localStorage.removeItem(STORAGE_KEY);
        document.documentElement.removeAttribute("data-theme");
      }
    } catch {}
  }, []);

  if (!mounted) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Settings className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Configure your Research OS preferences.
        </p>
      </div>

      {/* Color Scheme Picker */}
      <div className="rounded-xl border bg-card p-6 space-y-4">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Palette className="size-4" />
          Color Scheme
        </h2>
        <p className="text-xs text-muted-foreground">
          Choose a color scheme for the interface. Changes apply instantly and
          persist across sessions.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {THEMES.map((theme) => {
            const isActive = activeTheme === theme.id;
            return (
              <button
                key={theme.id}
                onClick={() => applyTheme(theme.id)}
                className={`text-left rounded-lg border p-3 transition-all hover:shadow-md flex items-start gap-3 ${
                  isActive
                    ? "border-primary ring-2 ring-ring/30 bg-primary/5"
                    : "border-border hover:border-muted-foreground/30"
                }`}
              >
                {/* Swatches */}
                <div className="flex gap-1 shrink-0 mt-0.5">
                  {theme.swatches.map((color, i) => (
                    <span
                      key={i}
                      className="size-5 rounded-full border border-black/10"
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                  ))}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{theme.name}</span>
                    {theme.dark && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-medium">
                        Dark
                      </span>
                    )}
                    {isActive && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/15 text-primary font-medium flex items-center gap-0.5">
                        <Check className="size-3" />
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                    {theme.description}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* About Card */}
      <div className="rounded-xl border bg-card p-6 space-y-4 max-w-lg">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-sidebar text-sidebar-primary-foreground">
            <FlaskConical className="size-5" />
          </div>
          <div>
            <h3 className="font-semibold">Scientra Copilot</h3>
            <p className="text-xs text-muted-foreground">
              Research OS v0.2.1 — Intelligence Platform
            </p>
          </div>
        </div>

        <div className="border-t pt-3 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Papers Imported</span>
            <span className="font-medium">{stats.paper_count}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Vectors Indexed</span>
            <span className="font-medium">{stats.metadata_embedding_count}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Data Source</span>
            <span className="font-medium">{dataSource === "REAL_API" ? "Real API" : dataSource}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">API Endpoint</span>
            <span className="font-medium text-xs">{API_BASE_URL}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
