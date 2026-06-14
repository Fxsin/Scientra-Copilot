"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Settings, FlaskConical, Palette, Check, Brain,
  Loader2, AlertCircle, Zap, Eye, EyeOff,
} from "lucide-react";
import { useApiWithFallback, updateGlobalDataSource } from "@/lib/use-api";
import { getStats, getAISettings, updateAISettings, testAIConnection } from "@/lib/api";
import { API_BASE_URL } from "@/lib/api";
import type { StatsResponse, AISettingsResponse } from "@/lib/types";

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

const PROVIDERS = [
  { id: "deepseek", name: "DeepSeek" },
  { id: "openai", name: "OpenAI" },
  { id: "anthropic", name: "Anthropic" },
  { id: "local", name: "Local" },
];

export default function SettingsPage() {
  const [activeTheme, setActiveTheme] = useState<string>("");
  const [mounted, setMounted] = useState(false);

  const { data: stats, dataSource } = useApiWithFallback(getStats, mockStats);

  useEffect(() => {
    updateGlobalDataSource(dataSource);
  }, [dataSource]);

  // ── AI Settings state ──
  const [aiSettings, setAiSettings] = useState<AISettingsResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(true);
  const [aiSaving, setAiSaving] = useState(false);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiTestResult, setAiTestResult] = useState<{ status: string; error?: string } | null>(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [editApiKey, setEditApiKey] = useState("");
  const [aiError, setAiError] = useState<string | null>(null);

  // ── Form state (populated from server) ──
  const [formProvider, setFormProvider] = useState("deepseek");
  const [formModel, setFormModel] = useState("deepseek-chat");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [formTemperature, setFormTemperature] = useState(0.2);
  const [formMaxTokens, setFormMaxTokens] = useState(4096);
  const [formEnabled, setFormEnabled] = useState(true);
  const [formTasks, setFormTasks] = useState<Record<string, boolean>>({});

  // Read saved theme on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setActiveTheme(saved);
    } catch {}
    setMounted(true);
  }, []);

  // Load AI settings
  useEffect(() => {
    let cancelled = false;
    async function load() {
      setAiLoading(true);
      setAiError(null);
      try {
        const s = await getAISettings();
        if (cancelled) return;
        setAiSettings(s);
        setFormProvider(s.provider);
        setFormModel(s.model);
        setFormBaseUrl(s.base_url);
        setFormTemperature(s.temperature);
        setFormMaxTokens(s.max_tokens);
        setFormEnabled(s.enabled);
        setFormTasks({ ...s.enabled_tasks });
        setEditApiKey("");
      } catch (err: unknown) {
        if (!cancelled) {
          setAiError(err instanceof Error ? err.message : "Failed to load AI settings");
        }
      } finally {
        if (!cancelled) setAiLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
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

  const handleSaveAI = useCallback(async () => {
    setAiSaving(true);
    setAiError(null);
    try {
      const body: Record<string, unknown> = {
        enabled: formEnabled,
        provider: formProvider,
        model: formModel,
        base_url: formBaseUrl,
        temperature: formTemperature,
        max_tokens: formMaxTokens,
        enabled_tasks: formTasks,
      };
      // Only send API key if the user typed a new one
      if (editApiKey) {
        body.api_key = editApiKey;
      }
      const updated = await updateAISettings(body as never);
      setAiSettings(updated);
      setEditApiKey("");
      setShowApiKey(false);
    } catch (err: unknown) {
      setAiError(err instanceof Error ? err.message : "Failed to save AI settings");
    } finally {
      setAiSaving(false);
    }
  }, [formEnabled, formProvider, formModel, formBaseUrl, formTemperature, formMaxTokens, formTasks, editApiKey]);

  const handleTest = useCallback(async () => {
    setAiTesting(true);
    setAiTestResult(null);
    try {
      const result = await testAIConnection({
        provider: formProvider,
        model: formModel,
        base_url: formBaseUrl,
        api_key: editApiKey || undefined,
      });
      setAiTestResult(result);
    } catch (err: unknown) {
      setAiTestResult({
        status: "failed",
        error: err instanceof Error ? err.message : "Connection test failed",
      });
    } finally {
      setAiTesting(false);
    }
  }, [formProvider, formModel, formBaseUrl, editApiKey]);

  const handleTaskToggle = useCallback((taskKey: string) => {
    setFormTasks((prev) => ({ ...prev, [taskKey]: !prev[taskKey] }));
  }, []);

  if (!mounted) return null;

  const isConfigured = aiSettings?.api_key_configured || !!editApiKey;

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

      {/* ── AI Settings Section (Phase 2.1) ── */}
      <div className="rounded-xl border bg-card p-6 space-y-4">
        <h2 className="text-base font-semibold flex items-center gap-2">
          <Brain className="size-4" />
          AI Provider
        </h2>
        <p className="text-xs text-muted-foreground">
          Configure the LLM provider used for summaries, evidence enrichment,
          and AI-powered analysis features.
        </p>

        {aiLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Loader2 className="size-4 animate-spin" />
            Loading AI settings…
          </div>
        ) : (
          <>
            {/* Status badge */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Status:</span>
              {formEnabled && isConfigured ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                  <Check className="size-3" />
                  Configured
                </span>
              ) : formEnabled ? (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  <AlertCircle className="size-3" />
                  Not Configured — API key required
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  Disabled
                </span>
              )}
            </div>

            {/* Enable/Disable */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formEnabled}
                onChange={(e) => setFormEnabled(e.target.checked)}
                className="rounded border-gray-300 text-primary focus:ring-primary"
              />
              <span className="text-sm">Enable AI features</span>
            </label>

            {/* Provider */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Provider</label>
              <select
                value={formProvider}
                onChange={(e) => setFormProvider(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                disabled={!formEnabled}
              >
                {PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            {/* Model / Base URL */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Model</label>
                <input
                  type="text"
                  value={formModel}
                  onChange={(e) => setFormModel(e.target.value)}
                  placeholder="e.g. deepseek-chat"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                  disabled={!formEnabled}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Base URL</label>
                <input
                  type="text"
                  value={formBaseUrl}
                  onChange={(e) => setFormBaseUrl(e.target.value)}
                  placeholder="e.g. https://api.deepseek.com"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                  disabled={!formEnabled}
                />
              </div>
            </div>

            {/* API Key */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                API Key
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showApiKey ? "text" : "password"}
                    value={editApiKey}
                    onChange={(e) => setEditApiKey(e.target.value)}
                    placeholder={
                      aiSettings?.api_key_preview
                        ? `Current: ${aiSettings.api_key_preview}`
                        : "Enter API key…"
                    }
                    className="w-full rounded-lg border bg-background px-3 py-2 pr-10 text-sm"
                    disabled={!formEnabled}
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    title={showApiKey ? "Hide API key" : "Show API key"}
                  >
                    {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              {aiSettings?.api_key_preview && !editApiKey && (
                <p className="text-[11px] text-muted-foreground">
                  Current key: {aiSettings.api_key_preview} (enter new key to change)
                </p>
              )}
            </div>

            {/* Temperature / Max Tokens */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  Temperature ({formTemperature})
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={formTemperature}
                  onChange={(e) => setFormTemperature(parseFloat(e.target.value))}
                  className="w-full"
                  disabled={!formEnabled}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">Max Tokens</label>
                <input
                  type="number"
                  value={formMaxTokens}
                  onChange={(e) => setFormMaxTokens(parseInt(e.target.value) || 4096)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                  disabled={!formEnabled}
                />
              </div>
            </div>

            {/* Task toggles */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">Enabled Tasks</label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {Object.entries(formTasks).map(([key, enabled]) => (
                  <label
                    key={key}
                    className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg border cursor-pointer transition-colors ${
                      enabled
                        ? "border-primary/30 bg-primary/5 text-primary"
                        : "border-border text-muted-foreground"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={enabled}
                      onChange={() => handleTaskToggle(key)}
                      className="sr-only"
                      disabled={!formEnabled}
                    />
                    <Zap className={`size-3 ${enabled ? "text-primary" : ""}`} />
                    {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  </label>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleSaveAI}
                disabled={aiSaving || !formEnabled}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {aiSaving && <Loader2 className="size-4 animate-spin" />}
                {aiSaving ? "Saving…" : "Save Settings"}
              </button>

              <button
                onClick={handleTest}
                disabled={aiTesting || !isConfigured}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border text-sm font-medium hover:bg-accent disabled:opacity-50"
              >
                {aiTesting && <Loader2 className="size-4 animate-spin" />}
                {aiTesting ? "Testing…" : "Test Connection"}
              </button>
            </div>

            {/* Test Result */}
            {aiTestResult && (
              <div
                className={`text-xs rounded-lg px-3 py-2 ${
                  aiTestResult.status === "ok"
                    ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400"
                    : "bg-red-50 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                }`}
              >
                {aiTestResult.status === "ok"
                  ? "✓ Connection successful! Provider is responding correctly."
                  : `✗ Connection failed: ${aiTestResult.error || "Unknown error"}`}
              </div>
            )}

            {/* Error */}
            {aiError && (
              <div className="text-xs rounded-lg px-3 py-2 bg-red-50 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                {aiError}
              </div>
            )}
          </>
        )}
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
