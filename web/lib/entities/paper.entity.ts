/* ── Paper Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * A PaperEntity represents a single academic paper that has been
 * structurally extracted — beyond simple metadata into a machine-readable
 * research object with questions, hypotheses, findings, methods,
 * limitations, and future work.
 *
 * This is the entry point of the extraction pipeline:
 *   PDF → PaperEntity → Evidence → Concept → Topic → Gap → Hypothesis
 */
export interface PaperEntity extends BaseEntity {
  entityType: Extract<EntityType, "paper">;

  /* ── Bibliographic ── */
  title: string;
  authors: Author[];
  year: number;
  journal: string;
  doi?: string;
  abstract: string;

  /* ── Research framing ── */
  /** The scientific question this paper addresses */
  question: string;
  /** Explicit or implicit hypotheses tested */
  hypotheses: PaperHypothesis[];
  /** The methods used (extracted, not just listed) */
  methods: ExtractedMethod[];

  /* ── Results ── */
  /** Core findings with evidence links */
  findings: PaperFinding[];

  /* ── Critical appraisal ── */
  /** Explicit limitations acknowledged or detected */
  limitations: string[];
  /** What the authors suggest as next steps */
  futureWork: string[];

  /* ── Extraction metadata ── */
  extractionStatus: ExtractionStatus;
}

/* ── Sub-types ── */

export interface Author {
  name: string;
  affiliation?: string;
  isCorresponding?: boolean;
}

export interface PaperHypothesis {
  /** The hypothesis statement */
  statement: string;
  /** Was it explicitly stated or inferred? */
  source: "explicit" | "inferred";
  /** Sentence or paragraph reference in the paper */
  textRef?: string;
  /** Outcome after the paper's experiments */
  result: "supported" | "refuted" | "inconclusive" | "not_tested";
}

export interface ExtractedMethod {
  name: string;
  category: "binding_assay" | "structural" | "genetic" | "bioassay" | "computational" | "other";
  /** Brief description of what was done */
  description: string;
  /** Equipment or reagents mentioned */
  reagents?: string[];
}

export interface PaperFinding {
  /** One-sentence finding */
  statement: string;
  /** What type of evidence this provides */
  evidenceType: "direct" | "indirect" | "correlational" | "negative";
  /** Where in the paper this is reported */
  location?: string; // e.g. "Figure 3B", "Results §2.4"
  /** Confidence in this finding (0–100) */
  confidence: number;
}

export type ExtractionStatus =
  | "raw"           // PDF ingested, not yet processed
  | "metadata"      // Title, authors, abstract extracted
  | "structured"    // Full structural extraction done
  | "linked"        // Linked to entity graph (topic/gap/hypothesis IDs populated)
  | "curated";      // Human-reviewed and corrected
