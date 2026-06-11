/**
 * Regression tests for parseAISummary.
 *
 * Run: npx tsx scripts/test-summary-parser.ts
 *
 * Ensures JSON-like / broken-JSON / BOM / YAML summaries
 * NEVER leak raw structural artifacts into user-visible text areas.
 */

import { parseAISummary, cleanSummarySnippet, type ParsedSummary } from "../lib/summary-parser";

let passed = 0;
let failed = 0;

function assert(condition: boolean, label: string) {
  if (condition) { passed++; } else { failed++; console.error(`  FAIL: ${label}`); }
}

function assertNoJsonLeak(items: string[], label: string) {
  for (const item of items) {
    assert(!item.includes('"Core Finding"'), `${label}: no "Core Finding" label`);
    assert(!item.includes('"Evidence"'), `${label}: no "Evidence" label`);
    assert(!item.includes('"text":'), `${label}: no "text": field`);
    assert(!item.includes('"citations"'), `${label}: no "citations" field`);
    assert(item !== "{", `${label}: not lone curly`);
    assert(item !== "}", `${label}: not lone curly`);
    assert(item !== "[", `${label}: not lone bracket`);
    assert(item !== "]", `${label}: not lone bracket`);
  }
}

function assertTextPresent(items: string[], label: string) {
  assert(items.length > 0, `${label}: has items`);
  for (const item of items) {
    assert(item.length > 10, `${label}: reasonable length`);
  }
}

function runTest(name: string, raw: string, checks: (r: ParsedSummary) => void) {
  console.log(`\n=== ${name} ===`);
  const result = parseAISummary(raw);
  if (!result) { console.error("  FAIL: parseAISummary returned null"); failed++; return; }
  checks(result);
  // Universal assertions
  const tk = result.takeaway ?? "";
  assert(tk !== "{", "takeaway not lone curly");
  assert(tk !== "[", "takeaway not lone bracket");
  assert(!tk.includes('"Core Finding"'), "takeaway no JSON labels");
  assertNoJsonLeak(result.others, "others");
  assertNoJsonLeak(result.coreFindings, "coreFindings");
  assertNoJsonLeak(result.evidence, "evidence");
  assertNoJsonLeak(result.methods, "methods");
  assertNoJsonLeak(result.limitations, "limitations");
  assertNoJsonLeak(result.gaps, "gaps");
}

// ── Test 1: Markdown-like ──
runTest("Markdown", [
  "**Core Finding**: This paper proposes a reusable framework.",
  "**Evidence**: The authors evaluated multiple datasets.",
  "**Methods**: BBMV binding assays and RNAi knockdown.",
].join("\n"), (r) => {
  assert(r.coreFindings.length >= 1, "has core finding");
  assert(r.evidence.length >= 1, "has evidence");
  assert(r.methods.length >= 1, "has methods");
});

// ── Test 2: Valid JSON-like ──
const validJson = JSON.stringify({
  "Core Finding": [
    { "text": "This study identifies a general mechanism.", "citations": ["S001"] },
  ],
  "Evidence": [
    { "text": "Multiple experiments support the conclusion.", "citations": ["S002"] },
  ],
  "Methods": [
    { "text": "BBMV binding and RNAi knockdown were used." },
  ],
});
runTest("Valid JSON", validJson, (r) => {
  assert(r.coreFindings.length >= 1, "has core finding from JSON");
  assert(r.evidence.length >= 1, "has evidence from JSON");
  assert(r.methods.length >= 1, "has methods from JSON");
  assertTextPresent(r.coreFindings, "coreFindings text");
  // Verify citations NOT in output
  const all = [...r.coreFindings, ...r.evidence, ...r.methods, ...r.others];
  assert(!all.some(t => t.includes("S001")), "S001 citation not in output");
  assert(!all.some(t => t.includes("S002")), "S002 citation not in output");
});

