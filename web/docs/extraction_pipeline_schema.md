# Research OS — Extraction Pipeline Schema V1

> Data-model-only design. No UI changes. No new routes.

---

## 1. Pipeline Overview

```
                        ┌─────────────────────┐
                        │        PDF           │
                        │  (raw paper file)    │
                        └──────────┬──────────┘
                                   │ parse + structure
                                   ▼
                        ┌─────────────────────┐
                        │    PaperEntity       │
                        │  question            │
                        │  hypotheses          │
                        │  methods             │
                        │  findings            │
                        │  limitations         │
                        │  futureWork          │
                        └──────────┬──────────┘
                                   │ extract evidence
                                   ▼
                        ┌─────────────────────┐
                        │   EvidenceEntity     │
                        │  statement           │
                        │  evidenceType        │
                        │  direction           │
                        │  strength            │
                        │  sourcePaperIds      │
                        └──────────┬──────────┘
                                   │ aggregate + synthesize
                                   ▼
                        ┌─────────────────────┐
                        │   ConceptEntity      │
                        │  definition          │
                        │  maturity            │
                        │  supportingEvidence  │
                        │  contradictingEvid.  │
                        └──────────┬──────────┘
                                   │ organize hierarchically
                                   ▼
                        ┌─────────────────────┐
                        │   TopicEntity        │
                        │  definition          │
                        │  childConcepts       │
                        │  activityLevel       │
                        │  unresolvedQs        │
                        └──────────┬──────────┘
                                   │ detect gaps
                                   ▼
                        ┌─────────────────────┐
                        │    GapEntity         │
                        │  gapType             │
                        │  knownSummary        │
                        │  missingSummary      │
                        │  priority            │
                        │  detectionMethod     │
                        └──────────┬──────────┘
                                   │ generate hypotheses
                                   ▼
                        ┌─────────────────────┐
                        │  HypothesisEntity    │
                        │  statement           │
                        │  status              │
                        │  validationPath      │
                        │  resourceEstimate    │
                        └─────────────────────┘
```

---

## 2. Stage Details

### Stage 0: PDF → PaperEntity

**Input:** Raw PDF file  
**Output:** `PaperEntity` (status: `structured`)

**What happens:**
- Bibliographic metadata extracted (title, authors, year, journal, DOI)
- Abstract parsed
- Full text section-analyzed
- Research question identified (from abstract/introduction)
- Hypotheses extracted (explicit or inferred)
- Methods cataloged with category tags
- Findings extracted with confidence scores
- Limitations section parsed
- Future work section parsed

**Extraction methods:** LLM-based or rule-based NLP + regex

### Stage 1: PaperEntity → EvidenceEntity[]

**Input:** `PaperEntity` with findings  
**Output:** `EvidenceEntity[]`

**What happens:**
- Each finding becomes an `EvidenceEntity`
- `evidenceType` classified (experimental/computational/observational)
- `direction` assigned (supporting/contradicting/contextualizing)
- `strength` assessed (score, sampleSize, significance, controls)
- `methodIds` linked to methods used
- `sourcePaperIds` populated

### Stage 2: EvidenceEntity[] → ConceptEntity[]

**Input:** `EvidenceEntity[]` across multiple papers  
**Output:** `ConceptEntity[]`

**What happens:**
- Evidence clustered by semantic similarity
- Concepts defined from evidence clusters
- `maturity` assessed based on evidence quantity + quality
- Supporting/contradicting evidence linked
- Related concepts linked
- Open questions generated from evidence gaps

### Stage 3: ConceptEntity[] → TopicEntity[]

**Input:** `ConceptEntity[]`  
**Output:** `TopicEntity[]`

**What happens:**
- Concepts organized into topic hierarchy
- `activityLevel` computed from paper recency + count
- Representative papers selected
- Common methods identified
- Unresolved questions aggregated from concept open questions
- Reading order generated for newcomers

### Stage 4: TopicEntity[] → GapEntity[]

**Input:** `TopicEntity[]` with linked concepts + evidence  
**Output:** `GapEntity[]`

**What happens:**
- Gap detection by comparing topic claims vs. evidence coverage
- `detectionMethod` classified:
  - `evidence_absence` — topic claims exist but evidence missing
  - `method_limitation` — no adequate method exists
  - `species_blind_spot` — data only in limited models
  - `contradiction` — conflicting evidence to resolve
