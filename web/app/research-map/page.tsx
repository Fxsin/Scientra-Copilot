"use client";

import { ResearchMapView } from "@/components/research-map-view";
import { DemoBanner } from "@/components/demo-banner";
import { useApiWithFallback } from "@/lib/use-api";
import { getResearchMap } from "@/lib/api";
import {
  mockTopics,
  mockHotTopics,
  mockGapCards,
} from "@/lib/data/researchIntelligenceMock";
import type { ResearchMapResponse } from "@/lib/types";

function buildMockData(): ResearchMapResponse {
  const mature_topics = mockTopics.map((t) => ({
    cluster_id: t.id,
    name: t.name,
    paper_count: t.count,
    year_range: "2015–2025",
    method_diversity: t.representatives.length,
    key_methods: [],
    top_tags: t.representatives,
    confidence: "High",
    summary: t.representatives.join("; "),
    recent_count: Math.floor(t.count * 0.6),
    growth_rate: "Stable",
    gap_tags: [],
    connected_to: [],
    opportunity: "",
  }));

  const growing_topics = mockHotTopics.map((t) => ({
    cluster_id: t.id,
    name: t.name,
    paper_count: t.count,
    year_range: "2020–2025",
    method_diversity: 2,
    key_methods: [],
    top_tags: t.representatives,
    confidence: "High",
    summary: t.representatives.join("; "),
    recent_count: t.count,
    growth_rate: "Growing",
    gap_tags: [],
    connected_to: [],
    opportunity: "",
  }));

  const gap_topics = mockGapCards.map((t) => ({
    cluster_id: t.id,
    name: t.name,
    paper_count: t.count,
    year_range: "2022–2025",
    method_diversity: 1,
    key_methods: [],
    top_tags: t.representatives,
    confidence: "Medium",
    summary: t.representatives.join("; "),
    recent_count: t.count,
    growth_rate: "Emerging",
    gap_tags: t.representatives,
    connected_to: [],
    opportunity: "High potential research opportunity",
  }));

  const topic_relationships = [
    {
      source: "Cry toxin mechanism",
      target: "Vip3A mode of action",
      shared_tags: ["Pore formation", "Receptor binding", "Midgut"],
      strength: 5,
    },
    {
      source: "Cry toxin mechanism",
      target: "Insect resistance mechanisms",
      shared_tags: ["Cadherin", "ABCC2", "Resistance"],
      strength: 4,
    },
    {
      source: "Vip3A mode of action",
      target: "Insect resistance mechanisms",
      shared_tags: ["Receptor mutation", "Cross-resistance"],
      strength: 3,
    },
    {
      source: "Bt structural biology",
      target: "Cry toxin mechanism",
      shared_tags: ["Cryo-EM", "Pore structure", "Domain I"],
      strength: 4,
    },
  ];

  return {
    mature_topics,
    growing_topics,
    gap_topics,
    cluster_stats: [...mature_topics, ...growing_topics],
    topic_relationships,
  };
}

export default function ResearchMapPage() {
  const { data, isDemo } = useApiWithFallback(
    getResearchMap,
    buildMockData(),
  );

  return (
    <>
      <DemoBanner show={isDemo} />
      <ResearchMapView data={data} />
    </>
  );
}
