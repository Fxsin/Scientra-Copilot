/* ── Research Intelligence Platform — Mock Data ── */

/* ============================================================
   0. Project Meta — used by all page headers
   ============================================================ */

export interface ProjectMeta {
  projectName: string;
  paperCount: number;
  lastUpdated: string;
  dataSource: string;
}

export const mockProjectMeta: ProjectMeta = {
  projectName: "Bt Toxin Mode of Action",
  paperCount: 34,
  lastUpdated: "2026-06-09T23:30:00Z",
  dataSource: "Mock Intelligence Layer",
};

/* ============================================================
   1. Research Map — Project Summary & Landscape
   ============================================================ */

export interface ProjectSummary {
  projectName: string;
  paperCount: number;
  coreTopicCount: number;
  hotspotCount: number;
  gapCount: number;
  methodCount: number;
}

export const mockProjectSummary: ProjectSummary = {
  projectName: "Bt Toxin Mode of Action",
  paperCount: 34,
  coreTopicCount: 8,
  hotspotCount: 5,
  gapCount: 7,
  methodCount: 12,
};

/* ── Research Insights ── */

export interface ResearchInsights {
  whatIsEstablished: string;
  whatIsUncertain: string;
  nextOpportunity: string;
}

export const mockResearchInsights: ResearchInsights = {
  whatIsEstablished:
    "Cry toxin mode of action is well characterized at the molecular level: sequential binding to cadherin and ABCC2, oligomerization, and pore formation in the midgut epithelium. Cry1A and Cry3A structural families are solved.",
  whatIsUncertain:
    "Vip3A receptor identity and pore-forming mechanism remain unresolved. Whether Cry and Vip3A share receptor pathways is actively debated. The structural basis of toxin specificity across lepidopteran species is poorly understood.",
  nextOpportunity:
    "Solving the Vip3A pore structure by cryo-EM would unlock rational engineering of toxin potency and specificity. Standardizing quantitative binding assays for Vip3A would enable rigorous cross-study comparison. CRISPR-validated receptor libraries across pest species would transform resistance risk assessment.",
};

/* ── Core Topic Card ── */

export interface TopicCard {
  id: string;
  name: string;
  count: number;
  representatives: string[];
}

export const mockTopics: TopicCard[] = [
  {
    id: "t1",
    name: "Cry toxin mechanism",
    count: 14,
    representatives: [
      "Cry1A — pore formation in midgut",
      "Cry receptor binding kinetics",
      "Cry toxin oligomerization",
      "Cry1Ac — Bt resistance evolution",
    ],
  },
  {
    id: "t2",
    name: "Vip3A mode of action",
    count: 9,
    representatives: [
      "Vip3A — receptor identification",
      "Vip3A binding to midgut BBMV",
      "Vip3A — Cry synergy mechanism",
      "Vip3Aa protoxin activation",
    ],
  },
  {
    id: "t3",
    name: "Insect resistance mechanisms",
    count: 11,
    representatives: [
      "Cadherin mutation — Cry resistance",
      "ABCC2 transporter downregulation",
      "ALP receptor loss in Heliothis",
    ],
  },
  {
    id: "t4",
    name: "Bt structural biology",
    count: 7,
    representatives: [
      "Cry1Ac — domain I–III crystal structure",
      "Vip3A — C-terminal domain folding",
    ],
  },
];

/* ── Hot Topics ── */

export const mockHotTopics: TopicCard[] = [
  {
    id: "ht1",
    name: "Vip3A receptor identification",
    count: 12,
    representatives: [
      "Sf-FGFR — Vip3A binding",
      "Vip3Aa — Scavenger Receptor-C",
      "CRISPR validation of Vip3A targets",
    ],
  },
  {
    id: "ht2",
    name: "Cry–Vip synergy in stacked traits",
    count: 8,
    representatives: [
      "Cry1Ab+Vip3Aa — synergistic LC₅₀",
      "No-cross-resistance evidence",
    ],
  },
  {
    id: "ht3",
    name: "CRISPR-based resistance screening",
    count: 6,
    representatives: [
      "Sf9 cell knockout — receptor library",
      "In vivo CRISPR in Spodoptera",
    ],
  },
];

/* ── Research Gaps ── */

export const mockGapCards: TopicCard[] = [
  {
    id: "g1",
    name: "Vip3A — in vivo binding kinetics",
    count: 3,
    representatives: [
      "Limited SPR data for Vip3A–receptor",
      "No cryo-EM structure of Vip3A pore",
      "Gap: in vivo binding evidence missing",
    ],
  },
  {
    id: "g2",
    name: "Cross-species receptor conservation",
    count: 2,
    representatives: [
      "Lepidoptera receptor diversity understudied",
      "No data on Coleopteran Vip3A binding",
    ],
  },
  {
    id: "g3",
    name: "Resistance management — field data",
    count: 4,
    representatives: [
      "Limited field-evolved resistance data",
      "Gap: fitness cost quantification",
    ],
  },
];

/* ── Methods ── */

export const mockMethods: TopicCard[] = [
  {
    id: "m1",
    name: "Binding assays",
    count: 18,
    representatives: ["BBMV binding", "SPR", "ELISA", "ligand blot"],
  },
  {
    id: "m2",
    name: "Structural biology",
    count: 7,
    representatives: ["Cryo-EM", "X-ray crystallography", "AlphaFold"],
  },
  {
    id: "m3",
    name: "Genetic tools",
    count: 9,
    representatives: ["CRISPR KO", "RNAi", "qRT-PCR"],
  },
  {
    id: "m4",
    name: "Bioassays",
    count: 22,
    representatives: ["Diet overlay", "Droplet feeding", "LC₅₀"],
  },
];

/* ── Major Questions ── */

export interface MajorQuestion {
  id: string;
  question: string;
  relatedTopics: string[];
  evidenceLevel: "Strong" | "Moderate" | "Weak" | "Emerging";
  paperCount: number;
}

export const mockMajorQuestions: MajorQuestion[] = [
  {
    id: "q1",
    question: "What is the molecular identity of the functional Vip3A receptor in Spodoptera frugiperda?",
    relatedTopics: ["Vip3A", "Receptor", "Binding"],
    evidenceLevel: "Moderate",
    paperCount: 9,
  },
  {
    id: "q2",
    question: "How does Vip3A form pores in the midgut epithelium, and how does this differ from Cry toxins?",
    relatedTopics: ["Vip3A", "Cry toxin", "Pore formation", "Mechanism"],
    evidenceLevel: "Weak",
    paperCount: 5,
  },
  {
    id: "q3",
    question: "What mechanisms drive cross-resistance between Cry and Vip toxins in field populations?",
    relatedTopics: ["Resistance", "Cry", "Vip3A", "Field evolution"],
    evidenceLevel: "Emerging",
    paperCount: 3,
  },
  {
    id: "q4",
    question: "Can structural modeling predict receptor-toxin specificity across lepidopteran species?",
    relatedTopics: ["Structural biology", "Receptor", "Specificity"],
    evidenceLevel: "Weak",
    paperCount: 4,
  },
  {
    id: "q5",
    question: "What is the fitness cost of receptor mutations that confer Bt resistance?",
    relatedTopics: ["Resistance", "Fitness", "Receptor mutation"],
    evidenceLevel: "Moderate",
    paperCount: 7,
  },
];

/* ── Knowledge Coverage ── */

export interface CoverageDimension {
  id: string;
  label: string;
  percentage: number;
  paperCount: number;
  description: string;
}

export const mockCoverage: CoverageDimension[] = [
  {
    id: "topic_mechanism",
    label: "Mechanism",
    percentage: 72,
    paperCount: 24,
    description: "Mode of action, pore formation, signaling pathway",
  },
  {
    id: "topic_structure",
    label: "Structure",
    percentage: 41,
    paperCount: 14,
    description: "Crystal structures, cryo-EM, domain architecture",
  },
  {
    id: "in_vivo",
    label: "In vivo evidence",
    percentage: 35,
    paperCount: 12,
    description: "Whole-organism bioassays, field trials, histopathology",
  },
  {
    id: "topic_application",
    label: "Application",
    percentage: 56,
    paperCount: 19,
    description: "Transgenic crops, resistance management, field efficacy",
  },
  {
    id: "methods",
    label: "Methods",
    percentage: 62,
    paperCount: 21,
    description: "Established protocols, emerging techniques, validation",
  },
];

/* ============================================================
   2. Hotspots
   ============================================================ */

export type TrendLabel = "Emerging" | "Growing" | "Stable" | "Declining";

export interface HotspotItem {
  id: string;
  name: string;
  trend: TrendLabel;
  recentPaperCount: number;
  growthScore: number; // 0–100
  representativePapers: string[];
  keyMethods: string[];
  whyItMatters: string;
}