- `priority` computed: 0.4 × impact + 0.35 × confidence + 0.25 × feasibility
- Hypotheses linked (if already generated)

### Stage 5: GapEntity[] → HypothesisEntity[]

**Input:** `GapEntity[]`  
**Output:** `HypothesisEntity[]`

**What happens:**
- For each gap, generate falsifiable hypotheses
- `validationPath` designed with step-by-step experimental plan
- `resourceEstimate` computed (timeline, expertise, equipment, cost)
- `testableByMethodIds` linked to specific methods
- `validationReadiness` assessed

---

## 3. Entity Schemas (TypeScript Interfaces)

All entity interfaces are defined in:

```
web/lib/entities/
├── index.ts               // Barrel export
├── paper.entity.ts         // PaperEntity
├── evidence.entity.ts      // EvidenceEntity
├── concept.entity.ts       // ConceptEntity
├── topic.entity.ts         // TopicEntity
├── gap.entity.ts           // GapEntity
└── hypothesis.entity.ts    // HypothesisEntity
```

Each entity extends `BaseEntity` from `@/lib/data/researchIntelligenceMock`:

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

## 4. Real Paper JSON Example

Below is a structured `PaperEntity` for a real published paper.  
This shows the expected output of Stage 0 (PDF → PaperEntity).

```json
{
  "entityId": "paper_jiang_2024",
  "entityType": "paper",
  "title": "Identification of Sf-FGFR as a functional receptor for Vip3Aa in Spodoptera frugiperda",
  "summary": "Sf-FGFR was identified as a Vip3Aa binding protein by pull-down and mass spectrometry. CRISPR knockout of Sf-FGFR in Sf9 cells reduced Vip3Aa binding by ~70%, making it the first validated Vip3A receptor candidate.",
  "authors": [
    { "name": "Jiang, L.", "affiliation": "Chinese Academy of Agricultural Sciences", "isCorresponding": true },
    { "name": "Wang, Y.", "affiliation": "Chinese Academy of Agricultural Sciences" },
    { "name": "Zhang, H.", "affiliation": "Nanjing Agricultural University" },
    { "name": "Liu, X.", "affiliation": "Chinese Academy of Agricultural Sciences" }
  ],
  "year": 2024,
  "journal": "Insect Biochemistry and Molecular Biology",
  "doi": "",
  "abstract": "The vegetative insecticidal protein Vip3Aa from Bacillus thuringiensis is a key component of second-generation Bt crops...",

  "question": "What is the molecular identity of the functional Vip3Aa receptor in Spodoptera frugiperda midgut cells?",

  "hypotheses": [
    {
      "statement": "Sf-FGFR is a functional receptor that mediates Vip3Aa binding and cytotoxicity in Sf9 cells.",
      "source": "explicit",
      "textRef": "Introduction, paragraph 4",
      "result": "supported"
    }
  ],

  "methods": [
    {
      "name": "Pull-down assay",
      "category": "binding_assay",
      "description": "Vip3Aa-biotin incubated with Sf9 BBMV proteins, streptavidin pull-down, SDS-PAGE, silver stain.",
      "reagents": ["Vip3Aa-biotin", "streptavidin beads"]
    },
    {
      "name": "Mass spectrometry",
      "category": "computational",
      "description": "Excised bands digested with trypsin, analyzed by LC-MS/MS, searched against S. frugiperda proteome.",
      "reagents": ["trypsin"]
    },
    {
      "name": "CRISPR-Cas9 knockout",
      "category": "genetic",
      "description": "sgRNAs targeting Sf-FGFR exon 3 transfected into Sf9 cells, clonal selection, sequencing confirmation.",
      "reagents": ["Cas9 protein", "sgRNA"]
    },
    {
      "name": "Surface plasmon resonance (SPR)",
      "category": "binding_assay",
      "description": "Sf-FGFR immobilized on CM5 chip, Vip3Aa flowed as analyte at 5 concentrations (1–100 nM), fitted to 1:1 Langmuir model.",
      "reagents": ["CM5 chip", "Vip3Aa"]
    }
  ],

  "findings": [
    {
      "statement": "Sf-FGFR was identified as a Vip3Aa binding protein by pull-down and mass spectrometry.",
      "evidenceType": "direct",
      "location": "Figure 1, Results §2.1",
      "confidence": 90
    },
    {
      "statement": "CRISPR knockout of Sf-FGFR in Sf9 cells reduced Vip3Aa binding by ~70%.",
      "evidenceType": "direct",
      "location": "Figure 3A, Results §2.3",
      "confidence": 85
    },
    {
      "statement": "SPR showed Vip3Aa binds Sf-FGFR with Kd ~ 52 nM.",
      "evidenceType": "direct",
      "location": "Figure 4B, Results §2.4",
      "confidence": 80
    }
  ],

  "limitations": [
    "Receptor validation was performed only in Sf9 cells — no whole-insect knockout data.",
    "Binding reduction of 70% suggests additional receptors may exist.",
    "Only one lepidopteran species (S. frugiperda) was tested.",
    "SPR was performed with immobilized receptor; solution-phase binding not measured."
  ],

  "futureWork": [
    "Generate whole-insect Sf-FGFR knockout line and measure Vip3Aa susceptibility in vivo.",
    "Test whether Sf-FGFR homologs in H. virescens and D. v. virgifera also bind Vip3Aa.",
    "Determine cryo-EM structure of Vip3Aa bound to Sf-FGFR.",
    "Investigate whether Sf-FGFR knockout affects Cry toxin susceptibility (cross-resistance test)."
  ],

  "extractionStatus": "structured",

  "linkedTopicIds": ["topic_pore_formation", "topic_binding_assays"],
  "linkedConceptIds": ["concept_vip3a", "concept_receptor_binding"],
  "linkedEvidenceIds": ["evidence_vip3a_binds_fgfr"],
  "linkedPaperIds": [],
  "linkedGapIds": ["gap_vip3a_pore_structure", "gap_vip3a_receptor_in_vivo"]
}
```

