/**
 * Knowledge extraction utilities.
 *
 * Parses summary.md sections into structured knowledge cards.
 * No database changes. No LanceDB. No workflow. Presentation only.
 */

/* ── Section parsing ── */

export interface SummarySections {
  coreFinding: string[];
  evidence: string[];
  methods: string[];
  keyResults: string[];
  limitations: string[];
  relevance: string[];
  futureWork: string[];
  raw: string;
}

/** Parse summary markdown into named sections. */
export function parseSummarySections(markdown: string): SummarySections {
  const lines = markdown.split("\n");
  const sections: SummarySections = {
    coreFinding: [],
    evidence: [],
    methods: [],
    keyResults: [],
    limitations: [],
    relevance: [],
    futureWork: [],
    raw: markdown,
  };

  type ListSection = Exclude<keyof SummarySections, "raw">;
  let current: ListSection | null = null;

  const sectionMap: Record<string, ListSection> = {
    "core finding": "coreFinding",
    "evidence": "evidence",
    "methods": "methods",
    "key results": "keyResults",
    "limitations": "limitations",
    "relevance to my research": "relevance",
    "future work": "futureWork",
  };

  for (const line of lines) {
    const heading = line.match(/^#+\s+(.+)/);
    if (heading) {
      const name = heading[1].trim().toLowerCase();
      current = sectionMap[name] ?? null;
      continue;
    }
    if (current && line.trim().startsWith("- ")) {
      sections[current].push(line.trim().slice(2));
    }
  }

  return sections;
}

/* ── Knowledge Overview (one-liner) ── */

export function generateKnowledgeOverview(
  sections: SummarySections,
  title: string | null,
): string {
  // Prefer first core finding
  if (sections.coreFinding.length > 0) {
    const first = sections.coreFinding[0];
    // Strip citation anchors like (S007 source_section=...)
    const cleaned = first.replace(/\([^)]*S\d{3,}[^)]*\)/g, "").trim();
    return cleaned.length > 20
      ? cleaned
      : `${title ?? "This paper"} presents key findings relevant to the research domain.`;
  }
  // Fallback
  return `${title ?? "This paper"} contributes to the literature in this research domain.`;
}

/* ── Research Question ── */

export function extractResearchQuestion(
  sections: SummarySections,
  title: string | null,
): string {
  // Try to find a question-like pattern in coreFinding
  if (sections.coreFinding.length > 0) {
    const combined = sections.coreFinding.join(" ");
    // Look for "whether", "how", "determine", "investigate", "understand"
    const investigRe =
      /(?:investigates?|examines?|explores?|determines?|asks?\s+)?(?:whether|how|why|what)\s+([^.]+)/i;
    const match = combined.match(investigRe);
    if (match) {
      return `How does ${match[0].trim().replace(/^[,\s]+/, "")}?`;
    }
    // Use first core finding rephrased
    const cleaned = sections.coreFinding[0]
      .replace(/\([^)]*S\d{3,}[^)]*\)/g, "")
      .trim();
    return `This study investigates: ${cleaned.length > 150 ? cleaned.slice(0, 150) + "…" : cleaned}`;
  }
  return `${title ?? "This paper"} addresses key questions in its research domain.`;
}

/* ── Core Findings (max 3) ── */

export function extractCoreFindings(sections: SummarySections): string[] {
  const candidates = [
    ...sections.coreFinding,
    ...sections.keyResults,
  ];
  return candidates.slice(0, 3).map((f) =>
    f.replace(/\([^)]*S\d{3,}[^)]*\)/g, "").trim(),
  );
}

/* ── Novelty ── */

export interface NoveltyItem {
  text: string;
  tags: string[];
}

