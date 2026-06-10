/* ── Gap Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * A GapEntity represents a research gap — something we do not know
 * that matters scientifically. Gaps are identified by analyzing what
 * topics claim to cover vs. what evidence actually supports.
 *
 *   TopicEntity → GapEntity → HypothesisEntity
 */
export interface GapEntity extends BaseEntity {
  entityType: Extract<EntityType, "research_gap">;

  /** Detailed description of the gap */
  description: string;

  /** Classification */
  gapType: GapType;

  /** What the literature currently says */
  knownSummary: string;

  /** What is missing */
  missingSummary: string;

  /** Why filling this gap matters */
  whyItMatters: string;

  /** Topic(s) this gap falls under */
  topicIds: string[];

  /** Concepts implicated in this gap */
  conceptIds: string[];

  /** Papers that provide evidence (or lack thereof) */
  paperIds: string[];

  /** How this gap was detected */
  detectionMethod: "evidence_absence" | "method_limitation" | "species_blind_spot" | "contradiction" | "computational";

  /** Priority scoring */
  priority: GapPriority;

  /** Hypotheses that address this gap */
  hypothesisIds: string[];
}

export type GapType =
  | "evidence_gap"          // Missing experimental data
  | "method_gap"            // No adequate method exists
  | "species_model_gap"     // Data only in one species/model
  | "contradiction_gap";    // Conflicting evidence

export interface GapPriority {
  /** 0–100 weighted score */
  score: number;
  /** Scientific importance (0–100) */
  impact: number;
  /** How confident we are this is a real gap (0–100) */
  confidence: number;
  /** How feasible to address (0–100) */
  feasibility: number;
  /** Computed as: 0.4 × impact + 0.35 × confidence + 0.25 × feasibility */
}
