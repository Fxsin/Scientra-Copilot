"use client";

import {
  Printer,
  Download,
  FlaskConical,
  Calendar,
  Star,
  Signal,
  TrendingUp,
  SearchCheck,
  Target,
  Lightbulb,
  BookOpen,
  Hash,
} from "lucide-react";
import {
  mockProjectMeta,
  mockProjectSummary,
  mockResearchInsights,
  mockHotspots,
  mockResearchGaps,
  mockTopics,
  mockCoverage,
  mockMajorQuestions,
  mockResearchPapers,
} from "@/lib/data/researchIntelligenceMock";

export default function ReportPage() {
  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="space-y-8" id="report-content">
      {/* Title Banner */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="bg-sidebar px-6 py-8 text-sidebar-foreground">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-sidebar-primary">
              <FlaskConical className="size-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Research Intelligence Report</h1>
              <p className="text-xs text-sidebar-foreground/60">
                Scientra Copilot — Research OS
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-sidebar-foreground/70">
            <span className="flex items-center gap-1">
              <Calendar className="size-3" />
              Generated: {today}
            </span>
            <span className="flex items-center gap-1">
              <BookOpen className="size-3" />
              Project: {mockProjectMeta.projectName}
            </span>
            <span className="flex items-center gap-1">
              <Hash className="size-3" />
              {mockProjectMeta.paperCount} Papers
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 px-6 py-3 border-b bg-muted/30">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Printer className="size-3.5" />
            Print Report
          </button>
          <button
            onClick={() => {
              const el = document.getElementById("report-content");
              if (!el) return;
              const text = el.innerText;
              const blob = new Blob([text], {
                type: "text/plain;charset=utf-8",
              });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `Scientra_Report_${today}.txt`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="inline-flex items-center gap-1.5 rounded-md border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
          >
            <Download className="size-3.5" />
            Export TXT
          </button>
        </div>
      </div>

      {/* Executive Summary */}
      <Section icon={Star} title="Executive Summary" color="text-yellow-600">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <SummaryStat
            label="Papers"
            value={mockProjectSummary.paperCount}
          />
          <SummaryStat
            label="Core Topics"
            value={mockProjectSummary.coreTopicCount}
          />
          <SummaryStat
            label="Hotspots"
            value={mockProjectSummary.hotspotCount}
          />
          <SummaryStat
            label="Research Gaps"
            value={mockProjectSummary.gapCount}
          />
        </div>

        <div className="space-y-3">
          <InsightBlock
            label="What is Established"
            color="emerald"
            text={mockResearchInsights.whatIsEstablished}
          />
          <InsightBlock
            label="What is Uncertain"
            color="amber"
            text={mockResearchInsights.whatIsUncertain}
          />
          <InsightBlock
            label="Next Opportunity"
            color="blue"
            text={mockResearchInsights.nextOpportunity}
          />
        </div>
      </Section>

      {/* Knowledge Coverage */}
      <Section icon={Signal} title="Knowledge Coverage" color="text-indigo-600">
        <div className="space-y-3">
          {mockCoverage.map((dim) => (
            <div key={dim.id} className="flex items-center gap-3">
              <span className="text-sm font-medium w-28 shrink-0">
                {dim.label}
              </span>
              <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${dim.percentage}%` }}
                />
              </div>
              <span className="text-sm font-semibold w-10 text-right">
                {dim.percentage}%
              </span>
              <span className="text-xs text-muted-foreground w-32 text-right">
                {dim.paperCount} papers
              </span>
            </div>
          ))}
        </div>
      </Section>

      {/* Core Topics */}
      <Section icon={BookOpen} title="Core Research Topics" color="text-blue-600">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {mockTopics.map((topic) => (
            <div key={topic.id} className="rounded-lg border p-4 space-y-2">
              <h4 className="text-sm font-semibold">
                {topic.name}
                <span className="ml-2 text-xs text-muted-foreground">
                  ({topic.count} papers)
                </span>
              </h4>
              <ul className="space-y-0.5">
                {topic.representatives.map((r, i) => (
                  <li
                    key={i}
                    className="text-xs text-muted-foreground pl-3 border-l-2 border-primary/20"
                  >
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* Hotspots */}
      <Section
        icon={TrendingUp}
        title="Research Hotspots"
        color="text-orange-600"
      >
        <div className="space-y-4">
          {mockHotspots.map((hs) => (
            <div key={hs.id} className="rounded-lg border p-4 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-semibold">{hs.name}</h4>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-700 px-2 py-0.5 text-[11px] font-medium shrink-0">
                  <TrendingUp className="size-3" />
                  {hs.trend} ({hs.growthScore}%)
                </span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {hs.whyItMatters}
              </p>
              <div className="flex flex-wrap gap-1">
                {hs.keyMethods.map((m) => (
                  <span
                    key={m}
                    className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-[10px] font-medium"
                  >
                    {m}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Research Gaps */}
      <Section
        icon={SearchCheck}
        title="Research Gaps & Opportunities"
        color="text-red-600"
      >
        <div className="space-y-4">
          {mockResearchGaps.map((gap) => (
            <div key={gap.id} className="rounded-lg border p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex items-center rounded-full bg-red-50 text-red-700 px-2 py-0.5 text-[10px] font-semibold">
                      {gap.gapType}
                    </span>
                    <span className="text-[11px] font-medium text-emerald-600">
                      {gap.opportunityLevel} Opportunity
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold">{gap.title}</h4>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <MiniMetric label="Conf" value={gap.confidence} />
                  <MiniMetric label="Impact" value={gap.impact} />
                  <MiniMetric label="Feas" value={gap.feasibility} />
                </div>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {gap.description}
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md bg-blue-50/50 border border-blue-100 p-2">
                  <p className="text-[10px] font-semibold text-blue-800 mb-0.5">
                    Known
                  </p>
                  <p className="text-[10px] text-blue-700 leading-relaxed">
                    {gap.knownSummary}
                  </p>
                </div>
                <div className="rounded-md bg-red-50/50 border border-red-100 p-2">
                  <p className="text-[10px] font-semibold text-red-800 mb-0.5">
                    Missing
                  </p>
                  <p className="text-[10px] text-red-700 leading-relaxed">
                    {gap.missingSummary}
                  </p>
                </div>
              </div>
              <div className="rounded-md bg-emerald-50/50 border border-emerald-100 p-2">
                <p className="text-[10px] font-semibold text-emerald-800 mb-0.5 flex items-center gap-1">
                  <Lightbulb className="size-3" />
                  Suggested Next Step
                </p>
                <p className="text-[10px] text-emerald-700 leading-relaxed">
                  {gap.suggestedNextStep}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Major Questions */}
      <Section
        icon={Target}
        title="Major Research Questions"
        color="text-purple-600"
      >
        <div className="space-y-3">
          {mockMajorQuestions.map((q) => (
            <div
              key={q.id}
              className="flex items-start gap-3 rounded-lg border p-3"
            >
              <span className="text-lg font-bold text-primary/30 mt-0.5">
                Q
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{q.question}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      q.evidenceLevel === "Strong"
                        ? "bg-emerald-50 text-emerald-700"
                        : q.evidenceLevel === "Moderate"
                          ? "bg-blue-50 text-blue-700"
                          : q.evidenceLevel === "Weak"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-purple-50 text-purple-700"
                    }`}
                  >
                    {q.evidenceLevel} Evidence
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {q.paperCount} papers
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Key Literature */}
      <Section icon={BookOpen} title="Key Literature" color="text-slate-600">
        <div className="space-y-3">
          {mockResearchPapers.map((paper) => (
            <div key={paper.id} className="rounded-lg border p-3 space-y-1.5">
              <h4 className="text-sm font-semibold">{paper.title}</h4>
              <p className="text-xs text-muted-foreground">
                {paper.authors.join(", ")} ({paper.year}) —{" "}
                <span className="italic">{paper.journal}</span>
              </p>
              <ul className="space-y-0.5">
                {paper.keyFindings.map((f, i) => (
                  <li
                    key={i}
                    className="text-xs text-muted-foreground pl-3 border-l-2 border-primary/20"
                  >
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* Footer */}
      <div className="border-t pt-4 text-center text-xs text-muted-foreground space-y-1">
        <p>
          Generated by <span className="font-semibold">Scientra Copilot</span>{" "}
          — Research OS v0.2.0
        </p>
        <p>
          This report synthesizes {mockProjectMeta.paperCount} papers across{" "}
          {mockProjectSummary.coreTopicCount} core topics. Data as of{" "}
          {mockProjectMeta.lastUpdated}.
        </p>
        <p className="text-[10px]">
          Disclaimer: This is a demo report generated from mock intelligence
          layer data for demonstration purposes.
        </p>
      </div>
    </div>
  );
}

/* ── Reusable Components ── */

function Section({
  icon: Icon,
  title,
  color,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-card p-6">
      <h2 className="flex items-center gap-2 text-lg font-bold mb-4">
        <Icon className={`size-5 ${color}`} />
        {title}
      </h2>
      {children}
    </section>
  );
}

function SummaryStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-muted p-3 text-center">
      <span className="block text-2xl font-bold text-primary">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function InsightBlock({
  label,
  color,
  text,
}: {
  label: string;
  color: string;
  text: string;
}) {
  const colors: Record<string, string> = {
    emerald: "border-l-emerald-500 bg-emerald-50/50",
    amber: "border-l-amber-500 bg-amber-50/50",
    blue: "border-l-blue-500 bg-blue-50/50",
  };
  return (
    <div className={`border-l-4 rounded-r-lg p-3 ${colors[color]}`}>
      <p className="text-xs font-semibold text-muted-foreground mb-1">
        {label}
      </p>
      <p className="text-sm leading-relaxed">{text}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <span className="block text-xs font-bold">{value}</span>
      <span className="block text-[9px] text-muted-foreground">{label}</span>
    </div>
  );
}