export const mockHotspots: HotspotItem[] = [
  {
    id: "hs1",
    name: "Vip3A receptor deorphanization",
    trend: "Emerging",
    recentPaperCount: 7,
    growthScore: 89,
    representativePapers: [
      "Jiang et al. (2024) — Identification of Sf-FGFR as a Vip3A receptor",
      "Liu et al. (2025) — Scavenger Receptor-C mediates Vip3Aa binding",
    ],
    keyMethods: ["CRISPR KO screen", "Pull-down + MS", "SPR"],
    whyItMatters:
      "Resolving the Vip3A receptor identity is the single most impactful open question in Bt mode-of-action research. Every new candidate receptor reshapes our understanding of Cry–Vip specificity.",
  },
  {
    id: "hs2",
    name: "Cry–Vip3A stacking strategies",
    trend: "Growing",
    recentPaperCount: 9,
    growthScore: 72,
    representativePapers: [
      "Tabashnik et al. (2024) — No cross-resistance between Cry1Ab and Vip3Aa",
      "Zhang et al. (2025) — Synergistic LC₅₀ in dual-toxin bioassays",
    ],
    keyMethods: ["Diet overlay bioassay", "Isobole analysis", "Resistance selection"],
    whyItMatters:
      "Stacked traits are the frontline defense against resistance evolution. Understanding synergy at the molecular level enables rational trait design instead of empirical stacking.",
  },
  {
    id: "hs3",
    name: "Structural biology of toxin pores",
    trend: "Growing",
    recentPaperCount: 5,
    growthScore: 65,
    representativePapers: [
      "Wang et al. (2024) — Cryo-EM structure of Cry1Ac prepore",
      "Recent AlphaFold3 predictions of Vip3A pore",
    ],
    keyMethods: ["Cryo-EM", "AlphaFold3", "MD simulation"],
    whyItMatters:
      "The absence of a Vip3A pore structure is a critical gap. A solved structure would unlock rational engineering of toxin specificity and potency.",
  },
  {
    id: "hs4",
    name: "Field-evolved resistance monitoring",
    trend: "Stable",
    recentPaperCount: 6,
    growthScore: 40,
    representativePapers: [
      "F₂ screen data from Brazil, India, China (2023–2025)",
      "Long-term monitoring in Bt cotton regions",
    ],
    keyMethods: ["F₂ screen", "Diagnostic concentration bioassay", "Allele frequency"],
    whyItMatters:
      "Field monitoring is the canary in the coal mine for Bt crop durability. Stable publication rate reflects established surveillance programs rather than scientific stagnation.",
  },
  {
    id: "hs5",
    name: "RNAi + Bt combinatorial approaches",
    trend: "Emerging",
    recentPaperCount: 4,
    growthScore: 78,
    representativePapers: [
      "dsRNA targeting midgut genes + Cry toxin synergy",
      "Nanoparticle delivery of RNAi in lepidopteran pests",
    ],
    keyMethods: ["dsRNA synthesis", "Nanoparticle formulation", "qRT-PCR validation"],
    whyItMatters:
      "RNAi–Bt combinations represent the next generation of insecticidal traits. This area is nascent but growing fast — early entrants will define the experimental standards.",
  },
  {
    id: "hs6",
    name: "Cry toxin oligomerization",
    trend: "Declining",
    recentPaperCount: 2,
    growthScore: 18,
    representativePapers: [
      "Gómez et al. (2014) — sequential binding model",
      "Recent re-evaluation of oligomer necessity",
    ],
    keyMethods: ["Size-exclusion chromatography", "Cross-linking", "AFM"],
    whyItMatters:
      "Once a central debate, the oligomerization field has matured. Remaining questions are nuanced — the topic is consolidating rather than expanding.",
  },
];

/* ============================================================
   3. Research Gaps
   ============================================================ */

export type GapType = "Evidence Gap" | "Method Gap" | "Species / Model Gap" | "Contradiction Gap";

export interface EvidenceBasis {
  paperCount: number;
  directEvidenceCount: number;
  indirectEvidenceCount: number;
  contradictionCount: number;
  missingEvidenceType: string;
}

export interface ResearchGapItem {
  id: string;
  title: string;
  gapType: GapType;
  description: string;
  supportingPapers: string[];
  missingEvidence: string;
  opportunityLevel: "High" | "Medium" | "Low";
  suggestedNext: string;
  /** Score 0–100: how confident we are that this is a real gap */
  confidence: number;
  /** Score 0–100: scientific/translational importance of filling this gap */
  impact: number;
  /** Score 0–100: how feasible it is to address with current methods */
  feasibility: number;
  /** Concrete validation path */
  suggestedValidationPath: string;
  /** What is currently known from the literature */
  knownSummary: string;
  /** What is still unknown or unresolved */
  missingSummary: string;
  /** Why this gap matters scientifically */
  whyItMatters: string;
  /** Quantitative evidence backing the gap claim */
  evidenceBasis: EvidenceBasis;
  /** Topic Explorer topic IDs this gap relates to */
  linkedTopicIds: string[];
  /** Concept IDs this gap is connected to */
  linkedConceptIds: string[];
  /** Specific paper IDs supporting this gap */
  linkedPaperIds: string[];
  /** Evidence IDs supporting this gap */
  linkedEvidenceIds: string[];
  /** Actionable next step (displayed as "Suggested Next Step") */
  suggestedNextStep: string;
}

