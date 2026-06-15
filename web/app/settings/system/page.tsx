"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Cpu,
  HardDrive,
  Database,
  Brain,
  Key,
  Network,
  Package,
  Server,
} from "lucide-react";

interface CheckItem {
  name: string;
  status: "PASS" | "WARN" | "FAIL" | "INFO";
  detail: string;
  fix: string;
}

interface HealthData {
  available: boolean;
  health_score: number;
  status: string;
  summary: {
    total_checks: number;
    passed: number;
    warnings: number;
    failed: number;
  };
  checks: CheckItem[];
  repair_suggestions: { problem: string; severity: string; cause: string; fix: string }[];
}

interface StartupStatus {
  api_running: boolean;
  api_url: string | null;
  web_running: boolean;
  web_url: string | null;
  health_score: number;
  health_status: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8710";

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ReactNode; color: string }> = {
    PASS: { icon: <CheckCircle2 className="size-4" />, color: "text-green-500" },
    WARN: { icon: <AlertTriangle className="size-4" />, color: "text-yellow-500" },
    FAIL: { icon: <XCircle className="size-4" />, color: "text-red-500" },
    INFO: { icon: <Info className="size-4" />, color: "text-blue-400" },
  };
  const c = config[status] || config.INFO;
  return <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.color}`}>{c.icon} {status}</span>;
}

function getCheckIcon(name: string) {
  const lower = name.toLowerCase();
  if (lower.includes("python") || lower.includes("cpu")) return <Cpu className="size-4" />;
  if (lower.includes("disk")) return <HardDrive className="size-4" />;
  if (lower.includes("lance") || lower.includes("db")) return <Database className="size-4" />;
  if (lower.includes("bge") || lower.includes("model")) return <Brain className="size-4" />;
  if (lower.includes("api") || lower.includes("key")) return <Key className="size-4" />;
  if (lower.includes("port")) return <Network className="size-4" />;
  if (lower.includes("dependencies") || lower.includes("node") || lower.includes("git")) return <Package className="size-4" />;
  if (lower.includes("ram") || lower.includes("gpu")) return <Server className="size-4" />;
  return <Activity className="size-4" />;
}

export default function SystemPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [startup, setStartup] = useState<StartupStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [hRes, sRes] = await Promise.all([
          fetch(`${API_BASE}/system/health`),
          fetch(`${API_BASE}/system/startup-status`),
        ]);
        const hData = await hRes.json();
        const sData = await sRes.json();
        setHealth(hData);
        setStartup(sData);
      } catch {
        setHealth(null);
        setStartup(null);
      }
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-muted-foreground">Loading system status…</div>
      </div>
    );
  }

  const score = health?.health_score ?? 0;
  const status = health?.status ?? "unknown";
  const scoreColor =
    status === "healthy" ? "text-green-500" : status === "degraded" ? "text-yellow-500" : "text-red-500";
  const scoreBg =
    status === "healthy"
      ? "bg-green-500/10"
      : status === "degraded"
      ? "bg-yellow-500/10"
      : "bg-red-500/10";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">System Status</h1>
        <p className="text-sm text-muted-foreground mt-1">P6.6.1 Environment &amp; Health Monitor</p>
      </div>

      {/* Health Score Card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`rounded-lg border p-6 text-center ${scoreBg}`}>
          <div className={`text-5xl font-bold ${scoreColor}`}>{score}</div>
          <div className="text-sm text-muted-foreground mt-1">Health Score / 100</div>
          <div className={`text-xs font-semibold uppercase mt-1 ${scoreColor}`}>{status}</div>
        </div>

        {/* Startup Status */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Services</h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>API Server</span>
              <span className={startup?.api_running ? "text-green-500" : "text-muted-foreground"}>
                {startup?.api_running ? "✅ Running" : "⏹ Stopped"}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span>Web Frontend</span>
              <span className={startup?.web_running ? "text-green-500" : "text-muted-foreground"}>
                {startup?.web_running ? "✅ Running" : "⏹ Stopped"}
              </span>
            </div>
            {startup?.api_url && (
              <div className="text-xs text-muted-foreground mt-1">API: {startup.api_url}</div>
            )}
            {startup?.web_url && (
              <div className="text-xs text-muted-foreground">Web: {startup.web_url}</div>
            )}
          </div>
        </div>

        {/* Summary */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-semibold mb-3">Checks Summary</h3>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5"><CheckCircle2 className="size-3.5 text-green-500" /> Passed</span>
              <span className="font-mono font-bold text-green-600">{health?.summary.passed ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5"><AlertTriangle className="size-3.5 text-yellow-500" /> Warnings</span>
              <span className="font-mono font-bold text-yellow-600">{health?.summary.warnings ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-1.5"><XCircle className="size-3.5 text-red-500" /> Failed</span>
              <span className="font-mono font-bold text-red-600">{health?.summary.failed ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Check Results Table */}
      {health?.available && health.checks && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3">
            <h2 className="font-semibold">Environment Checks</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50 text-left">
                  <th className="px-5 py-2 font-medium w-8"></th>
                  <th className="px-5 py-2 font-medium">Check</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Detail</th>
                  <th className="px-5 py-2 font-medium">Fix</th>
                </tr>
              </thead>
              <tbody>
                {health.checks.map((c, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-5 py-2 text-muted-foreground">{getCheckIcon(c.name)}</td>
                    <td className="px-5 py-2 font-medium text-xs">{c.name}</td>
                    <td className="px-5 py-2"><StatusBadge status={c.status} /></td>
                    <td className="px-5 py-2 text-xs text-muted-foreground max-w-[200px] truncate">{c.detail}</td>
                    <td className="px-5 py-2 text-xs text-muted-foreground max-w-[200px] truncate">{c.fix || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Repair Suggestions */}
      {health?.repair_suggestions && health.repair_suggestions.length > 0 && (
        <section className="rounded-lg border bg-card">
          <div className="border-b px-5 py-3 flex items-center gap-2">
            <AlertTriangle className="size-4 text-yellow-500" />
            <h2 className="font-semibold">Repair Suggestions</h2>
            <span className="text-xs text-muted-foreground">{health.repair_suggestions.length} issues</span>
          </div>
          <div className="p-5 space-y-3">
            {health.repair_suggestions.map((r, i) => (
              <div key={i} className="flex items-start gap-3 rounded-md border p-3">
                <span className="mt-0.5">{r.severity === "FAIL" ? "🔴" : "🟡"}</span>
                <div>
                  <div className="font-medium text-sm">{r.problem}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">Cause: {r.cause}</div>
                  <div className="text-xs text-blue-500 mt-0.5">Fix: {r.fix}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty State */}
      {!health?.available && (
        <div className="rounded-lg border border-dashed p-12 text-center">
          <Activity className="mx-auto size-12 text-muted-foreground/40" />
          <h2 className="mt-4 text-lg font-semibold">System health data unavailable</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Run environment check to generate health data:
          </p>
          <code className="mt-4 inline-block rounded bg-muted px-4 py-2 text-sm">
            python Scripts/check_environment.py
          </code>
        </div>
      )}
    </div>
  );
}
