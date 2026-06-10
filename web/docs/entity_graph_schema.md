# Research OS — Entity Graph Schema V2

> Data-model-only design. No UI changes. No new routes.  
> All entities share `BaseEntity` and are linked through typed ID arrays.

---

## 1. Entity Types

| EntityType   | Prefix       | Example ID                              | Count (mock) |
|-------------|-------------|------------------------------------------|--------------|
| `paper`      | `paper_`     | `paper_jiang_2024`                       | 5            |
| `concept`    | `concept_`   | `concept_vip3a`                          | 12           |
| `method`     | `method_`    | `method_bbmv_binding`                    | 8            |
| `evidence`   | `evidence_`  | `evidence_vip3a_binds_fgfr`              | 14           |
| `topic`      | `topic_`     | `topic_pore_formation`                   | 25           |
| `research_gap` | `gap_`    | `gap_vip3a_pore_structure`               | 6            |
| `hypothesis` | `hypothesis_`| `hypothesis_domain_i_pore_formation`     | 3            |

---

## 2. BaseEntity Interface

Every entity in the system shares this minimal contract:

```typescript
interface BaseEntity {
  entityId: string;
  entityType: EntityType;
  title: string;
  summary: string;
  linkedTopicIds: string[];
  linkedConceptIds: string[];
  linkedEvidenceIds: string[];
  linkedPaperIds: string[];
  linkedGapIds: string[];
}
```

---

## 3. Entity-Specific Interfaces

### 3.1 Paper

```typescript
interface ResearchPaper {
  id: string;                    // stable: "paper_..."
  title: string;
  authors: string[];
  year: number;
  journal: string;
  doi?: string;
  abstract?: string;
  keyFindings: string[];         // bullet-point findings
  methods: string[];
  linkedTopicIds: string[];
  linkedConceptIds: string[];
  linkedEvidenceIds: string[];
  linkedGapIds: string[];
  relevanceScore?: number;       // 0–100
  evidenceRole?: EvidenceRole;   // direct | indirect | contradictory | background
}
```

### 3.2 Concept

Already modeled as `RINetworkNode` with `entityType: "concept"` in Knowledge Network:

```typescript
interface RINetworkNode {
  id: string;                    // "concept_vip3a"
  entityId: string;
  entityType: "concept" | "topic" | "research_gap" | "method" | "evidence" | "paper";
  label: string;
  type: "Concept" | "Method" | "Finding" | "Paper";
  color: string;
  size: number;
  linkedTopicIds?: string[];
  linkedConceptIds?: string[];
  linkedGapIds?: string[];
  linkedPaperIds?: string[];
}
```

### 3.3 Method

Modeled as `RINetworkNode` with `entityType: "method"`.

### 3.4 Evidence

Modeled as `RINetworkNode` with `entityType: "evidence"`.  
Represents individual findings, claims, or data points extracted from papers.

### 3.5 Topic

```typescript
interface TopicTreeNode {
  id: string;                    // "topic_pore_formation"
  label: string;
  children?: TopicTreeNode[];
}

interface TopicDetail {
  id: string;
  definition: string;
  keyFindings: string[];
  representativePapers: string[];
  relatedMethods: string[];
  relatedTopics: string[];
  unresolvedQuestions: string[];
  evidenceStrength: number;
  recentActivity: string;
  connectedGaps: string[];
  suggestedReadingOrder: string[];
}
```

### 3.6 Research Gap

```typescript
interface ResearchGapItem {
  id: string;                    // "gap_vip3a_pore_structure"
  title: string;
  gapType: GapType;
  description: string;
  knownSummary: string;
  missingSummary: string;
  whyItMatters: string;
  evidenceBasis: EvidenceBasis;
  confidence: number;
  impact: number;
  feasibility: number;
  suggestedNextStep: string;
  suggestedValidationPath: string;
  linkedTopicIds: string[];
  linkedConceptIds: string[];
  linkedPaperIds: string[];
  linkedEvidenceIds: string[];
}
```

### 3.7 Hypothesis — **NEW in V2**

```typescript
interface Hypothesis extends BaseEntity {
  entityType: "hypothesis";
  statement: string;             // The claim being tested
  proposedBy: string;            // Author lineage or source
  status: "untested"
         | "supported"
         | "refuted"
         | "partially_supported"
         | "contradicted";
  supportingEvidenceIds: string[];
  contradictingEvidenceIds: string[];
  targetGapIds: string[];        // Gaps this hypothesis aims to address
  validationPath: string;        // Experiment to validate or refute
}
```

---

