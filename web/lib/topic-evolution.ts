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
  source_type: "core_finding" | "evidence" | "method" | "limitation" | "gap" | "summary" | "title";
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

export function extractPaperEvidence(paper: {
  paper_id: string; title?: string | null; authors?: string[] | null;
  year?: number | null; journal?: string | null; summary?: string | null;
  evidence?: any | null;
}): PaperEvidence {
  const title = paper.title || "";

  // Priority: evidence.json > summary > title fallback
  const ev = paper.evidence;
  if (ev && ev.status !== "failed") {
    // Build parsed-like structure from evidence fields
    const cf: string[] = [];
    const evItems: string[] = [];
    const mt: string[] = [];
    const lm: string[] = [];
    const gp: string[] = [];
    for (const c of (ev.core_findings || [])) {
      const t = typeof c === "string" ? c : (c.finding || c.text || "");
      if (t) cf.push(t.slice(0, 300));
    }
    for (const r of (ev.key_results || [])) {
      const t = typeof r === "string" ? r : (r.result || r.text || "");
      if (t) evItems.push(t.slice(0, 300));
    }
    for (const m of (ev.methods || [])) {
      const t = typeof m === "string" ? m : (m.name || m.text || "");
      if (t) mt.push(t.slice(0, 200));
    }
    for (const l of (ev.limitations || [])) {
      const t = typeof l === "string" ? l : (l.limitation || l.text || "");
      if (t) lm.push(t.slice(0, 300));
    }
    for (const g of (ev.open_questions || [])) {
      const t = typeof g === "string" ? g : (g.question || g.text || "");
      if (t) gp.push(t.slice(0, 300));
    }
    // Also include discussion_points as evidence
    for (const d of (ev.discussion_points || [])) {
      const t = typeof d === "string" ? d : (d.point || d.text || "");
      if (t) evItems.push(t.slice(0, 300));
    }

    const hasEvidence = cf.length + evItems.length + mt.length > 0;
    return {
      paper_id: paper.paper_id, title, year: paper.year, journal: paper.journal || null,
      authors: paper.authors || [],
      parsed: hasEvidence ? { takeaway: cf[0] || null, coreFindings: cf, evidence: evItems, methods: mt, limitations: lm, gaps: gp, others: [] } : null,
      raw_text: "[evidence.json]" as any,
    };
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
  const withEvidence = evidences.filter((e) => e.parsed && (e.parsed.coreFindings.length + e.parsed.evidence.length + e.parsed.methods.length) > 0);
  const candidates = withEvidence.length >= count ? withEvidence : [...withEvidence, ...evidences.filter((e) => !withEvidence.includes(e))];
  return candidates.slice(0, count).map((e) => {
    const hasCF = (e.parsed?.coreFindings.length || 0) > 0;
    const hasEV = (e.parsed?.evidence.length || 0) > 0;
    const hasMT = (e.parsed?.methods.length || 0) > 0;
    let reason = "Selected as a representative paper based on title and keyword coverage.";
    let excerpt: string | undefined;
    if (hasCF) { reason = "Selected because it contributes a core finding in this phase."; excerpt = cleanEvidenceText(e.parsed!.coreFindings[0]).slice(0, 180); }
    else if (hasMT) { reason = "Selected because it contributes method-related evidence in this phase."; excerpt = cleanEvidenceText(e.parsed!.methods[0]).slice(0, 180); }
    else if (hasEV) { reason = "Selected because it provides evidence used in this phase analysis."; excerpt = cleanEvidenceText(e.parsed!.evidence[0]).slice(0, 180); }
    return { paper_id: e.paper_id, title: e.title, authors: e.authors, year: e.year, journal: e.journal, reason, key_excerpt: excerpt };
  });
}

/* ─── Build phase focus ─── */

function buildPhaseFocus(evidences: PaperEvidence[], keywords: string[]): string | null {
  const allCF = evidences.flatMap((e) => (e.parsed?.coreFindings || []).map(cleanEvidenceText)).filter(Boolean);
  if (allCF.length >= 2) {
    const key = keywords.slice(0, 3).join(", ");
    return key ? `Available papers in this phase are mainly associated with ${key}.` : `Papers in this phase share recurring themes in their core findings.`;
  }
  if (allCF.length === 1) return allCF[0].slice(0, 200);
  if (keywords.length > 0) return `Available papers in this phase are mainly associated with ${keywords.slice(0, 3).join(", ")}.`;
  return null;
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