export const mockResearchGaps: ResearchGapItem[] = [
  {
    id: "gap_vip3a_pore_structure",
    title: "Vip3A pore structure is unknown",
    gapType: "Evidence Gap",
    description:
      "Despite functional evidence that Vip3A forms pores in the midgut epithelium, no high-resolution structure of the Vip3A pore or prepore complex exists. Cry toxin pore structures are available (Cry1Ac, Cry4Ba), but Vip3A belongs to a different structural family.",
    supportingPapers: [
      "Cry1Ac prepore — cryo-EM at 3.2 Å",
      "Vip3Aa — AlphaFold prediction (no pore form)",
      "Functional evidence: Vip3A increases membrane conductance in planar lipid bilayers",
    ],
    missingEvidence:
      "Cryo-EM structure of Vip3A in membrane-inserted or prepore conformation; mutagenesis data mapping pore-lining residues.",
    opportunityLevel: "High",
    suggestedNext:
      "Reconstitute Vip3A in lipid nanodiscs and collect cryo-EM data. Alternatively, use AlphaFold3 with multimer and membrane context to generate a testable pore model for mutagenesis validation.",
    confidence: 85,
    impact: 90,
    feasibility: 40,
    suggestedValidationPath:
      "Collect cryo-EM data on Vip3A in nanodiscs → generate 3D classes → if resolution <4 Å, build atomic model → validate pore-lining residues by mutagenesis + planar lipid bilayer electrophysiology.",
    knownSummary:
      "Cry toxin pore structures (Cry1Ac, Cry4Ba) are solved by cryo-EM at 3–4 Å resolution. The general mechanism — domain I hairpin insertion, oligomeric prepore assembly — is well established. Vip3A increases membrane conductance in planar lipid bilayers, confirming it also forms pores.",
    missingSummary:
      "No high-resolution structure of the Vip3A pore or prepore exists. The architecture of the Vip3A pore (stoichiometry, membrane-spanning segments, conformational change upon insertion) is entirely unknown. Vip3A belongs to a different structural family than 3-domain Cry toxins, so the Cry pore mechanism cannot be extrapolated.",
    whyItMatters:
      "The pore structure is the key missing piece in the Vip3A mode-of-action puzzle. Without it, rational engineering of toxin potency and specificity is impossible. A solved Vip3A pore structure would also clarify whether Vip3A and Cry toxins share mechanistic principles or represent convergent evolution of insecticidal function.",
    evidenceBasis: {
      paperCount: 12,
      directEvidenceCount: 3,
      indirectEvidenceCount: 6,
      contradictionCount: 0,
      missingEvidenceType: "Structure",
    },
    linkedTopicIds: ["topic_pore_formation"],
    linkedConceptIds: ["concept_vip3a", "concept_pore_formation"],
    linkedPaperIds: ["paper_jiang_2024", "paper_liu_2025", "paper_wang_2024"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Reconstitute activated Vip3Aa in lipid nanodiscs, collect cryo-EM data (200 kV or 300 kV), perform 2D/3D classification. If resolution <4 Å, build and refine atomic model. Validate pore-lining residues by cysteine-scanning mutagenesis and planar lipid bilayer electrophysiology.",
  },
  {
    id: "gap_vip3a_binding_method",
    title: "No standardized method for Vip3A binding affinity quantification",
    gapType: "Method Gap",
    description:
      "BBMV binding assays for Cry toxins are well-established (125I-labeling, saturation binding, homologous competition). For Vip3A, binding is often reported qualitatively (present/absent on blot) without Kd values. SPR studies are rare and use different immobilization strategies, making cross-study comparison impossible.",
    supportingPapers: [
      "BBMV binding — qualitative Vip3A blots in Sf, Hz, Se",
      "SPR — single study with immobilized Vip3Aa on CM5 chip",
      "No inter-laboratory validation of Vip3A binding protocols",
    ],
    missingEvidence:
      "Validated protocol for quantitative Vip3A binding measurement (SPR or radioligand); inter-laboratory ring trial data.",
    opportunityLevel: "High",
    suggestedNext:
      "Develop a standardized SPR protocol: immobilize receptor candidate on chip, flow Vip3A analyte at 5 concentrations, fit to 1:1 Langmuir model. Share protocol as a pre-registered methods paper with step-by-step video protocol.",
    confidence: 75,
    impact: 65,
    feasibility: 80,
    suggestedValidationPath:
      "Select 3 labs → provide identical reagents (Vip3Aa, Sf-FGFR) → each lab runs SPR with shared protocol → compare Kd values across labs → if CV < 20%, publish as community standard.",
    knownSummary:
      "Cry toxin BBMV binding assays are a mature, widely adopted standard: 125I-labeled toxin, saturation binding to BBMV, homologous/heterologous competition. SPR has been used for Cry toxins with consistent Kd values across labs. For Vip3A, BBMV binding is demonstrated qualitatively in multiple labs.",
    missingSummary:
      "No standardized quantitative protocol exists for Vip3A binding. SPR studies are limited to a single lab. Kd values for Vip3A–receptor interaction are not available in the literature. Different immobilization strategies and buffer conditions prevent cross-study comparison.",
    whyItMatters:
      "Without quantitative binding data, the field cannot distinguish between high-affinity functional receptors and low-affinity incidental binding. A standardized method is a prerequisite for receptor validation, structure–activity studies, and cross-species comparisons.",
    evidenceBasis: {
      paperCount: 8,
      directEvidenceCount: 1,
      indirectEvidenceCount: 5,
      contradictionCount: 0,
      missingEvidenceType: "Method",
    },
    linkedTopicIds: ["topic_binding_assays"],
    linkedConceptIds: ["concept_vip3a"],
    linkedPaperIds: ["paper_jiang_2024", "paper_liu_2025"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Select 3 independent labs → distribute identical reagents (Vip3Aa batch, Sf-FGFR protein) → each lab runs SPR with pre-registered protocol → compare Kd values across labs → if CV < 20%, publish protocol as community standard methods paper.",
  },
  {
    id: "gap_cross_species_receptor",
    title: "Vip3A receptor studies limited to Spodoptera — no data in Coleoptera",
    gapType: "Species / Model Gap",
    description:
      "All published Vip3A receptor work uses Spodoptera frugiperda (Sf9 cells) or S. exigus. Vip3A is also active against other Lepidoptera (Helicoverpa, Agrotis) and some Coleoptera, but receptor identity across species is unexplored. This limits cross-species extrapolation and resistance risk assessment.",
    supportingPapers: [
      "Vip3Aa receptor candidates: Sf-FGFR, Sf-SR-C (both from Sf9)",
      "Vip3Aa active against H. virescens, A. ipsilon in bioassays",
      "No receptor data from Coleopteran models",
    ],
    missingEvidence:
      "Receptor identification and binding data from at least 3 lepidopteran pest species and 1 coleopteran; phylogenetic analysis of receptor conservation.",
    opportunityLevel: "Medium",
    suggestedNext:
      "Clone receptor orthologs from H. virescens and D. v. virgifera midgut cDNA. Express in Sf9 cells, measure Vip3A binding by SPR, and validate by CRISPR KO + bioassay.",
    confidence: 70,
    impact: 55,
    feasibility: 50,
    suggestedValidationPath:
      "Identify orthologs by BLAST → clone into expression vector → express in Sf9 cells → SPR with Vip3Aa → if Kd < 100 nM, validate by CRISPR KO in target species.",
    knownSummary:
      "Vip3A receptor candidates (Sf-FGFR, Sf-SR-C) have been identified in Spodoptera frugiperda using pull-down + mass spectrometry and CRISPR-based screens. Vip3A is active in bioassays against multiple Lepidoptera (H. virescens, A. ipsilon) and some Coleoptera.",
    missingSummary:
      "Receptor identity has not been confirmed in any species other than S. frugiperda. No receptor data exists for Coleopteran models. The phylogenetic conservation of Vip3A receptors across pest species is unknown.",
    whyItMatters:
      "Cross-species receptor data is essential for predicting which pest species are susceptible to Vip3A-expressing crops and for assessing the risk of receptor-based resistance evolution across the target pest spectrum.",
    evidenceBasis: {
      paperCount: 7,
      directEvidenceCount: 2,
      indirectEvidenceCount: 3,
      contradictionCount: 0,
      missingEvidenceType: "Species coverage",
    },
    linkedTopicIds: ["topic_model_organism"],
    linkedConceptIds: ["concept_vip3a"],
    linkedPaperIds: ["paper_jiang_2024"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Clone receptor orthologs from H. virescens, A. ipsilon, and D. v. virgifera midgut cDNA. Express in Sf9 cells, measure Vip3Aa binding by SPR, validate functional relevance by CRISPR KO + bioassay in at least one non-Spodoptera species.",
  },
  {
    id: "gap_cry_vip_receptor_contradiction",
    title: "Contradictory evidence on whether Cry and Vip3A share receptor pathways",
    gapType: "Contradiction Gap",
    description:
      "Some studies report that Cry1Ab-resistant insects show no cross-resistance to Vip3Aa, suggesting distinct receptors. Others show that Vip3A binding can be competed by Cry toxins in BBMV, implying shared or overlapping binding sites. The contradiction may stem from differences in experimental conditions (in vitro vs. in vivo, toxin concentrations, tissue source).",
    supportingPapers: [
      "No cross-resistance: Cry1Ab-resistant Diatraea remain Vip3Aa-susceptible",
      "Cross-competition: Cry1Ac reduces Vip3A binding to H. virescens BBMV by 40%",
      "Distinct midgut histopathology: Cry causes swelling, Vip3A causes blebbing",
    ],
    missingEvidence:
      "Systematic competition binding experiments with purified toxins at defined concentrations; in vivo validation in receptor-KO insects challenged with both toxins.",
    opportunityLevel: "High",
    suggestedNext:
      "Design a 2×2 factorial competition binding experiment: 4 concentrations each of Cry1Ac and Vip3Aa, all pairwise combinations, on the same BBMV preparation from the same insect cohort. Measure binding by SPR and validate with bioassay on receptor-KO lines.",
    confidence: 60,
    impact: 85,
    feasibility: 60,
    suggestedValidationPath:
      "Purify Cry1Ac and Vip3Aa → BBMV prep from single H. virescens cohort → 4×4 concentration matrix SPR → if competition detected at physiological concentrations, validate in Cry1Ac-resistant vs susceptible strains → if discrepancy persists, test buffer/pH effect.",
    knownSummary:
      "Cry1Ab-resistant insect strains show no cross-resistance to Vip3Aa, suggesting distinct receptors. However, Cry1Ac can partially reduce Vip3A binding to H. virescens BBMV in competition assays (~40% reduction), implying some overlap. The two toxins produce different histopathology (Cry = swelling, Vip3A = blebbing).",
    missingSummary:
      "The conditions under which Cry and Vip3A binding competition occurs are not defined. Concentration-dependence, pH sensitivity, and tissue-source effects have not been systematically tested. It is unclear whether the competition reflects shared receptor sites, overlapping binding surfaces, or non-specific steric effects.",
    whyItMatters:
      "If Cry and Vip3A share any receptor pathway, cross-resistance risk is higher than current models assume. If they do not, stacked Cry+Vip3A traits are truly independent resistance management tools. Resolving this contradiction determines the durability of second-generation Bt crops.",
    evidenceBasis: {
      paperCount: 10,
      directEvidenceCount: 4,
      indirectEvidenceCount: 4,
      contradictionCount: 3,
      missingEvidenceType: "Mechanism",
    },
    linkedTopicIds: ["topic_receptor_mutation"],
    linkedConceptIds: ["concept_cry_toxin", "concept_vip3a"],
    linkedPaperIds: ["paper_liu_2025", "paper_tabashnik_2024"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Design a 2×2 factorial competition binding experiment: 4 concentrations of Cry1Ac × 4 concentrations of Vip3Aa, on the same BBMV preparation. Measure by SPR. If competition is concentration-dependent and saturable, validate in Cry-resistant vs susceptible strains. If results differ across conditions, systematically test pH (7–10), ionic strength, and BBMV preparation method.",
  },
  {
    id: "gap_vip3a_receptor_in_vivo",
    title: "Lack of in vivo evidence for Vip3A receptor function",
    gapType: "Evidence Gap",
    description:
      "Vip3A receptor candidates (Sf-FGFR, Sf-SR-C) were identified by pull-down or CRISPR screen, but in vivo functional validation — demonstrating that receptor knockout abolishes Vip3A toxicity in the whole insect — is missing for most candidates.",
    supportingPapers: [
      "Sf-FGFR KO in Sf9 cells reduces Vip3A binding (in vitro)",
      "No published whole-insect KO validation for any Vip3A receptor",
    ],
    missingEvidence:
      "CRISPR KO of candidate receptor in whole Spodoptera larvae, followed by Vip3A bioassay showing >10-fold shift in LC₅₀.",
    opportunityLevel: "Medium",
    suggestedNext:
      "Generate homozygous receptor-KO Spodoptera line by CRISPR. Confirm KO by qPCR and western blot. Conduct diet-overlay bioassay with Vip3Aa at 6 concentrations; compare LC₅₀ with wild-type and heterozygous siblings.",
    confidence: 65,
    impact: 75,
    feasibility: 45,
    suggestedValidationPath:
      "Design sgRNAs targeting Sf-FGFR exon 3 → inject embryos → screen G0 mosaics by PCR → outcross to G2 → genotype → bioassay homozygous KO vs WT at 6 Vip3Aa concentrations → if LC₅₀ ratio > 10, receptor confirmed in vivo.",
    knownSummary:
      "Vip3A receptor candidates (Sf-FGFR, Sf-SR-C) were identified by pull-down + MS and CRISPR-based screens in Sf9 cells. Knockout of Sf-FGFR in Sf9 cells reduces Vip3A binding, providing in vitro evidence. No published study has validated any Vip3A receptor by whole-insect knockout.",
    missingSummary:
      "In vivo functional validation — demonstrating that receptor knockout in the whole insect abolishes or significantly reduces Vip3A toxicity — is absent. Without this, receptor candidates remain correlative, not causal.",
    whyItMatters:
      "In vivo validation is the gold standard for receptor identification. Until a Vip3A receptor is functionally validated in the whole insect, the mode-of-action model for Vip3A remains incomplete, and resistance monitoring based on receptor mutations cannot be designed.",
    evidenceBasis: {
      paperCount: 6,
      directEvidenceCount: 1,
      indirectEvidenceCount: 3,
      contradictionCount: 0,
      missingEvidenceType: "In vivo validation",
    },
    linkedTopicIds: ["topic_pore_formation"],
    linkedConceptIds: ["concept_vip3a"],
    linkedPaperIds: ["paper_jiang_2024"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Generate homozygous receptor-KO S. frugiperda line by CRISPR/Cas9 targeting Sf-FGFR exon 3. Confirm KO by qRT-PCR and western blot. Conduct diet-overlay bioassay with Vip3Aa at 6 concentrations (0.1–100 µg/cm²). Compare LC₅₀ of homozygous KO, heterozygous, and wild-type siblings. If LC₅₀ ratio > 10, receptor confirmed as functional in vivo.",
  },
  {
    id: "gap_resistance_fitness_cost",
    title: "Fitness cost of Bt resistance alleles in field populations is poorly quantified",
    gapType: "Evidence Gap",
    description:
      "Resistance management models assume fitness costs of resistance alleles, but empirical measurements are sparse. Most fitness cost studies use lab-selected strains, which may not reflect field-evolved resistance alleles. The few field studies report variable results depending on host plant, temperature, and genetic background.",
    supportingPapers: [
      "Lab-selected Cry1Ac-resistant H. virescens — 15% reduced pupal weight",
      "Field-derived Cry1F-resistant S. frugiperda — no detectable fitness cost on corn",
      "Conflicting results for Cry2Ab resistance in H. armigera across populations",
    ],
    missingEvidence:
      "Fitness cost measurements (survival, development time, pupal weight, fecundity) for field-derived resistance alleles, on relevant host plants, across multiple temperature regimes.",
    opportunityLevel: "Medium",
    suggestedNext:
      "Collect field populations with known resistance allele frequencies. Establish isogenic lines (resistant/susceptible) by repeated backcrossing. Measure life-table parameters on cotton/corn at 3 temperatures. Model resistance evolution under different fitness cost scenarios.",
    confidence: 55,
    impact: 70,
    feasibility: 35,
    suggestedValidationPath:
      "Sample 5 field populations → F₂ screen for resistance allele frequency → backcross to susceptible lab strain × 6 generations → life-table assay (n=100 per line) at 22°C/27°C/32°C on artificial diet + cotton leaf → measure survival, development time, pupal weight, fecundity → model resistance allele trajectory under observed fitness costs.",
    knownSummary:
      "Resistance management models universally assume fitness costs of Bt resistance alleles, and this assumption underpins the high-dose/refuge strategy. Lab-selected resistant strains sometimes show measurable fitness costs (e.g., 15% reduced pupal weight in Cry1Ac-resistant H. virescens), but field-derived strains often show no detectable cost.",
    missingSummary:
      "Fitness cost measurements for field-evolved resistance alleles are extremely sparse. Existing studies use variable host plants, temperatures, and genetic backgrounds, making cross-study comparison impossible. The interaction between genetic background and fitness cost magnitude is not quantified.",
    whyItMatters:
      "If field-evolved resistance alleles carry negligible fitness costs, the high-dose/refuge strategy is less effective than models predict. Accurate fitness cost data is essential for resistance evolution forecasting and regulatory decisions about Bt crop deployment.",
    evidenceBasis: {
      paperCount: 9,
      directEvidenceCount: 2,
      indirectEvidenceCount: 4,
      contradictionCount: 1,
      missingEvidenceType: "Field data",
    },
    linkedTopicIds: ["topic_resistance_mgmt"],
    linkedConceptIds: ["concept_cry_toxin"],
    linkedPaperIds: ["paper_tabashnik_2024"],
    linkedEvidenceIds: [],
    suggestedNextStep:
      "Sample 5 field populations with documented Bt resistance allele frequencies. Establish isogenic lines (RR/RS/SS) by 6 generations of backcrossing to a common susceptible strain. Conduct life-table assays (n=100 per genotype) at 22°C, 27°C, and 32°C on artificial diet and cotton leaf. Measure survival, development time, pupal weight, and fecundity. Parameterize a population genetics model to forecast resistance allele dynamics under observed fitness costs.",
  },
];

/* ============================================================
   4. Topic Explorer
   ============================================================ */

export interface TopicTreeNode {
  id: string;
  label: string;
  children?: TopicTreeNode[];
}

export interface TopicDetail {
  id: string;
  definition: string;
  keyFindings: string[];
  representativePapers: string[];
  relatedMethods: string[];
  relatedTopics: string[];
  unresolvedQuestions: string[];
  /** 0–100: aggregated evidence quality */
  evidenceStrength: number;
  /** Human-readable recent activity description */
  recentActivity: string;
  /** IDs of connected research gaps */
  connectedGaps: string[];
  /** Ordered list of paper IDs / titles to read first */
  suggestedReadingOrder: string[];
}

export const mockTopicTree: TopicTreeNode[] = [
  {
    id: "root",
    label: "Bt Mode of Action",
    children: [
      {
        id: "mechanism",
        label: "Mechanism",
        children: [
          { id: "topic_pore_formation", label: "Pore formation" },
          { id: "topic_oligomerization", label: "Oligomerization" },
          { id: "topic_signal_transduction", label: "Signal transduction" },
          { id: "topic_cell_death", label: "Cell death pathways" },
        ],
      },
      {
        id: "structure",
        label: "Structure",
        children: [
          { id: "topic_cry_structure", label: "Cry toxin structure" },
          { id: "topic_vip_structure", label: "Vip3A structure" },
          { id: "topic_domain_function", label: "Domain function" },
        ],
      },
      {
        id: "method_category",
        label: "Method",
        children: [
          { id: "topic_binding_assays", label: "Binding assays" },
          { id: "topic_cryo_em", label: "Cryo-EM" },
          { id: "topic_crispr", label: "CRISPR tools" },
          { id: "topic_bioassay", label: "Bioassay" },
          { id: "topic_bioinformatics", label: "Bioinformatics" },
        ],
      },
      {
        id: "model_organism",
        label: "Model organism",
        children: [
          { id: "topic_sf", label: "Spodoptera frugiperda" },
          { id: "topic_hz", label: "Helicoverpa zea" },
          { id: "topic_se", label: "Spodoptera exigua" },
          { id: "topic_dvv", label: "Diabrotica v. virgifera" },
        ],
      },
      {
        id: "application",
        label: "Application",
        children: [
          { id: "topic_transgenic", label: "Transgenic crops" },
          { id: "topic_resistance_mgmt", label: "Resistance management" },
          { id: "topic_stacking", label: "Trait stacking" },
        ],
      },
      {
        id: "resistance",
        label: "Resistance / Adaptation",
        children: [
          { id: "topic_receptor_mutation", label: "Receptor mutation" },
          { id: "topic_midgut_protease", label: "Midgut protease alteration" },
          { id: "topic_immune_response", label: "Immune response" },
          { id: "topic_behavioral", label: "Behavioral avoidance" },
        ],
      },
    ],
  },
];

export const mockTopicDetails: Record<string, TopicDetail> = {
  topic_pore_formation: {
    id: "topic_pore_formation",
    definition:
      "Pore formation is the process by which Bt toxins insert into the insect midgut epithelial membrane, forming ion-permeable pores that disrupt osmotic balance and lead to cell lysis. Cry toxins form pores via a sequential binding–oligomerization–insertion model; the Vip3A pore-forming mechanism is less well characterized.",
    keyFindings: [
      "Cry1Ac forms a 250 kDa tetrameric prepore that inserts into the membrane at neutral-to-alkaline pH",
      "Domain I (α-helical bundle) is the pore-forming domain in all 3-domain Cry toxins",
      "Vip3A increases membrane conductance in planar lipid bilayers, confirming pore-forming activity",
      "Pore formation requires proteolytic activation of protoxin (both Cry and Vip families)",
    ],
    representativePapers: [
      "Bravo et al. (2007) — Mode of action of Bt Cry toxins",
      "Soberón et al. (2009) — Role of Cry toxin oligomerization in pore formation",
    ],
    relatedMethods: ["Planar lipid bilayer electrophysiology", "Cryo-EM", "MD simulation", "BBMV permeability assay"],
    relatedTopics: ["Oligomerization", "Cry toxin structure", "Vip3A structure", "Receptor binding"],
    unresolvedQuestions: [
      "Does Vip3A form the same type of pore as Cry toxins?",
      "What is the stoichiometry of the functional pore?",
      "Is oligomerization a prerequisite for Vip3A membrane insertion?",
    ],
    evidenceStrength: 75,
    recentActivity: "Active — 3 new papers on Vip3A pore formation in 2025, including the first cryo-EM attempt at the Vip3A prepore.",
    connectedGaps: ["gap_vip3a_pore_structure"],
    suggestedReadingOrder: [
      "Bravo et al. (2007) — foundational Cry pore model",
      "Soberón et al. (2009) — oligomerization + pore link",
      "Endo et al. (2022) — cryo-EM of Cry pore structure",
      "Recent Vip3A functional studies (2024–2025)",
    ],
  },
  topic_oligomerization: {
    id: "topic_oligomerization",
    definition:
      "Oligomerization refers to the assembly of monomeric toxin subunits into a higher-order oligomeric complex (typically tetrameric for Cry toxins) that is competent for membrane insertion. The sequential binding model posits that monomer binding to cadherin triggers a conformational change enabling oligomerization.",
    keyFindings: [
      "Cry1Ac oligomerization is triggered by cadherin binding and removal of helix α-1",
      "The Cry oligomer is a tetramer with ~250 kDa molecular weight",
      "Oligomerization-defective Cry mutants are non-toxic despite retaining receptor binding",
      "Whether Vip3A requires oligomerization for toxicity is unresolved",
    ],
    representativePapers: [
      "Gómez et al. (2002) — Cadherin binding triggers Cry1A oligomerization",
      "Pardo-López et al. (2006) — Structural changes during oligomerization",
    ],
    relatedMethods: ["Size-exclusion chromatography", "Chemical cross-linking", "Blue-native PAGE", "AFM"],
    relatedTopics: ["Pore formation", "Receptor binding", "Cry toxin structure"],
    unresolvedQuestions: [
      "Is oligomerization universally required across all Cry toxin subfamilies?",
      "What is the oligomeric state of Vip3A in the membrane?",
    ],
    evidenceStrength: 60,
    recentActivity: "Stable — foundational work from 2002–2009 is well cited; new work focuses on Vip3A oligomerization question.",
    connectedGaps: [],
    suggestedReadingOrder: [
      "Gómez et al. (2002) — cadherin-triggered oligomerization",
      "Pardo-López et al. (2006) — structural changes during oligomerization",
      "Bravo et al. (2007) — comprehensive mode-of-action review",
    ],
  },
  topic_cryo_em: {
    id: "topic_cryo_em",
    definition:
      "Cryo-electron microscopy (cryo-EM) is a structural biology technique where samples are flash-frozen in vitreous ice and imaged at cryogenic temperatures. It has become the method of choice for determining high-resolution structures of toxin pores and toxin–receptor complexes that are difficult to crystallize.",
    keyFindings: [
      "Cryo-EM structure of Cry1Ac prepore at 3.2 Å revealed domain I conformational changes",
      "Cry4Ba pore structure showed a tetrameric assembly spanning the lipid bilayer",
      "AlphaFold3 predictions increasingly guide cryo-EM model building for Bt toxins",
    ],
    representativePapers: [
      "Byrne et al. (2022) — Cryo-EM pipeline for membrane proteins",
      "Recent cryo-EM of Bt toxin–receptor complexes",
    ],
    relatedMethods: ["Single-particle analysis", "Tomography", "AlphaFold", "X-ray crystallography"],
    relatedTopics: ["Cry toxin structure", "Vip3A structure", "Pore formation"],
    unresolvedQuestions: [
      "Can cryo-EM resolve the Vip3A pore structure in a native lipid environment?",
      "What is the resolution limit for toxin–receptor complexes in nanodiscs?",
    ],
    evidenceStrength: 70,
    recentActivity: "Growing — major cryo-EM facilities now routinely solving toxin structures; AlphaFold3 integration accelerating model building.",
    connectedGaps: ["gap_vip3a_pore_structure"],
    suggestedReadingOrder: [
      "Byrne et al. (2022) — cryo-EM pipeline for membrane proteins",
      "Endo et al. (2022) — Cry pore structure by cryo-EM",
      "Recent cryo-EM of Bt toxin–receptor complexes",
    ],
  },
};

// Default detail for topics without specific content
export function getDefaultTopicDetail(label: string): TopicDetail {
  return {
    id: label.toLowerCase().replace(/\s+/g, "_"),
    definition: `${label} — detailed exploration coming soon. This topic area is part of the Bt mode-of-action research landscape.`,
    keyFindings: [
      "Key findings will be populated from literature analysis",
      "This topic has active research interest",
    ],
    representativePapers: [
      "Relevant papers will be linked here",
    ],
    relatedMethods: ["Various methods apply to this topic"],
    relatedTopics: ["Related topics will be mapped"],
    unresolvedQuestions: [
      "What are the key unresolved questions in this area?",
    ],
    evidenceStrength: 30,
    recentActivity: "Data pending — topic coverage will improve as more papers are ingested.",
    connectedGaps: [],
    suggestedReadingOrder: [
      "Start with the most recent review paper in this area",
    ],
  };
}

/* ============================================================
   5. Knowledge Network
   ============================================================ */

export type NetworkMode = "concept" | "method" | "evidence" | "contradiction";

export interface RINetworkNode {
  id: string;
  /** Stable shared entity ID (e.g. "concept_cry_toxin") */
  entityId: string;
  /** Entity category for cross-page linking */
  entityType: "concept" | "topic" | "research_gap" | "method" | "evidence" | "paper";
  label: string;
  type: "Concept" | "Method" | "Finding" | "Paper";
  color: string;
  size: number;
  linkedTopicIds?: string[];
  linkedConceptIds?: string[];
  linkedGapIds?: string[];
  linkedPaperIds?: string[];
  x?: number;
  y?: number;
}

export interface RINetworkLink {
  source: string;
  target: string;
  type: string;
  weight: number;
  label: string;
}

export interface RINetworkData {
  nodes: RINetworkNode[];
  links: RINetworkLink[];
}

export const mockConceptNetwork: RINetworkData = {
  nodes: [
    { id: "concept_cry_toxin", entityId: "concept_cry_toxin", entityType: "concept", label: "Cry toxin", type: "Concept", color: "#0d1f39", size: 18 },
    { id: "concept_vip3a", entityId: "concept_vip3a", entityType: "concept", label: "Vip3A", type: "Concept", color: "#0d1f39", size: 16 },
    { id: "concept_pore_formation", entityId: "concept_pore_formation", entityType: "concept", label: "Pore formation", type: "Concept", color: "#16512b", size: 14 },
    { id: "concept_receptor_binding", entityId: "concept_receptor_binding", entityType: "concept", label: "Receptor binding", type: "Concept", color: "#16512b", size: 15 },
    { id: "concept_oligomerization", entityId: "concept_oligomerization", entityType: "concept", label: "Oligomerization", type: "Concept", color: "#16512b", size: 12 },
    { id: "concept_resistance", entityId: "concept_resistance", entityType: "concept", label: "Resistance", type: "Concept", color: "#5c6b72", size: 14 },
    { id: "concept_midgut_epithelium", entityId: "concept_midgut_epithelium", entityType: "concept", label: "Midgut epithelium", type: "Concept", color: "#0d1f39", size: 12 },
    { id: "concept_cadherin", entityId: "concept_cadherin", entityType: "concept", label: "Cadherin", type: "Concept", color: "#16512b", size: 10 },
    { id: "concept_abcc2", entityId: "concept_abcc2", entityType: "concept", label: "ABCC2 transporter", type: "Concept", color: "#16512b", size: 10 },
    { id: "concept_crispr", entityId: "concept_crispr", entityType: "concept", label: "CRISPR", type: "Concept", color: "#5c6b72", size: 11 },
    { id: "concept_bt_crop", entityId: "concept_bt_crop", entityType: "concept", label: "Bt crop", type: "Concept", color: "#0d1f39", size: 13 },
    { id: "concept_stacked_trait", entityId: "concept_stacked_trait", entityType: "concept", label: "Stacked trait", type: "Concept", color: "#5c6b72", size: 10 },
  ],
  links: [
    { source: "concept_cry_toxin", target: "concept_pore_formation", type: "mechanism_of", weight: 8, label: "forms pore via" },
    { source: "concept_cry_toxin", target: "concept_receptor_binding", type: "binds_to", weight: 9, label: "binds" },
    { source: "concept_cry_toxin", target: "concept_oligomerization", type: "undergoes", weight: 6, label: "oligomerizes" },
    { source: "concept_vip3a", target: "concept_pore_formation", type: "mechanism_of", weight: 5, label: "likely forms pore" },
    { source: "concept_vip3a", target: "concept_receptor_binding", type: "binds_to", weight: 7, label: "binds" },
    { source: "concept_receptor_binding", target: "concept_cadherin", type: "involves", weight: 7, label: "receptor" },
    { source: "concept_receptor_binding", target: "concept_abcc2", type: "involves", weight: 5, label: "receptor" },
    { source: "concept_resistance", target: "concept_cadherin", type: "mutation_in", weight: 4, label: "mutation" },
    { source: "concept_resistance", target: "concept_abcc2", type: "mutation_in", weight: 4, label: "mutation" },
    { source: "concept_crispr", target: "concept_cadherin", type: "validates", weight: 5, label: "KO validates" },
    { source: "concept_bt_crop", target: "concept_cry_toxin", type: "expresses", weight: 8, label: "expresses" },
    { source: "concept_bt_crop", target: "concept_vip3a", type: "expresses", weight: 6, label: "expresses" },
    { source: "concept_cry_toxin", target: "concept_resistance", type: "drives", weight: 6, label: "drives" },
    { source: "concept_midgut_epithelium", target: "concept_receptor_binding", type: "site_of", weight: 5, label: "site of" },
    { source: "concept_stacked_trait", target: "concept_cry_toxin", type: "combines", weight: 5, label: "combines" },
    { source: "concept_stacked_trait", target: "concept_vip3a", type: "combines", weight: 5, label: "combines" },
  ],
};

export const mockMethodNetwork: RINetworkData = {
  nodes: [
    { id: "method_bbmv_binding", entityId: "method_bbmv_binding", entityType: "method", label: "BBMV binding", type: "Method", color: "#16512b", size: 14 },
    { id: "method_spr", entityId: "method_spr", entityType: "method", label: "SPR", type: "Method", color: "#16512b", size: 12 },
    { id: "method_cryo_em", entityId: "method_cryo_em", entityType: "method", label: "Cryo-EM", type: "Method", color: "#16512b", size: 13 },
    { id: "method_crispr_ko", entityId: "method_crispr_ko", entityType: "method", label: "CRISPR KO", type: "Method", color: "#16512b", size: 15 },
    { id: "method_diet_bioassay", entityId: "method_diet_bioassay", entityType: "method", label: "Diet bioassay", type: "Method", color: "#16512b", size: 14 },
    { id: "method_planar_lipid_bilayer", entityId: "method_planar_lipid_bilayer", entityType: "method", label: "Planar lipid bilayer", type: "Method", color: "#16512b", size: 10 },
    { id: "method_alphafold", entityId: "method_alphafold", entityType: "method", label: "AlphaFold", type: "Method", color: "#16512b", size: 11 },
    { id: "method_rnai", entityId: "method_rnai", entityType: "method", label: "RNAi", type: "Method", color: "#16512b", size: 11 },
  ],
  links: [
    { source: "method_bbmv_binding", target: "method_spr", type: "complements", weight: 6, label: "validates" },
    { source: "method_crispr_ko", target: "method_bbmv_binding", type: "validates", weight: 7, label: "confirms target" },
    { source: "method_cryo_em", target: "method_alphafold", type: "integrated_with", weight: 5, label: "guided by" },
    { source: "method_diet_bioassay", target: "method_crispr_ko", type: "paired_with", weight: 7, label: "phenotype readout" },
    { source: "method_planar_lipid_bilayer", target: "method_cryo_em", type: "complements", weight: 4, label: "functional data" },
    { source: "method_rnai", target: "method_crispr_ko", type: "alternative_to", weight: 5, label: "precedes" },
    { source: "method_spr", target: "method_bbmv_binding", type: "quantifies", weight: 6, label: "Kd measurement" },
  ],
};

export const mockEvidenceNetwork: RINetworkData = {
  nodes: [
    { id: "evidence_vip3a_binds_fgfr", entityId: "evidence_vip3a_binds_fgfr", entityType: "evidence", label: "Vip3A binds Sf-FGFR", type: "Finding", color: "#ebc146", size: 14 },
    { id: "evidence_no_cross_resistance", entityId: "evidence_no_cross_resistance", entityType: "evidence", label: "No Cry-Vip cross-resistance", type: "Finding", color: "#ebc146", size: 13 },
    { id: "evidence_cry1ac_tetrameric_pore", entityId: "evidence_cry1ac_tetrameric_pore", entityType: "evidence", label: "Cry1Ac forms tetrameric pore", type: "Finding", color: "#ebc146", size: 15 },
    { id: "evidence_cadherin_mutation_resistance", entityId: "evidence_cadherin_mutation_resistance", entityType: "evidence", label: "Cadherin mutation → Cry resistance", type: "Finding", color: "#ebc146", size: 14 },
    { id: "evidence_vip3a_membrane_conductance", entityId: "evidence_vip3a_membrane_conductance", entityType: "evidence", label: "Vip3A increases membrane conductance", type: "Finding", color: "#ebc146", size: 12 },
    { id: "evidence_cry_vip_competition_bbmv", entityId: "evidence_cry_vip_competition_bbmv", entityType: "evidence", label: "Cry-Vip binding competition in BBMV", type: "Finding", color: "#ebc146", size: 11 },
    { id: "evidence_abcc2_downregulation", entityId: "evidence_abcc2_downregulation", entityType: "evidence", label: "ABCC2 downregulation → resistance", type: "Finding", color: "#ebc146", size: 12 },
  ],
  links: [
    { source: "evidence_vip3a_binds_fgfr", target: "evidence_vip3a_membrane_conductance", type: "supports", weight: 6, label: "upstream of" },
    { source: "evidence_no_cross_resistance", target: "evidence_cry_vip_competition_bbmv", type: "contradicts", weight: 3, label: "vs." },
    { source: "evidence_cry1ac_tetrameric_pore", target: "evidence_cadherin_mutation_resistance", type: "contextualizes", weight: 4, label: "structural basis" },
    { source: "evidence_cadherin_mutation_resistance", target: "evidence_abcc2_downregulation", type: "parallels", weight: 5, label: "similar mechanism" },
    { source: "evidence_vip3a_binds_fgfr", target: "evidence_cry_vip_competition_bbmv", type: "contextualizes", weight: 4, label: "binding context" },
  ],
};

export const mockContradictionNetwork: RINetworkData = {
  nodes: [
    { id: "evidence_claim_shared_receptors", entityId: "evidence_claim_shared_receptors", entityType: "evidence", label: "Claim: Cry & Vip3A share receptors", type: "Finding", color: "#dc2626", size: 12 },
    { id: "evidence_claim_distinct_receptors", entityId: "evidence_claim_distinct_receptors", entityType: "evidence", label: "Claim: Cry & Vip3A use distinct receptors", type: "Finding", color: "#2563eb", size: 12 },
    { id: "evidence_bbmv_competition_data", entityId: "evidence_bbmv_competition_data", entityType: "evidence", label: "BBMV competition data", type: "Finding", color: "#ebc146", size: 10 },
    { id: "evidence_cross_resistance_data", entityId: "evidence_cross_resistance_data", entityType: "evidence", label: "Cross-resistance data", type: "Finding", color: "#ebc146", size: 10 },
    { id: "evidence_histopathology_diff", entityId: "evidence_histopathology_diff", entityType: "evidence", label: "Histopathology difference", type: "Finding", color: "#ebc146", size: 9 },
    { id: "evidence_crispr_ko_evidence", entityId: "evidence_crispr_ko_evidence", entityType: "evidence", label: "CRISPR KO evidence", type: "Finding", color: "#ebc146", size: 10 },
    { id: "evidence_concentration_dependent", entityId: "evidence_concentration_dependent", entityType: "evidence", label: "Resolution: concentration-dependent", type: "Finding", color: "#16512b", size: 11 },
  ],
  links: [
    { source: "evidence_claim_shared_receptors", target: "evidence_bbmv_competition_data", type: "supported_by", weight: 5, label: "supports" },
    { source: "evidence_claim_distinct_receptors", target: "evidence_cross_resistance_data", type: "supported_by", weight: 6, label: "supports" },
    { source: "evidence_claim_shared_receptors", target: "evidence_claim_distinct_receptors", type: "contradicts", weight: 4, label: "contradicts" },
    { source: "evidence_bbmv_competition_data", target: "evidence_cross_resistance_data", type: "contradicts", weight: 3, label: "vs." },
    { source: "evidence_claim_distinct_receptors", target: "evidence_histopathology_diff", type: "supported_by", weight: 4, label: "supports" },
    { source: "evidence_crispr_ko_evidence", target: "evidence_claim_distinct_receptors", type: "supported_by", weight: 5, label: "validates" },
    { source: "evidence_concentration_dependent", target: "evidence_claim_shared_receptors", type: "reconciles", weight: 3, label: "partially explains" },
    { source: "evidence_concentration_dependent", target: "evidence_claim_distinct_receptors", type: "reconciles", weight: 3, label: "partially explains" },
  ],
};

export function getNetworkData(mode: NetworkMode): RINetworkData {
  switch (mode) {
    case "method":
      return mockMethodNetwork;
    case "evidence":
      return mockEvidenceNetwork;
    case "contradiction":
      return mockContradictionNetwork;
    case "concept":
    default:
      return mockConceptNetwork;
  }
}

/* ── Node Inspector Data ── */

export interface NodeInspectorData {
  whyImportant: string;
  supportingPapers: string[];
  relatedTopics: string[];
  methods: string[];
  gaps: string[];
  contradictions: string[];
}

export function getNodeInspectorData(nodeId: string): NodeInspectorData {
  const data: Record<string, NodeInspectorData> = {
    concept_cry_toxin: {
      whyImportant: "Cry toxins are the most widely deployed insecticidal proteins in transgenic crops, protecting billions of dollars of agricultural value annually.",
      supportingPapers: ["Bravo et al. (2007)", "Soberón et al. (2009)", "Tabashnik et al. (2013)"],
      relatedTopics: ["topic_pore_formation", "topic_oligomerization", "topic_receptor_binding"],
      methods: ["BBMV binding", "Cryo-EM", "Bioassay"],
      gaps: ["gap_vip3a_pore_structure"],
      contradictions: ["Oligomerization necessity debated for some Cry subfamilies"],
    },
    concept_vip3a: {
      whyImportant: "Vip3A is the key alternative to Cry toxins in second-generation Bt crops, with no known cross-resistance. Its receptor and pore mechanism remain major open questions.",
      supportingPapers: ["Jiang et al. (2024)", "Liu et al. (2025)", "Chakroun et al. (2016)"],
      relatedTopics: ["topic_pore_formation", "topic_receptor_binding"],
      methods: ["CRISPR KO", "SPR", "Pull-down + MS"],
      gaps: ["gap_vip3a_pore_structure", "gap_vip3a_receptor_in_vivo"],
      contradictions: ["Disputed whether Vip3A oligomerizes before membrane insertion"],
    },
    concept_pore_formation: {
      whyImportant: "Pore formation is the terminal lytic event — understanding it is essential for engineering toxin potency and overcoming resistance.",
      supportingPapers: ["Bravo et al. (2007)", "Endo et al. (2022) — cryo-EM of pore"],
      relatedTopics: ["topic_oligomerization", "topic_receptor_binding"],
      methods: ["Planar lipid bilayer", "Cryo-EM", "MD simulation"],
      gaps: ["gap_vip3a_pore_structure"],
      contradictions: ["Whether the pore is tetrameric or hexameric for Cry toxins"],
    },
  };
  return data[nodeId] ?? {
    whyImportant: "Detailed analysis for this node is being prepared.",
    supportingPapers: [],
    relatedTopics: [],
    methods: [],
    gaps: [],
    contradictions: [],
  };
}

/* ============================================================
   6. Entity Helpers
   ============================================================ */

/**
 * Resolve a topic query param to a stable topic ID.
 * Supports backward-compatible aliases (e.g. "pore_formation" → "topic_pore_formation").
 */
export function resolveTopicAlias(param: string | null): string | null {
  if (!param) return null;

  // Already a stable ID
  if (param.startsWith("topic_")) return param;

  // Known backward-compatible aliases
  const aliasMap: Record<string, string> = {
    pore_formation: "topic_pore_formation",
    oligomerization: "topic_oligomerization",
    cryo_em: "topic_cryo_em",
    binding_assays: "topic_binding_assays",
    crispr: "topic_crispr",
    bioassay: "topic_bioassay",
    bioinformatics: "topic_bioinformatics",
    receptor_mutation: "topic_receptor_mutation",
    resistance_mgmt: "topic_resistance_mgmt",
    model_organism: "topic_model_organism",
    signal_transduction: "topic_signal_transduction",
    cell_death: "topic_cell_death",
    cry_structure: "topic_cry_structure",
    vip_structure: "topic_vip_structure",
    domain_function: "topic_domain_function",
    transgenic: "topic_transgenic",
    stacking: "topic_stacking",
    midgut_protease: "topic_midgut_protease",
    immune_response: "topic_immune_response",
    behavioral: "topic_behavioral",
    sf: "topic_sf",
    hz: "topic_hz",
    se: "topic_se",
    dvv: "topic_dvv",
  };

  return aliasMap[param] ?? `topic_${param}`;
}

/** Get research gaps linked to a topic ID. */
export function getResearchGapsByTopicId(topicId: string): ResearchGapItem[] {
  return mockResearchGaps.filter((g) => g.linkedTopicIds.includes(topicId));
}

/** Get research gaps linked to a concept ID. */
export function getResearchGapsByConceptId(conceptId: string): ResearchGapItem[] {
  return mockResearchGaps.filter((g) => g.linkedConceptIds.includes(conceptId));
}

/** Get a topic detail by its stable ID, with alias fallback. */
export function getTopicById(topicId: string): TopicDetail | null {
  // Try direct lookup first
  if (mockTopicDetails[topicId]) return mockTopicDetails[topicId];
  // Try without topic_ prefix
  const bare = topicId.replace(/^topic_/, "");
  if (mockTopicDetails[bare]) return mockTopicDetails[bare];
  // Try with topic_ prefix
  if (mockTopicDetails[`topic_${bare}`]) return mockTopicDetails[`topic_${bare}`];
  return null;
}

/** Get research gaps matching a network node by shared entity relationships. */
export function getResearchGapsByNode(node: RINetworkNode): ResearchGapItem[] {
  const entityId = node.entityId ?? node.id;
  return mockResearchGaps.filter(
    (g) =>
      g.id === entityId ||
      g.linkedTopicIds.includes(entityId) ||
      g.linkedConceptIds.includes(entityId) ||
      g.linkedPaperIds.includes(entityId) ||
      g.linkedEvidenceIds.includes(entityId),
  );
}

/* ============================================================
   7. Research Papers
   ============================================================ */

export type EvidenceRole = "direct" | "indirect" | "contradictory" | "background";

export interface ResearchPaper {
  id: string;
  title: string;
  authors: string[];
  year: number;
  journal: string;
  doi?: string;
  abstract?: string;
  keyFindings: string[];
  methods: string[];
  linkedTopicIds: string[];
  linkedConceptIds: string[];
  linkedEvidenceIds: string[];
  linkedGapIds: string[];
  relevanceScore?: number;
  evidenceRole?: EvidenceRole;
}

export const mockResearchPapers: ResearchPaper[] = [
  {
    id: "paper_jiang_2024",
    title: "Identification of Sf-FGFR as a functional receptor for Vip3Aa in Spodoptera frugiperda",
    authors: ["Jiang, L.", "Wang, Y.", "Zhang, H.", "Liu, X."],
    year: 2024,
    journal: "Insect Biochemistry and Molecular Biology",
    keyFindings: [
      "Sf-FGFR was identified as a Vip3Aa binding protein by pull-down and mass spectrometry",
      "CRISPR knockout of Sf-FGFR in Sf9 cells reduced Vip3Aa binding by ~70%",
      "Sf-FGFR is the first validated Vip3A receptor candidate in any insect species",
    ],
    methods: ["Pull-down assay", "Mass spectrometry", "CRISPR-Cas9 knockout", "SPR"],
    linkedTopicIds: ["topic_pore_formation", "topic_binding_assays"],
    linkedConceptIds: ["concept_vip3a", "concept_receptor_binding"],
    linkedEvidenceIds: ["evidence_vip3a_binds_fgfr"],
    linkedGapIds: ["gap_vip3a_pore_structure", "gap_vip3a_receptor_in_vivo"],
    relevanceScore: 95,
    evidenceRole: "direct",
  },
  {
    id: "paper_liu_2025",
    title: "Scavenger Receptor-C mediates Vip3Aa cytotoxicity independently of the Cry toxin receptor pathway",
    authors: ["Liu, X.", "Chen, W.", "Jiang, L."],
    year: 2025,
    journal: "Proceedings of the National Academy of Sciences",
    keyFindings: [
      "Scavenger Receptor-C (SR-C) was identified as a second Vip3Aa receptor candidate",
      "SR-C knockout does not affect Cry1Ac toxicity, confirming distinct receptor pathways",
      "Vip3Aa binds SR-C with Kd ~ 45 nM by SPR",
    ],
    methods: ["CRISPR-Cas9 knockout", "SPR", "Diet overlay bioassay"],
    linkedTopicIds: ["topic_pore_formation", "topic_binding_assays", "topic_receptor_mutation"],
    linkedConceptIds: ["concept_vip3a", "concept_receptor_binding", "concept_cry_toxin"],
    linkedEvidenceIds: ["evidence_no_cross_resistance", "evidence_claim_distinct_receptors"],
    linkedGapIds: ["gap_vip3a_pore_structure", "gap_cry_vip_receptor_contradiction"],
    relevanceScore: 92,
    evidenceRole: "direct",
  },
  {
    id: "paper_tabashnik_2024",
    title: "No cross-resistance between Cry1Ab and Vip3Aa in field-derived strains of Helicoverpa zea",
    authors: ["Tabashnik, B.E.", "Carrière, Y.", "Fabrick, J.A."],
    year: 2024,
    journal: "Pest Management Science",
    keyFindings: [
      "Field-derived Cry1Ab-resistant H. zea strains showed no cross-resistance to Vip3Aa",
      "LC₅₀ values for Vip3Aa were identical between Cry-resistant and susceptible strains",
      "Results support independent receptor pathways for Cry and Vip toxins",
    ],
    methods: ["Diet overlay bioassay", "F₂ screen", "Diagnostic concentration assay"],
    linkedTopicIds: ["topic_receptor_mutation", "topic_resistance_mgmt"],
    linkedConceptIds: ["concept_cry_toxin", "concept_vip3a", "concept_resistance"],
    linkedEvidenceIds: ["evidence_no_cross_resistance", "evidence_claim_distinct_receptors"],
    linkedGapIds: ["gap_cry_vip_receptor_contradiction"],
    relevanceScore: 88,
    evidenceRole: "direct",
  },
  {
    id: "paper_wang_2024",
    title: "Cryo-EM structure of the Cry1Ac prepore complex at 3.2 Å resolution",
    authors: ["Wang, H.", "Li, Q.", "Zhang, Y."],
    year: 2024,
    journal: "Nature Structural & Molecular Biology",
    keyFindings: [
      "Cry1Ac prepore assembles as a domain-swapped tetramer at neutral pH",
      "Domain I α-helices undergo a ~30° conformational change upon oligomerization",
      "The prepore structure explains the pH-dependence of membrane insertion",
    ],
    methods: ["Cryo-EM", "Single-particle analysis", "Molecular dynamics simulation"],
    linkedTopicIds: ["topic_pore_formation", "topic_cry_structure", "topic_cryo_em"],
    linkedConceptIds: ["concept_cry_toxin", "concept_pore_formation", "concept_oligomerization"],
    linkedEvidenceIds: ["evidence_cry1ac_tetrameric_pore"],
    linkedGapIds: ["gap_vip3a_pore_structure"],
    relevanceScore: 90,
    evidenceRole: "direct",
  },
  {
    id: "paper_bravo_2007",
    title: "Mode of action of Bacillus thuringiensis Cry and Cyt toxins and their potential for insect control",
    authors: ["Bravo, A.", "Gill, S.S.", "Soberón, M."],
    year: 2007,
    journal: "Toxicon",
    keyFindings: [
      "Comprehensive review of the sequential binding model for Cry toxin mode of action",
      "Cadherin binding triggers proteolytic cleavage of helix α-1 and oligomerization",
      "ABCC2 and alkaline phosphatase serve as secondary receptors for Cry toxins",
    ],
    methods: ["Review", "BBMV binding", "Planar lipid bilayer"],
    linkedTopicIds: ["topic_pore_formation", "topic_oligomerization", "topic_receptor_binding"],
    linkedConceptIds: ["concept_cry_toxin", "concept_pore_formation", "concept_cadherin", "concept_abcc2"],
    linkedEvidenceIds: [],
    linkedGapIds: [],
    relevanceScore: 100,
    evidenceRole: "background",
  },
];

/* ── Paper helpers ── */

export function getPaperById(paperId: string): ResearchPaper | null {
  return mockResearchPapers.find((p) => p.id === paperId) ?? null;
}

export function getPapersByGapId(gapId: string): ResearchPaper[] {
  return mockResearchPapers.filter((p) => p.linkedGapIds.includes(gapId));
}

export function getPapersByTopicId(topicId: string): ResearchPaper[] {
  return mockResearchPapers.filter((p) => p.linkedTopicIds.includes(topicId));
}

export function getPapersByConceptId(conceptId: string): ResearchPaper[] {
  return mockResearchPapers.filter((p) => p.linkedConceptIds.includes(conceptId));
}

export function getPapersByEvidenceId(evidenceId: string): ResearchPaper[] {
  return mockResearchPapers.filter((p) => p.linkedEvidenceIds.includes(evidenceId));
}

/** Demo note — subtle, non-defensive */
export const DEMO_PAPER_NOTE =
  "Demo paper records are structured to match the future real-data schema.";

/* ============================================================
   8. Unified Entity Model — BaseEntity + Entity Graph Schema
   ============================================================ */

/**
 * Every entity in the Research OS shares a BaseEntity.
 * Concrete types (Paper, Concept, Gap, Hypothesis, etc.)
 * extend this with domain-specific fields.
 */
export type EntityType =
  | "paper"
  | "concept"
  | "method"
  | "evidence"
  | "topic"
  | "research_gap"
  | "hypothesis";

export interface BaseEntity {
  /** Stable identifier, e.g. "paper_jiang_2024", "concept_vip3a" */
  entityId: string;
  /** Discriminant for entity graph traversal */
  entityType: EntityType;
  /** Human-readable label */
  title: string;
  /** One-sentence summary for graph tooltips */
  summary: string;
  linkedTopicIds: string[];
  linkedConceptIds: string[];
  linkedEvidenceIds: string[];
  linkedPaperIds: string[];
  linkedGapIds: string[];
}

/* ── Hypothesis ── */

export interface Hypothesis extends BaseEntity {
  entityType: "hypothesis";
  /** The claim being tested */
  statement: string;
  /** Who proposed it (author lineage or source) */
  proposedBy: string;
  /** Current status */
  status: "untested" | "supported" | "refuted" | "partially_supported" | "contradicted";
  /** Evidence that supports this hypothesis */
  supportingEvidenceIds: string[];
  /** Evidence that contradicts this hypothesis */
  contradictingEvidenceIds: string[];
  /** Gaps this hypothesis aims to address */
  targetGapIds: string[];
  /** What experiment or analysis would validate or refute this */
  validationPath: string;
}

export const mockHypotheses: Hypothesis[] = [
  {
    entityId: "hypothesis_domain_i_pore_formation",
    entityType: "hypothesis",
    title: "Vip3A Domain I forms the pore-lining region",
    summary:
      "By analogy with Cry toxins, Vip3A Domain I (N-terminal region) contains the membrane-insertion elements that form the lytic pore.",
    statement:
      "Vip3A Domain I α-helices insert into the midgut epithelial membrane to form an ion-permeable pore.",
    proposedBy: "Structural analogy to Cry toxin Domain I",
    status: "untested",
    supportingEvidenceIds: [
      "evidence_vip3a_membrane_conductance",
    ],
    contradictingEvidenceIds: [],
    targetGapIds: ["gap_vip3a_pore_structure"],
    validationPath:
      "Express Vip3A Domain I fragment. Test membrane insertion by planar lipid bilayer electrophysiology. If Domain I alone increases conductance, resolve its structure by cryo-EM.",
    linkedTopicIds: ["topic_pore_formation"],
    linkedConceptIds: ["concept_vip3a", "concept_pore_formation"],
    linkedEvidenceIds: ["evidence_vip3a_membrane_conductance"],
    linkedPaperIds: ["paper_jiang_2024", "paper_liu_2025"],
    linkedGapIds: ["gap_vip3a_pore_structure"],
  },
  {
    entityId: "hypothesis_vip3a_cry_distinct_receptors",
    entityType: "hypothesis",
    title: "Vip3A and Cry toxins use distinct, non-overlapping receptor pathways",
    summary:
      "The two toxin families bind different receptors and form pores independently, enabling reliable resistance management through stacking.",
    statement:
      "Vip3Aa and Cry1Ab/Cry1Ac bind to distinct midgut receptors with no shared binding sites, and resistance to one does not confer cross-resistance to the other.",
    proposedBy: "Tabashnik et al. (2024) — field resistance data",
    status: "partially_supported",
    supportingEvidenceIds: [
      "evidence_no_cross_resistance",
      "evidence_claim_distinct_receptors",
    ],
    contradictingEvidenceIds: [
      "evidence_cry_vip_competition_bbmv",
      "evidence_claim_shared_receptors",
    ],
    targetGapIds: ["gap_cry_vip_receptor_contradiction"],
    validationPath:
      "2×2 factorial competition SPR experiment: 4 concentrations each of Cry1Ac and Vip3Aa on same BBMV prep. If no saturable competition, hypothesis supported. If competition is concentration-dependent, hypothesis refuted.",
    linkedTopicIds: ["topic_receptor_mutation", "topic_resistance_mgmt"],
    linkedConceptIds: ["concept_cry_toxin", "concept_vip3a", "concept_receptor_binding"],
    linkedEvidenceIds: [
      "evidence_no_cross_resistance",
      "evidence_claim_distinct_receptors",
      "evidence_cry_vip_competition_bbmv",
    ],
    linkedPaperIds: ["paper_liu_2025", "paper_tabashnik_2024"],
    linkedGapIds: ["gap_cry_vip_receptor_contradiction"],
  },
  {
    entityId: "hypothesis_sr_c_primary_vip3a_receptor",
    entityType: "hypothesis",
    title: "Scavenger Receptor-C is the primary functional receptor for Vip3Aa in Lepidoptera",
    summary:
      "SR-C mediates the majority of Vip3Aa cytotoxicity, and its presence is necessary for Vip3Aa toxicity in lepidopteran pests.",
    statement:
      "SR-C binds Vip3Aa with high affinity (Kd < 50 nM) and SR-C knockout abolishes Vip3Aa toxicity in whole insects.",
    proposedBy: "Liu et al. (2025) — SR-C identification and in vitro characterization",
    status: "partially_supported",
    supportingEvidenceIds: [
      "evidence_vip3a_binds_fgfr",
    ],
    contradictingEvidenceIds: [],
    targetGapIds: ["gap_vip3a_receptor_in_vivo", "gap_cross_species_receptor"],
    validationPath:
      "Generate SR-C homozygous KO S. frugiperda line. Bioassay with Vip3Aa at 6 concentrations. If LC₅₀ shifts > 10-fold vs wild-type, SR-C confirmed as primary functional receptor. Extend to H. virescens for cross-species validation.",
    linkedTopicIds: ["topic_pore_formation", "topic_binding_assays", "topic_model_organism"],
    linkedConceptIds: ["concept_vip3a", "concept_receptor_binding"],
    linkedEvidenceIds: ["evidence_vip3a_binds_fgfr"],
    linkedPaperIds: ["paper_jiang_2024", "paper_liu_2025"],
    linkedGapIds: ["gap_vip3a_receptor_in_vivo", "gap_cross_species_receptor"],
  },
];

/* ── Hypothesis helpers ── */

export function getHypothesesByGapId(gapId: string): Hypothesis[] {
  return mockHypotheses.filter((h) => h.targetGapIds.includes(gapId));
}

export function getHypothesisById(hypothesisId: string): Hypothesis | null {
  return mockHypotheses.find((h) => h.entityId === hypothesisId) ?? null;
}

/* ── Entity Graph traversal helpers ── */

/** Resolve an entity of any type by its entityId, returning it as a BaseEntity. */
export function resolveEntityById(entityId: string): BaseEntity | null {
  // Order: try each concrete type
  const paper = getPaperById(entityId);
  if (paper) return paperToBaseEntity(paper);
  const gap = mockResearchGaps.find((g) => g.id === entityId);
  if (gap) return gapToBaseEntity(gap);
  const hypothesis = getHypothesisById(entityId);
  if (hypothesis) return hypothesis;
  // Future: topic, concept, method, evidence lookups
  return null;
}

/** Convert ResearchPaper → BaseEntity */
function paperToBaseEntity(p: ResearchPaper): BaseEntity {
  return {
    entityId: p.id,
    entityType: "paper",
    title: p.title,
    summary: p.keyFindings[0] ?? "",
    linkedTopicIds: p.linkedTopicIds,
    linkedConceptIds: p.linkedConceptIds,
    linkedEvidenceIds: p.linkedEvidenceIds,
    linkedPaperIds: [],
    linkedGapIds: p.linkedGapIds,
  };
}

/** Convert ResearchGapItem → BaseEntity */
function gapToBaseEntity(g: ResearchGapItem): BaseEntity {
  return {
    entityId: g.id,
    entityType: "research_gap",
    title: g.title,
    summary: g.missingSummary,
    linkedTopicIds: g.linkedTopicIds,
    linkedConceptIds: g.linkedConceptIds,
    linkedEvidenceIds: g.linkedEvidenceIds,
    linkedPaperIds: g.linkedPaperIds,
    linkedGapIds: [],
  };
}

/** All entity counts for schema validation */
export const ENTITY_COUNTS = {
  papers: 5,
  concepts: 12,
  methods: 8,
  evidences: 14,
  topics: 25,
  researchGaps: 6,
  hypotheses: 3,
  total: 73,
} as const;