## 4. Entity Graph — Relationship Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                      ENTITY GRAPH                                │
│                                                                  │
│   PAPER ──────────────────────────────────────────────────────┐  │
│   │                                                           │  │
│   │ provides                                                   │  │
│   ▼                                                           │  │
│   EVIDENCE ──────────────────────────────────────────────────┐│  │
│   │                                                          ││  │
│   │ supports / contradicts / contextualizes                  ││  │
│   ▼                                                          ││  │
│   CONCEPT ──────────────────────────────────────────────────┐││  │
│   │                                                         │││  │
│   │ organizes into                                          │││  │
│   ▼                                                         │││  │
│   TOPIC ───────────────────────────────────────────────────┐│││  │
│   │                                                        ││││  │
│   │ reveals                                                ││││  │
│   ▼                                                        ││││  │
│   RESEARCH GAP ───────────────────────────────────────────┐││││  │
│   │                                                       │││││  │
│   │ generates / is addressed by                            │││││  │
│   ▼                                                       │││││  │
│   HYPOTHESIS ────────────────────────────────────────────┐│││││  │
│   │                                                      ││││││  │
│   │ specifies                                            ││││││  │
│   ▼                                                      ││││││  │
│   VALIDATION PATH                                        ││││││  │
│   │                                                      ││││││  │
│   │ (feeds back to)                                      ││││││  │
│   └──────────────────────────────────────────────────────┘│││││  │
│                                                           │││││  │
│   METHOD ◄──── used by ──── PAPER ───► METHOD             │││││  │
│                                                           │││││  │
│   (all entities cross-linked via linked*Ids arrays)       │││││  │
└───────────────────────────────────────────────────────────────┘││││  │
                                                                  ││││  │
```

### 4.1 Edge Semantics

| From        | To             | Relationship                          | Via Field              |
|------------|----------------|---------------------------------------|------------------------|
| Paper      | Evidence       | Paper provides evidence               | `linkedEvidenceIds`    |
| Evidence   | Concept        | Evidence supports/contradicts concept | `linkedConceptIds`     |
| Concept    | Topic          | Concept organizes into topic          | `linkedTopicIds`       |
| Topic      | Research Gap   | Topic reveals gap                     | `linkedGapIds`         |
| Research Gap | Hypothesis   | Gap generates hypothesis              | `linkedGapIds` (on Hypothesis) |
| Hypothesis | Validation Path| Hypothesis specifies validation       | `validationPath`       |
| Paper      | Topic          | Paper addresses topic                 | `linkedTopicIds`       |
| Paper      | Concept        | Paper discusses concept               | `linkedConceptIds`     |
| Paper      | Research Gap   | Paper contributes evidence to gap     | `linkedGapIds`         |
| Method     | Paper          | Paper uses method                     | `methods` (on Paper)   |
| Method     | Concept        | Method validates concept              | `linkedConceptIds`     |

### 4.2 Backward Edges (query helpers)

```typescript
getPapersByGapId(gapId)       // Paper → Gap
getPapersByTopicId(topicId)   // Paper → Topic
getPapersByConceptId(id)      // Paper → Concept
getPapersByEvidenceId(id)     // Paper → Evidence
getHypothesesByGapId(gapId)   // Hypothesis → Gap
getResearchGapsByTopicId(id)  // Gap → Topic
getResearchGapsByConceptId(id)// Gap → Concept
getResearchGapsByNode(node)   // Gap → Network Node
resolveEntityById(entityId)   // Any entity → BaseEntity
```

---

## 5. Concrete Examples

### 5.1 Paper → Evidence → Concept → Topic → Gap → Hypothesis → Validation Path

```
paper_jiang_2024
  │  (Sf-FGFR as Vip3Aa receptor)
  │
  ├── provides ──→ evidence_vip3a_binds_fgfr
  │                 (Vip3A binds Sf-FGFR)
  │
  ├── supports ──→ concept_vip3a
  │                 concept_receptor_binding
  │
  ├── organizes ──→ topic_pore_formation
  │                  topic_binding_assays
  │
  ├── reveals ────→ gap_vip3a_pore_structure
  │                  gap_vip3a_receptor_in_vivo
  │
  ├── generates ──→ hypothesis_sr_c_primary_vip3a_receptor
  │                  (SR-C is primary functional Vip3Aa receptor)
  │
  └── validates ──→ "Generate SR-C KO line, bioassay at 6 concentrations"
                     (Validation Path)
```

### 5.2 Contradiction Mapping

```
evidence_cry_vip_competition_bbmv    (supports shared receptors)
          ↕ CONTRADICTS
evidence_no_cross_resistance          (supports distinct receptors)

          ↓ both feed into

gap_cry_vip_receptor_contradiction
          ↓ addressed by

hypothesis_vip3a_cry_distinct_receptors
  status: "partially_supported"
  validationPath: "2×2 factorial competition SPR experiment"
```

---

## 6. Entity Counts (Current Mock Data)

```
Papers:      5
Concepts:    12
Methods:     8
Evidences:   14
Topics:      25
Gaps:        6
Hypotheses:  3
─────────────────
Total:       73 entities
```

---

## 7. Next Steps (Not This Pass)

Future schema refinements reserved for later passes:

- Add `evidenceRole` field to every linked ID relationship (not just Paper)
- Normalize Concept and Topic entities into full BaseEntity extensions with their own mock arrays
- Add time-series tracking per entity (when was it added, what changed)
- Add confidence propagation through the graph (Paper.confidence → Evidence → Gap.confidence)
- Implement graph traversal UI (click a Gap → see the entire evidence chain)
