/* ── Evidence Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * An EvidenceEntity is a single, atomic piece of evidence extracted
 * from one or more papers. It is the bridge between raw paper content
 * and higher-level concepts.
 *
 *   PaperEntity.finding → EvidenceEntity → ConceptEntity
 */
export interface EvidenceEntity extends BaseEntity {
  entityType: Extract<EntityType, "evidence">;

  /** The evidence statement — what was observed */
  statement: string;

  /** Type classification */
  evidenceType: EvidenceType;

  /** Direction: does this evidence support, contradict, or contextualize? */
  direction: EvidenceDirection;

  /** Source paper(s) this evidence is extracted from */
  sourcePaperIds: string[];

  /** Which finding(s) in the source paper(s) this maps to */
  sourceFindingRefs: string[];

  /** The method(s) used to generate this evidence */
  methodIds: string[];

  /** Strength assessment */
  strength: EvidenceStrength;

  /** Whether this evidence has been independently replicated */
  replicationStatus: "unreplicated" | "replicated" | "failed_replication" | "not_applicable";
}

/* ── Evidence classification ── */

export type EvidenceType =
  | "experimental"       // Wet-lab experiment
  | "computational"      // In silico prediction / simulation
  | "observational"      // Field observation / survey
  | "meta_analysis"      // Aggregated from multiple studies
  | "review";            // Narrative review synthesis

export type EvidenceDirection =
  | "supporting"         // Supports a concept or hypothesis
  | "contradicting"      // Contradicts a concept or hypothesis
  | "contextualizing"    // Provides context but doesn't directly test
  | "neutral";           // Reports without taking a position

export interface EvidenceStrength {
  /** 0–100 overall confidence */
  score: number;
  /** Sample size if applicable */
  sampleSize?: number;
  /** Statistical significance level if reported */
  significance?: string;
  /** Whether key controls were present */
  hasControls: boolean;
  /** Whether the method is well-established in the field */
  methodMaturity: "established" | "emerging" | "novel";
}
