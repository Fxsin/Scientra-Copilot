/**
 * Evidence-driven Topic Evolution Analysis.
 * Generic — no domain-specific logic. Uses parseAISummary for structured extraction.
 */

import { parseAISummary, cleanSummarySnippet, type ParsedSummary } from "./summary-parser";

/* ─── Types ─── */

export interface EvidenceQuote {
  paper_id: string;
  title: string;
  year?: number | null;
  journal?: string | null;
  excerpt: string;
  source_type: "core_finding" | "evidence" | "method" | "limitation" | "gap" | "summary" | "title" | "discussion_point" | "key_result" | "open_question" | "claim";
}

export interface MilestonePaper {
  paper_id: string;
  title: string;
  authors?: string[];
  year?: number | null;
  journal?: string | null;
  reason: string;
  key_excerpt?: string;
}

export interface PhaseAnalysis {
  phase: "early" | "middle" | "recent";
  label: string;
  year_range: [number, number];
  paper_count: number;
  focus: string | null;
  key_conclusions: EvidenceQuote[];
  evidence_quotes: EvidenceQuote[];
  method_signals: string[];
  milestone_papers: MilestonePaper[];
  change_from_previous: string | null;
  open_questions: EvidenceQuote[];
  confidence: "high" | "medium" | "low";
  evidence_count: number;
}

export interface PaperEvidence {
  paper_id: string;
  title: string;
  year?: number | null;
  journal?: string | null;
  authors?: string[];
  parsed: ParsedSummary | null;
  raw_text: string | null;
}

/* ─── Generic method signal words ─── */

const METHOD_WORDS = new Set([
  "assay", "analysis", "sequencing", "microscopy", "structure", "structural",
  "binding", "modeling", "profiling", "transcriptomics", "proteomics",
  "screen", "screening", "survey", "comparison", "validation", "experiment",
  "expression", "purification", "imaging", "phylogeny", "phylogenetic",
  "genome", "genomic", "simulation", "statistical", "cryo-em", "crystallography",
  "nmr", "spectroscopy", "chromatography", "electrophoresis", "blot",
  "pcr", "qpcr", "rna-seq", "rnai", "crispr", "knockout", "knockdown",
  "overexpression", "mutagenesis", "pull-down", "co-ip", "elisa", "western",
  "immunofluorescence", "flow-cytometry", "bioassay", "diet-overlay",
  "leaf-disk", "feeding", "injection", "bioinformatics", "docking",
]);

/* ─── Clean text ─── */

