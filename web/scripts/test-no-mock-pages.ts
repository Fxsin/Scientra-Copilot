/**
 * No-Mock Guard Test — ensures user-facing pages do not import or render mock data.
 */
import * as fs from "fs";

const PAGES = [
  "app/research-gaps/page.tsx",
  "app/knowledge-network/page.tsx",
  "app/report/page.tsx",
  "app/topic-explorer/page.tsx",
];

const FORBIDDEN = [
  "researchIntelligenceMock",
  "mockResearchGaps",
  "mockHotspots",
  "mockKnowledgeNetwork",
  "mockReport",
  "mockTopicExplorer",
  "Bt Toxin Mode of Action",
  "Vip3A pore structure is unknown",
  "standardized quantitative binding assay",
  "resistance allele surveillance",
  'paperCount: 34',
  'paperCount":34',
  'projectName: "Bt Toxin Mode of Action"',
];

let passed = 0;
let failed = 0;

for (const page of PAGES) {
  const content = fs.readFileSync(page, "utf-8");
  let pageOk = true;

  for (const forbidden of FORBIDDEN) {
    if (content.includes(forbidden)) {
      console.log(`  ❌ ${page}: contains "${forbidden}"`);
      pageOk = false;
    }
  }

  if (pageOk) {
    console.log(`  ✅ ${page}`);
    passed++;
  } else {
    failed++;
  }
}

console.log(`\n========================================`);
console.log(`No-Mock Test: ${passed} passed, ${failed} failed`);
console.log(`========================================`);
process.exit(failed > 0 ? 1 : 0);