### Mapping: PaperEntity → EvidenceEntity

The 3 findings above would produce 3 EvidenceEntities:

| Finding | EvidenceEntity | evidenceType | direction |
|---------|---------------|-------------|-----------|
| Sf-FGFR identified as Vip3Aa binding protein | evidence_vip3a_binds_fgfr | experimental | supporting |
| CRISPR KO reduced Vip3Aa binding by ~70% | evidence_sffgfr_ko_reduces_binding | experimental | supporting |
| SPR Kd ~ 52 nM | evidence_vip3a_sffgfr_kd_52nm | experimental | supporting |

### Mapping: EvidenceEntity → ConceptEntity → TopicEntity

```
evidence_vip3a_binds_fgfr ──┐
evidence_sffgfr_ko_reduces  ├──→ concept_vip3a ──→ topic_pore_formation
evidence_vip3a_sffgfr_kd   ──┘       │
                                      └──→ topic_binding_assays
```

### Mapping: TopicEntity → GapEntity → HypothesisEntity

```
topic_pore_formation
  │
  ├── reveals ──→ gap_vip3a_pore_structure
  │                 (no cryo-EM structure yet)
  │                    │
  │                    └── generates ──→ hypothesis_domain_i_pore_formation
  │                                       "Vip3A Domain I forms the pore-lining region"
  │
  └── reveals ──→ gap_vip3a_receptor_in_vivo
                    (in vitro only, no whole-insect KO)
                       │
                       └── generates ──→ hypothesis_sr_c_primary_vip3a_receptor
                                          "SR-C is the primary functional Vip3Aa receptor"
```

---

## 5. Pipeline Status

| Stage | Status | Input | Output |
|-------|--------|-------|--------|
| 0: PDF → PaperEntity | Schema defined | PDF | PaperEntity |
| 1: PaperEntity → Evidence | Schema defined | PaperEntity.findings | EvidenceEntity[] |
| 2: Evidence → Concept | Schema defined | EvidenceEntity[] | ConceptEntity[] |
| 3: Concept → Topic | Schema defined | ConceptEntity[] | TopicEntity[] |
| 4: Topic → Gap | Schema defined | TopicEntity[] | GapEntity[] |
| 5: Gap → Hypothesis | Schema defined | GapEntity[] | HypothesisEntity[] |

All schemas are ready. No extraction logic is implemented yet.

---

## 6. Entity Files Location

```
web/lib/entities/
├── index.ts               (barrel export)
├── paper.entity.ts         (PaperEntity + sub-types)
├── evidence.entity.ts      (EvidenceEntity + sub-types)
├── concept.entity.ts       (ConceptEntity + sub-types)
├── topic.entity.ts         (TopicEntity + sub-types)
├── gap.entity.ts           (GapEntity + sub-types)
└── hypothesis.entity.ts    (HypothesisEntity + sub-types)
```