export function cleanEvidenceText(s: string): string {
  let t = s;
  t = t.replace(/"text"\s*:\s*/gi, "").replace(/"content"\s*:\s*/gi, "").replace(/"citations?"\s*:\s*/gi, "");
  // Strip JSON section labels
  t = t.replace(/"(Core Finding|Core Findings|Evidence|Methods?|Limitations?|Gaps?|Pathways?|Key Results?)"\s*:\s*/gi, "");
  t = t.replace(/[{}[\]\\]/g, "");
  t = t.replace(/\*\*/g, "").replace(/\s+/g, " ").trim();
  t = t.replace(/^["']|["']$/g, "").replace(/"/g, "");
  if (t.length < 6) return "";
  return t;
}

/* ─── Extract paper evidence ─── */

/** Normalize evidence object: snake_case API fields → internal camelCase + extract text */
export function normalizePaperEvidence(rawEvidence: Record<string, unknown> | null | undefined): {
  coreFindings: string[];
  keyResults: string[];
  discussionPoints: string[];
  methods: string[];
  limitations: string[];
  openQuestions: string[];
  claims: string[];
  evidenceQuotes: { excerpt: string; source_type: string; quote: string }[];
  hasContent: boolean;
  sourceLabel: string;
} {
  const empty = {
    coreFindings: [] as string[], keyResults: [] as string[],
    discussionPoints: [] as string[], methods: [] as string[],
    limitations: [] as string[], openQuestions: [] as string[],
    claims: [] as string[], evidenceQuotes: [] as { excerpt: string; source_type: string; quote: string }[],
    hasContent: false, sourceLabel: "title_fallback",
  };

  if (!rawEvidence || typeof rawEvidence !== "object") return empty;

  const ev = rawEvidence as Record<string, unknown>;
  if (ev.status === "failed") return empty;

  // Extract text from each field, handling both string and object formats
  const extractArray = (arr: unknown, primaryKey: string, fallbackKey = "text"): string[] => {
    if (!Array.isArray(arr)) return [];
    return arr.map((item: unknown) => {
      if (typeof item === "string") return item.slice(0, 300);
      if (item && typeof item === "object") {
        const obj = item as Record<string, unknown>;
        return String(obj[primaryKey] || obj[fallbackKey] || "").slice(0, 300);
      }
      return "";
    }).filter(Boolean);
  };

  const extractQuotes = (arr: unknown, sourceType: string): { excerpt: string; source_type: string; quote: string }[] => {
    if (!Array.isArray(arr)) return [];
    return arr.map((item: unknown) => {
      if (typeof item === "string") return { excerpt: item.slice(0, 300), source_type: sourceType, quote: item.slice(0, 200) };
      if (item && typeof item === "object") {
        const obj = item as Record<string, unknown>;
        const text = String(obj.point || obj.result || obj.finding || obj.limitation || obj.question || obj.claim || obj.name || obj.text || "").slice(0, 300);
        const quote = String(obj.quote || "").slice(0, 200);
        return { excerpt: text, source_type: sourceType, quote: quote || text.slice(0, 200) };
      }
      return { excerpt: "", source_type: sourceType, quote: "" };
    }).filter(q => q.excerpt.length > 0);
  };

  const coreFindings = extractArray(ev.core_findings, "finding");
  const keyResults = extractArray(ev.key_results, "result");
  const discussionPoints = extractArray(ev.discussion_points, "point");
  const methods = extractArray(ev.methods, "name");
  const limitations = extractArray(ev.limitations, "limitation");
  const openQuestions = extractArray(ev.open_questions, "question");
  const claims = extractArray(ev.claims, "claim");

  // Build evidence quotes from all sources
  const evidenceQuotes = [
    ...extractQuotes(ev.discussion_points, "discussion_point"),
    ...extractQuotes(ev.key_results, "key_result"),
    ...extractQuotes(ev.core_findings, "core_finding"),
    ...extractQuotes(ev.methods, "method"),
    ...extractQuotes(ev.limitations, "limitation"),
    ...extractQuotes(ev.open_questions, "open_question"),
    ...extractQuotes(ev.claims, "claim"),
  ];

  const hasContent = coreFindings.length + keyResults.length + discussionPoints.length + methods.length + limitations.length + openQuestions.length + claims.length > 0;

  return {
    coreFindings, keyResults, discussionPoints, methods, limitations, openQuestions, claims,
    evidenceQuotes, hasContent,
    sourceLabel: hasContent ? "structured_evidence" : "title_fallback",
  };
}


export function extractPaperEvidence(paper: {
  paper_id: string; title?: string | null; authors?: string[] | null;
  year?: number | null; journal?: string | null; summary?: string | null;
  evidence?: any | null;
}): PaperEvidence {
  const title = paper.title || "";

  // Priority: structured evidence > summary > title fallback
  const ev = paper.evidence;
  if (ev && ev.status !== "failed") {
    const norm = normalizePaperEvidence(ev);
    if (norm.hasContent) {
      // Combine all evidence into a parsed-like structure
      const allEvidence = [...norm.keyResults, ...norm.discussionPoints, ...norm.coreFindings];
      return {
        paper_id: paper.paper_id, title, year: paper.year, journal: paper.journal || null,
        authors: paper.authors || [],
        parsed: {
          takeaway: norm.coreFindings[0] || norm.keyResults[0] || norm.discussionPoints[0] || null,
          coreFindings: norm.coreFindings,
          evidence: allEvidence,
          methods: norm.methods,
          limitations: norm.limitations,
          gaps: norm.openQuestions,
          others: norm.claims,
        },
        raw_text: "[structured_evidence]" as any,
      };
    }
  }

  // Fallback to summary
  const summary = paper.summary || null;
  const parsed = summary ? parseAISummary(summary) : null;
  return {
    paper_id: paper.paper_id, title, year: paper.year, journal: paper.journal || null,
    authors: paper.authors || [],
    parsed,
    raw_text: summary,
  };
}

/* ─── Select top papers for analysis (max 5 per phase) ─── */

export function selectMilestonePapers(evidences: PaperEvidence[], count = 2): MilestonePaper[] {
  // Score each paper by evidence richness
  const scored = evidences.map((e) => {
    const cf = (e.parsed?.coreFindings.length || 0);
    const ev = (e.parsed?.evidence.length || 0);
    const mt = (e.parsed?.methods.length || 0);
    const lm = (e.parsed?.limitations.length || 0);
    const gp = (e.parsed?.gaps.length || 0);
    const total = cf + ev + mt + lm + gp;
    return { e, total, cf, ev, mt };
  });
  scored.sort((a, b) => b.total - a.total);

  return scored.slice(0, count).map(({ e, cf, ev, mt }) => {
    let reason = "Contains structured evidence from paper analysis.";
    let excerpt: string | undefined;
    if (cf > 0) {
      reason = "Contains core findings extracted from this paper.";
      excerpt = cleanEvidenceText(e.parsed!.coreFindings[0]).slice(0, 180);
    } else if (ev > 0) {
      reason = "Contains discussion points and evidence from this paper.";
      excerpt = cleanEvidenceText(e.parsed!.evidence[0]).slice(0, 180);
    } else if (mt > 0) {
      reason = "Contains method-related evidence in this phase.";
      excerpt = cleanEvidenceText(e.parsed!.methods[0]).slice(0, 180);
    } else {
      reason = "Selected as a representative paper based on title and keyword coverage.";
    }
    return { paper_id: e.paper_id, title: e.title, authors: e.authors, year: e.year, journal: e.journal, reason, key_excerpt: excerpt };
  });
}

/* ─── Build phase focus ─── */

function buildPhaseFocus(evidences: PaperEvidence[], keywords: string[]): string | null {
  // Count evidence types for richer focus description
  const totalEvidence = evidences.reduce((sum, e) => {
    return sum + (e.parsed?.coreFindings.length || 0) + (e.parsed?.evidence.length || 0) + (e.parsed?.methods.length || 0);
  }, 0);
  const paperCount = evidences.length;

  if (totalEvidence >= 3 && paperCount >= 2) {
    // Build a focus from actual evidence content
    const samples = evidences
      .flatMap((e) => (e.parsed?.evidence || []).map(cleanEvidenceText))
      .filter(Boolean)
      .slice(0, 2);
    if (samples.length > 0) {
      return `Papers in this phase contain structured evidence including discussion points and extracted findings.`;
    }
  }
  if (totalEvidence >= 1) {
    return `This phase contains limited structured evidence from ${paperCount} paper${paperCount > 1 ? "s" : ""}.`;
  }
  // Fallback: keyword-based (only when no structured evidence at all)
  if (keywords.length > 0) {
    return `Available papers in this phase are associated with ${keywords.slice(0, 3).join(", ")}.`;
  }
  return "Not enough structured evidence to infer a clear phase focus.";
}

/* ─── Build key conclusions ─── */

function buildKeyConclusions(evidences: PaperEvidence[]): EvidenceQuote[] {
  const quotes: EvidenceQuote[] = [];
  for (const e of evidences) {
    for (const cf of (e.parsed?.coreFindings || [])) {
      const txt = cleanEvidenceText(cf);
      if (txt) quotes.push({ paper_id: e.paper_id, title: e.title, year: e.year, journal: e.journal, excerpt: txt.slice(0, 200), source_type: "core_finding" });
      if (quotes.length >= 3) return quotes;
    }
  }
  return quotes;
}

/* ─── Build evidence quotes ─── */

function buildEvidenceQuotes(evidences: PaperEvidence[]): EvidenceQuote[] {
  const quotes: EvidenceQuote[] = [];
  for (const e of evidences) {
    for (const ev of (e.parsed?.evidence || [])) {
      const txt = cleanEvidenceText(ev);
      if (txt) quotes.push({ paper_id: e.paper_id, title: e.title, year: e.year, journal: e.journal, excerpt: txt.slice(0, 180), source_type: "evidence" });
      if (quotes.length >= 2) return quotes;
    }
  }
  return quotes;
}

/* ─── Build method signals ─── */

function buildMethodSignals(evidences: PaperEvidence[]): string[] {
  const sig = new Set<string>();
  for (const e of evidences) {
    const text = [e.title, ...(e.parsed?.methods || []), ...(e.parsed?.evidence || [])].join(" ").toLowerCase();
    for (const w of text.split(/[\s,.;:()]+/)) {
      if (METHOD_WORDS.has(w)) sig.add(w);
    }
  }
  return Array.from(sig).slice(0, 6);
}

/* ─── Build open questions ─── */

function buildOpenQuestions(evidences: PaperEvidence[]): EvidenceQuote[] {
  const quotes: EvidenceQuote[] = [];
  for (const e of evidences) {
    for (const lim of [...(e.parsed?.limitations || []), ...(e.parsed?.gaps || [])]) {
      const txt = cleanEvidenceText(lim);
      if (txt) quotes.push({ paper_id: e.paper_id, title: e.title, year: e.year, journal: e.journal, excerpt: txt.slice(0, 180), source_type: "limitation" });
      if (quotes.length >= 3) return quotes;
    }
  }
  return quotes;
}

/* ─── Build change from previous ─── */

function buildChangeFromPrevious(curr: PhaseAnalysis, prev: PhaseAnalysis | null): string | null {
  if (!prev) return "Baseline phase for this topic.";
  const newMethods = curr.method_signals.filter((m) => !prev.method_signals.includes(m));
  const newKW = curr.key_conclusions.length - prev.key_conclusions.length;
  if (newMethods.length >= 2) return `Compared with the previous phase, this phase adds stronger method signals around ${newMethods.slice(0, 3).join(", ")}.`;
  if (newKW > 0 && curr.key_conclusions.length > prev.key_conclusions.length) return `Compared with the previous phase, this phase introduces more structured evidence from paper summaries.`;
  return "No clear directional shift detected from available papers.";
}

/* ─── Build evolution summary ─── */

function buildEvolutionSummary(phases: PhaseAnalysis[]): string {
  const valid = phases.filter((p) => p.focus);
  if (valid.length < 2) return "Topic evolution is based on limited structured evidence. More complete paper summaries may improve this analysis.";
  const first = valid[0], last = valid[valid.length - 1];
  const fm = first.method_signals.slice(0, 2).join(", ");
  const lm = last.method_signals.slice(0, 2).join(", ");
  if (fm && lm && fm !== lm) return `Across phases, method signals shifted from ${fm} to ${lm}.`;
  return `Across phases, this topic shows consistent research themes with ${last.evidence_count} evidence-backed findings in the most recent phase.`;
}

/* ─── Main entry point ─── */

export function buildEvidenceDrivenPhaseAnalysis(
  phases: { phase: string; label: string; year_range: [number, number]; paper_count: number; representative_papers?: any[]; papers?: any[]; keywords?: string[] }[],
  getPaperSummary?: (paperId: string) => Promise<{ text?: string | null } | null>,
): PhaseAnalysis[] {
  return phases.map((ph, i, arr) => {
    const candidates = (ph.representative_papers || ph.papers || []).slice(0, 5);
    const evidences = candidates.map((p: any) => extractPaperEvidence({ ...p, summary: p.summary || p.summary_text || null }));
    const evidenceCount = evidences.filter((e) => e.parsed && (e.parsed.coreFindings.length + e.parsed.evidence.length) > 0).length;

    const keyConclusions = buildKeyConclusions(evidences);
    const evidenceQuotes = buildEvidenceQuotes(evidences);
    const methodSignals = buildMethodSignals(evidences);
    const milestonePapers = selectMilestonePapers(evidences, 2);
    const openQuestions = buildOpenQuestions(evidences);
    const focus = buildPhaseFocus(evidences, ph.keywords || []);

    const confidence: "high" | "medium" | "low" =
      evidenceCount >= 2 ? "high" : evidenceCount >= 1 ? "medium" : "low";

    const prev = i > 0 ? arr[i - 1] as any : null;
    const prevAnalysis = prev ? ({
      method_signals: buildMethodSignals((prev.representative_papers || prev.papers || []).slice(0, 5).map((p: any) => extractPaperEvidence({ ...p, summary: null }))),
      key_conclusions: [] as EvidenceQuote[],
    } as PhaseAnalysis) : null;

    const self: PhaseAnalysis = {
      phase: ph.phase as "early" | "middle" | "recent",
      label: ph.label,
      year_range: ph.year_range,
      paper_count: ph.paper_count,
      focus,
      key_conclusions: keyConclusions,
      evidence_quotes: evidenceQuotes,
      method_signals: methodSignals,
      milestone_papers: milestonePapers,
      change_from_previous: null,
      open_questions: openQuestions,
      confidence,
      evidence_count: evidenceCount,
    };
    self.change_from_previous = buildChangeFromPrevious(self, prevAnalysis);
    return self;
  });
}

export { buildEvolutionSummary };
