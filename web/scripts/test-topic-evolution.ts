/**
 * Tests for topic-evolution.ts
 * Run: npx tsx scripts/test-topic-evolution.ts
 */

import { buildEvidenceDrivenPhaseAnalysis, extractPaperEvidence, cleanEvidenceText, buildEvolutionSummary } from "../lib/topic-evolution";

let passed = 0, failed = 0;
function assert(cond: boolean, label: string) { if (cond) passed++; else { failed++; console.error(`  FAIL: ${label}`); } }

// Test 1: extractPaperEvidence with summary
const e1 = extractPaperEvidence({ paper_id: "p1", title: "Test", summary: '{"Core Finding":[{"text":"Finding A","citations":["S001"]}]}' });
assert(e1.parsed !== null, "parsed summary exists");
assert(e1.parsed!.coreFindings.length >= 1, "has core findings");
assert(!e1.parsed!.coreFindings[0].includes("S001"), "no citation leak in coreFindings");

// Test 2: extractPaperEvidence without summary
const e2 = extractPaperEvidence({ paper_id: "p2", title: "No summary paper" });
assert(e2.parsed === null, "null parsed when no summary");
assert(e2.raw_text === null, "null raw_text");

// Test 3: cleanEvidenceText
const cleaned = cleanEvidenceText('{"Core Finding":[{"text":"hello world test"}]}');
assert(cleaned.includes("hello world test"), "strips JSON structure: got " + JSON.stringify(cleaned));
assert(cleanEvidenceText("short") === "", "filters too-short text");

// Test 4: buildEvidenceDrivenPhaseAnalysis with no summaries
const phases = [
  { phase: "early", label: "Early phase", year_range: [2000, 2005] as [number, number], paper_count: 3, papers: [{ paper_id: "p1", title: "Paper 1" }] },
  { phase: "recent", label: "Recent phase", year_range: [2020, 2024] as [number, number], paper_count: 2, papers: [{ paper_id: "p2", title: "Paper 2" }] },
];
const result = buildEvidenceDrivenPhaseAnalysis(phases);
assert(result.length === 2, "2 phases");
const early = result[0];
assert(early.confidence === "low", "low confidence when no summaries");
assert(early.focus === null, "no focus without evidence");
assert(early.key_conclusions.length === 0, "no key conclusions without evidence");
assert(early.open_questions.length === 0, "no open questions without evidence");
assert(early.change_from_previous === "Baseline phase for this topic.", "early phase baseline text");

// Test 5: With summaries including limitations
const phases2 = [
  { phase: "early", label: "Early", year_range: [2000, 2005] as [number, number], paper_count: 2, keywords: ["test"], papers: [
    { paper_id: "p1", title: "T1", summary: JSON.stringify({ "Core Finding": [{ "text": "CF1 content here for analysis.", "citations": ["S001"] }], "Limitations": [{ "text": "Sample size was limited and further validation needed.", "citations": ["S002"] }] }) },
    { paper_id: "p2", title: "T2", summary: JSON.stringify({ "Core Finding": [{ "text": "CF2 second finding.", "citations": ["S003"] }], "Evidence": [{ "text": "Multiple lines support this.", "citations": ["S004"] }] }) },
  ]},
];
const result2 = buildEvidenceDrivenPhaseAnalysis(phases2);
const ephase = result2[0];
assert(ephase.confidence === "high", "high confidence with 2 summaries");
assert(ephase.focus !== null, "focus present");
assert(!ephase.focus!.includes("Research in this phase centered on"), "no template phrase in focus");
assert(ephase.key_conclusions.length >= 1, "has key conclusions");
assert(ephase.evidence_quotes.length >= 1, "has evidence quotes");
assert(ephase.milestone_papers.length >= 1, "has milestone papers");
assert(ephase.open_questions.length >= 1, "has open questions from limitations");
// Verify no citation leaks
const allText = JSON.stringify(ephase);
assert(!allText.includes("S001"), "S001 not in output");
assert(!allText.includes("S002"), "S002 not in output");
assert(!allText.includes('"citations"'), "citations field not in output");

// Test 6: No limitations → no open questions
const phases3 = [
  { phase: "early", label: "Early", year_range: [2000, 2005] as [number, number], paper_count: 1, papers: [
    { paper_id: "p1", title: "T1", summary: JSON.stringify({ "Core Finding": [{ "text": "Only finding, no limitations or gaps.", "citations": ["S001"] }] }) },
  ]},
];
const result3 = buildEvidenceDrivenPhaseAnalysis(phases3);
assert(result3[0].open_questions.length === 0, "no open questions when no limitations");
assert(result3[0].method_signals.length === 0, "no method signals without method words");
assert(result3[0].change_from_previous !== null, "has change text");

// Test 7: Evolution summary
const summary = buildEvolutionSummary(result2);
assert(summary.length > 10, "evolution summary exists");

console.log(`\nPassed: ${passed}, Failed: ${failed}`);
process.exit(failed > 0 ? 1 : 0);