export function extractNovelty(sections: SummarySections): NoveltyItem[] {
  const tags: string[] = [];
  const allText = [
    ...sections.coreFinding,
    ...sections.evidence,
    ...sections.keyResults,
  ].join(" ").toLowerCase();

  const noveltyKeywords: Record<string, string> = {
    first: "First",
    novel: "Novel",
    "previously unknown": "Previously unknown",
    "newly identified": "Newly identified",
    "for the first time": "First",
    "breakthrough": "Breakthrough",
    unprecedented: "Unprecedented",
    "never before": "Novel",
    discovery: "Discovery",
  };

  for (const [keyword, label] of Object.entries(noveltyKeywords)) {
    if (allText.includes(keyword) && !tags.includes(label)) {
      tags.push(label);
    }
  }

  // Also extract the sentence containing the novelty keyword
  const items: NoveltyItem[] = [];
  const seen = new Set<string>();
  for (const finding of [...sections.coreFinding, ...sections.evidence]) {
    const lower = finding.toLowerCase();
    for (const [keyword, label] of Object.entries(noveltyKeywords)) {
      if (lower.includes(keyword) && !seen.has(label)) {
        seen.add(label);
        items.push({
          text: finding.replace(/\([^)]*S\d{3,}[^)]*\)/g, "").trim(),
          tags: [label],
        });
      }
    }
  }

  if (items.length === 0 && tags.length === 0) {
    tags.push("Established finding");
    if (sections.coreFinding[0]) {
      items.push({
        text: sections.coreFinding[0]
          .replace(/\([^)]*S\d{3,}[^)]*\)/g, "")
          .trim(),
        tags: ["Finding"],
      });
    }
  }

  return items;
}

/* ── Methods from tags ── */

export function extractMethodBadges(
  assignedTags: Record<string, string[]>,
): string[] {
  const methods = assignedTags["METHOD"] ?? [];
  // Filter for known methods
  const knownMethods = [
    "RNAi",
    "CRISPR",
    "LigandBlot",
    "SPR",
    "MST",
    "AlphaFold",
  ];
  const badges = methods.filter((m) =>
    knownMethods.some((k) => m.toLowerCase() === k.toLowerCase()),
  );
  return badges.length > 0 ? badges : methods;
}

/* ── Limitations ── */

export function extractLimitations(sections: SummarySections): string[] {
  if (sections.limitations.length > 0) {
    return sections.limitations.map((l) =>
      l.replace(/\([^)]*S\d{3,}[^)]*\)/g, "").trim(),
    );
  }
  return ["Not explicitly reported."];
}

/* ── Relevance matching ── */

const DEFAULT_RESEARCH_INTERESTS = [
  "Vip3A",
  "Cry toxins",
  "peritrophic membrane",
  "Bt mode of action",
  "insect receptor",
  "RNAi screening",
];

export interface RelevanceMatch {
  keyword: string;
  matchedIn: string[];
  reason: string;
}

export function matchRelevance(
  summary: string,
  tags: Record<string, string[]>,
  title: string | null,
  interests: string[] = DEFAULT_RESEARCH_INTERESTS,
): RelevanceMatch[] {
  const matches: RelevanceMatch[] = [];
  const lowerSummary = summary.toLowerCase();
  const lowerTitle = (title ?? "").toLowerCase();
  const allTags = Object.values(tags).flat().join(" ").toLowerCase();

  for (const interest of interests) {
    const lower = interest.toLowerCase();
    const matchedIn: string[] = [];
    if (lowerTitle.includes(lower)) matchedIn.push("title");
    if (allTags.includes(lower)) matchedIn.push("tags");
    if (lowerSummary.includes(lower)) matchedIn.push("summary");

    if (matchedIn.length > 0) {
      const reasons: Record<string, string> = {
        title: "Title directly mentions this topic",
        tags: `Assigned tags match research interest: ${interest}`,
        summary:
          "Summary discusses this topic in the context of experimental findings",
      };
      matches.push({
        keyword: interest,
        matchedIn,
        reason: matchedIn.map((m) => reasons[m]).join(". "),
      });
    }
  }

  return matches;
}
