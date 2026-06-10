"use client";

import { useState } from "react";
import { DemoBanner } from "@/components/demo-banner";
import {
  GitBranch,
  ChevronRight,
  ChevronDown,
  BookOpen,
  Beaker,
  AlertCircle,
  Sparkles,
  TrendingUp,
  Link2,
} from "lucide-react";
import {
  mockTopicTree,
  mockTopicDetails,
  getDefaultTopicDetail,
  getResearchGapsByTopicId,
  type TopicTreeNode,
  type TopicDetail,
} from "@/lib/data/researchIntelligenceMock";

export default function TopicExplorerPage() {
  const [selectedId, setSelectedId] = useState<string>("topic_pore_formation");

  const topicDetail =
    mockTopicDetails[selectedId] ??
    getDefaultTopicDetail(selectedId.replace(/^topic_/, ""));
  const linkedGaps = getResearchGapsByTopicId(selectedId);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <GitBranch className="size-5 text-purple-500" />
          <h1 className="text-2xl font-bold tracking-tight">Topic Explorer</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Browse the research topic hierarchy and explore definitions, findings,
          and connections.
        </p>
      </div>

      <DemoBanner />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="rounded-xl border bg-card p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Topic Tree
            </h2>
            {mockTopicTree.map((node) => (
              <TreeNodeRenderer
                key={node.id}
                node={node}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-xl border bg-card p-6 space-y-4">
            <h3 className="text-lg font-semibold">
              {topicDetail.id.replace(/_/g, " ")}
            </h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {topicDetail.definition}
            </p>

            <div className="flex items-center gap-2">
              <SignalStrength value={topicDetail.evidenceStrength} />
              <span className="text-xs text-muted-foreground">
                Evidence Strength
              </span>
            </div>

            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <TrendingUp className="size-3 mt-0.5 shrink-0" />
              <span>{topicDetail.recentActivity}</span>
            </div>

            <Section title="Key Findings" icon={Sparkles}>
              <ul className="list-disc list-inside space-y-1">
                {topicDetail.keyFindings.map((f, i) => (
                  <li key={i} className="text-sm text-muted-foreground">
                    {f}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title="Related Methods" icon={Beaker}>
              <div className="flex flex-wrap gap-1.5">
                {topicDetail.relatedMethods.map((m) => (
                  <span
                    key={m}
                    className="inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-xs font-medium"
                  >
                    {m}
                  </span>
                ))}
              </div>
            </Section>

            <Section title="Unresolved Questions" icon={AlertCircle}>
              <ul className="space-y-1">
                {topicDetail.unresolvedQuestions.map((q, i) => (
                  <li
                    key={i}
                    className="text-sm text-muted-foreground flex items-start gap-2"
                  >
                    <span className="text-amber-500 mt-1 shrink-0">?</span>
                    {q}
                  </li>
                ))}
              </ul>
            </Section>

            {linkedGaps.length > 0 && (
              <Section title="Connected Research Gaps" icon={Link2}>
                <ul className="space-y-1">
                  {linkedGaps.map((g) => (
                    <li
                      key={g.id}
                      className="text-sm text-red-600 flex items-start gap-2"
                    >
                      <AlertCircle className="size-3 mt-1 shrink-0" />
                      {g.title}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <Section title="Suggested Reading Order" icon={BookOpen}>
              <ol className="list-decimal list-inside space-y-1">
                {topicDetail.suggestedReadingOrder.map((r, i) => (
                  <li key={i} className="text-sm text-muted-foreground">
                    {r}
                  </li>
                ))}
              </ol>
            </Section>
          </div>
        </div>
      </div>
    </div>
  );
}

function TreeNodeRenderer({
  node,
  selectedId,
  onSelect,
  depth = 0,
}: {
  node: TopicTreeNode;
  selectedId: string;
  onSelect: (id: string) => void;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 1);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = node.id === selectedId;

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) setOpen(!open);
          onSelect(node.id);
        }}
        className={`flex items-center gap-1.5 w-full text-left py-1 px-2 rounded-md text-sm transition-colors ${
          isSelected
            ? "bg-primary/10 text-primary font-medium"
            : "hover:bg-muted text-foreground"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          open ? (
            <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="size-3 shrink-0 text-muted-foreground" />
          )
        ) : (
          <span className="w-3" />
        )}
        {node.label}
      </button>
      {open &&
        hasChildren &&
        node.children!.map((child) => (
          <TreeNodeRenderer
            key={child.id}
            node={child}
            selectedId={selectedId}
            onSelect={onSelect}
            depth={depth + 1}
          />
        ))}
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t pt-3">
      <p className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
        <Icon className="size-3.5" />
        {title}
      </p>
      {children}
    </div>
  );
}

function SignalStrength({ value }: { value: number }) {
  const bars = Math.ceil(value / 25);
  return (
    <div className="flex items-end gap-0.5 h-4">
      {[1, 2, 3, 4].map((n) => (
        <div
          key={n}
          className={`w-1.5 rounded-t-sm transition-colors ${
            n <= bars
              ? value >= 75
                ? "bg-emerald-500"
                : value >= 50
                  ? "bg-blue-500"
                  : value >= 25
                    ? "bg-amber-500"
                    : "bg-red-500"
              : "bg-slate-200"
          }`}
          style={{ height: `${n * 4}px` }}
        />
      ))}
    </div>
  );
}