// ── Test 3: YAML frontmatter + JSON ──
const yamlJson = [
  "---",
  "title: Example Paper",
  "framework: Scientra Copilot V1",
  "summary_date: 2026-06-10",
  "summary_tool: Scientra Copilot Summary Agent",
  "---",
  JSON.stringify({
    "Core Finding": [
      { "text": "Finding after frontmatter.", "citations": ["S001"] },
    ],
    "Evidence": [
      { "text": "Evidence after frontmatter.", "citations": ["S002"] },
    ],
  }),
].join("\n");
runTest("YAML + JSON", yamlJson, (r) => {
  assert(r.coreFindings.length >= 1, "has core finding after YAML strip");
  assert(r.evidence.length >= 1, "has evidence after YAML strip");
  assertTextPresent(r.coreFindings, "CF after YAML");
  const all = [...r.coreFindings, ...r.evidence, ...r.others];
  assert(!all.some(t => t.includes("title:") || t.includes("framework:") || t.includes("summary_tool:")), "no YAML metadata in output");
});

// ── Test 4: BOM + YAML + JSON ──
const bomYamlJson = "﻿" + yamlJson;
runTest("BOM + YAML + JSON", bomYamlJson, (r) => {
  assert(r.coreFindings.length >= 1, "has core finding despite BOM");
  assert(r.evidence.length >= 1, "has evidence despite BOM");
  assertTextPresent(r.coreFindings, "CF after BOM+YAML");
});

// ── Test 5: BOM + YAML + truncated JSON ──
const truncJson = [
  "{",
  '  "Core Finding": [',
  '    {',
  '      "text": "This is a complete text field that should be extracted.",',
  '      "citations": ["S001", "S016"]',
  "    },",
  '    {',
  '      "text": "This second text may be incomplete', // intentionally truncated
].join("\n");
const bomYamlTrunc = "﻿---\ntitle: Example\n---\n" + truncJson;
runTest("BOM + YAML + truncated JSON", bomYamlTrunc, (r) => {
  // Should extract at least the first complete "text" field
  const all = [...r.coreFindings, ...r.evidence, ...r.methods, ...r.others];
  assert(all.some(t => t.includes("complete text field")), "extracts complete text field from broken JSON");
  assert(!all.some(t => t.includes("may be incomplete")), "does NOT extract incomplete text field");
  assert(!all.some(t => t.includes("S001") || t.includes("S016")), "no citation leak");
  assert(!all.some(t => t === "{" || t === "}" || t === "["), "no JSON brackets in output");
});

// ── Test 6: Plain text ──
runTest("Plain text", "This is a plain summary paragraph.\nAnother supporting paragraph.", (r) => {
  assert(r.takeaway !== null, "has takeaway");
  assert(r.takeaway!.length > 10, "takeaway has content");
  assert(r.others.length >= 1, "has supporting text");
});

// ── Test 7: Broken unparseable JSON (no valid text fields) ──
const garbageJson = [
  "{",
  '  "Core Finding": [',
  '    { "broken_field": "no text key here" }',
  "]",
  "}", // this is technically valid JSON but has no "text" fields
].join("\n");
const result7 = parseAISummary(garbageJson);
console.log("\n=== Broken JSON (no text fields) ===");
if (result7) {
  const all = [...result7.coreFindings, ...result7.evidence, ...result7.methods, ...result7.others];
  assert(all.length === 0, "no garbage content leaked");
  assert(result7.takeaway === null, "takeaway is null for garbage input");
} else {
  // Returning null is also acceptable
  passed++;
}
assert(true, "does not crash on garbage input");

// ── Test 8: Snippet cleaner ──
console.log("\n=== cleanSummarySnippet ===");
const snippet1 = cleanSummarySnippet('**Core Finding**: Domain shuffling reveals exchangeable domain. **Evidence**: More text here.');
assert(snippet1 !== null, "snippet extracted");
assert(snippet1!.includes("Domain"), "snippet contains content");
assert(!snippet1!.includes("**"), "snippet has no markdown markers");
assert(!snippet1!.includes("Core Finding"), "snippet has no label");

const snippet2 = cleanSummarySnippet(validJson);
assert(snippet2 !== null, "snippet from JSON");
assert(!snippet2!.includes("{"), "snippet no JSON braces");

// ── Summary ──
console.log(`\n${"=".repeat(40)}`);
console.log(`Passed: ${passed}, Failed: ${failed}`);
console.log(`${"=".repeat(40)}`);

process.exit(failed > 0 ? 1 : 0);
