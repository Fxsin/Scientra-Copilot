/* ── Concept Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * A ConceptEntity represents an abstract scientific concept that
 * emerges from aggregating multiple pieces of evidence. Concepts
 * sit above individual findings and below topics in the hierarchy.
 *
 *   EvidenceEntity → ConceptEntity → TopicEntity
 */
export interface ConceptEntity extends BaseEntity {
  entityType: Extract<EntityType, "concept">;

  /** Formal definition of the concept */
  definition: string;

  /** Evidence that supports this concept */
  supportingEvidenceIds: string[];

  /** Evidence that contradicts this concept */
  contradictingEvidenceIds: string[];

  /** Related concepts that form a cluster or hierarchy */
  relatedConceptIds: string[];

  /** How well-established this concept is in the field */
  maturity: ConceptMaturity;

  /** Methods used to establish this concept */
  methodIds: string[];

  /** Papers that are foundational to this concept */
  foundationalPaperIds: string[];

  /** Open questions about this concept */
  openQuestions: string[];
}

export type ConceptMaturity =
  | "established"       // Widely accepted, textbook-level
  | "consolidating"     // Mostly accepted, some debate
  | "emerging"          // Recently proposed, limited validation
  | "controversial"     // Actively debated
  | "speculative";      // Proposed but untested
