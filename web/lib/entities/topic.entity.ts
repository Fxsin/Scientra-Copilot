/* ── Topic Entity Schema V1 ── */

import type { BaseEntity, EntityType } from "@/lib/data/researchIntelligenceMock";

/**
 * A TopicEntity represents a research topic — a coherent area of
 * scientific inquiry that organizes multiple concepts. Topics are
 * the primary navigation unit in the Topic Explorer.
 *
 *   ConceptEntity → TopicEntity → GapEntity
 */
export interface TopicEntity extends BaseEntity {
  entityType: Extract<EntityType, "topic">;

  /** Formal definition of the topic */
  definition: string;

  /** Concepts that fall under this topic */
  childConceptIds: string[];

  /** Parent topics (if hierarchical) */
  parentTopicIds: string[];

  /** Evidence strength aggregated from child concepts */
  aggregatedEvidenceStrength: number; // 0–100

  /** How active is research in this topic */
  activityLevel: ActivityLevel;

  /** Key representative papers */
  representativePaperIds: string[];

  /** Methods commonly used in this topic area */
  commonMethodIds: string[];

  /** Unresolved questions at the topic level */
  unresolvedQuestions: string[];

  /** Gaps identified within this topic */
  gapIds: string[];

  /** Suggested reading order for newcomers */
  readingOrder: string[]; // paper IDs
}

export interface ActivityLevel {
  /** 0–100 growth score */
  growthScore: number;
  /** Recent paper count (last 2 years) */
  recentPaperCount: number;
  /** Trend direction */
  trend: "rising" | "stable" | "declining" | "emerging";
}
