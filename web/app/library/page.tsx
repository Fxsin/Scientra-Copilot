"use client";

import { Library, BookOpen, Users, Calendar } from "lucide-react";
import {
  mockResearchPapers,
  type ResearchPaper,
} from "@/lib/data/researchIntelligenceMock";

export default function LibraryPage() {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Library className="size-5 text-slate-500" />
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Browse and manage your research paper collection.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatBadge label="Papers" value={mockResearchPapers.length} />
        <StatBadge label="Topics" value={25} />
        <StatBadge label="Gaps" value={6} />
      </div>

      <div className="space-y-3">
        {mockResearchPapers.map((paper) => (
          <PaperCard key={paper.id} paper={paper} />
        ))}
      </div>
    </div>
  );
}

function StatBadge({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border bg-card p-4 text-center">
      <span className="block text-2xl font-bold">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

function PaperCard({ paper }: { paper: ResearchPaper }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm hover:shadow-md transition-shadow space-y-3">
      <h3 className="text-base font-semibold leading-snug">{paper.title}</h3>

      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Users className="size-3" />
          {paper.authors.length > 2
            ? `${paper.authors[0]} et al.`
            : paper.authors.join(", ")}
        </span>
        <span className="flex items-center gap-1">
          <BookOpen className="size-3" />
          {paper.journal}
        </span>
        <span className="flex items-center gap-1">
          <Calendar className="size-3" />
          {paper.year}
        </span>
      </div>

      <ul className="space-y-1">
        {paper.keyFindings.map((f, i) => (
          <li
            key={i}
            className="text-sm text-muted-foreground pl-3 border-l-2 border-primary/20"
          >
            {f}
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap gap-1.5">
        {paper.methods.map((m) => (
          <span
            key={m}
            className="inline-flex items-center rounded-md bg-blue-50 text-blue-700 px-2 py-0.5 text-xs font-medium"
          >
            {m}
          </span>
        ))}
      </div>
    </div>
  );
}
