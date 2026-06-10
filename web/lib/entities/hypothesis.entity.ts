/* ── Hypothesis Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * A HypothesisEntity represents a testable scientific hypothesis
 * generated from one or more research gaps. It is the most downstream
 * entity in the extraction pipeline and connects directly to
 * experimental design.
 *
 *   GapEntity → HypothesisEntity → Validation Path
 */
export interface HypothesisEntity extends BaseEntity {
  entityType: Extract<EntityType, "hypothesis">;

  /** The precise, falsifiable hypothesis statement */
  statement: string;

  /** Who proposed it or where it originates */
  proposedBy: string;

  /** Current empirical status */
  status: HypothesisStatus;

  /** Evidence that supports this hypothesis */
  supportingEvidenceIds: string[];

  /** Evidence that contradicts this hypothesis */
  contradictingEvidenceIds: string[];

  /** Gap(s) this hypothesis addresses */
  targetGapIds: string[];

  /** Concepts relevant to testing this hypothesis */
  relatedConceptIds: string[];

  /** Papers that discuss or test this hypothesis */
  relatedPaperIds: string[];

  /** Methods that would be used to test this */
  testableByMethodIds: string[];

  /** A step-by-step experimental plan to validate or refute */
  validationPath: string;

  /** Whether the validation path has been designed */
  validationReadiness: "designed" | "feasibility_assessed" | "not_designed";

  /** Estimated resources needed */
  resourceEstimate?: ResourceEstimate;
}

export type HypothesisStatus =
  | "untested"
  | "supported"
  | "refuted"
  | "partially_supported"
  | "contradicted";

export interface ResourceEstimate {
  /** Rough time estimate */
  timeline: string;          // e.g. "6–12 months"
  /** Required expertise */
  expertise: string[];       // e.g. ["cryo-EM", "SPR"]
  /** Key equipment */
  equipment: string[];       // e.g. ["300 kV cryo-TEM"]
  /** Estimated cost range */
  costRange: string;         // e.g. "$50K–$150K"
}
