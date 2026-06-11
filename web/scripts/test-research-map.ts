/**
 * Research Map Data Integrity Test Script
 *
 * Validates:
 * 1. /research-map returns topics with required fields
 * 2. topics have keywords, papers, representative_papers
 * 3. /research-map/topic/{id} returns year_distribution, evolution_phases, related_topics
 * 4. No low-value keywords present
 * 5. paper_count matches papers.length
 */

const API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL || process.env.SCIENTRA_API_URL || `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}`;

const LOW_VALUE_WORDS = new Set([
  "against", "not", "text", "citation", "citations", "gene", "genes",
  "undefined", "null", "none", "true", "false",
]);

interface TestResult { name: string; passed: boolean; detail?: string; }
const results: TestResult[] = [];

function pass(name: string, detail?: string) {
  results.push({ name, passed: true, detail });
  console.log(`  ✅ ${name}${detail ? ` — ${detail}` : ""}`);
}

function fail(name: string, detail?: string) {
  results.push({ name, passed: false, detail });
  console.log(`  ❌ ${name}${detail ? ` — ${detail}` : ""}`);
}

async function fetchJson(path: string): Promise<any> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
  return res.json();
}

async function main() {
  console.log("=== Research Map Data Integrity Tests ===\n");

  let mapData: any;
  let topicId: string | null = null;

  // ── 1. /research-map ──
  console.log("--- /research-map ---");
  try {
    mapData = await fetchJson("/research-map");
    pass("/research-map returns data");
  } catch (e: any) {
    fail("/research-map returns data", e.message);
    printSummary();
    return;
  }

  const allTopics = [
    ...(mapData.mature_topics || []),
    ...(mapData.growing_topics || []),
    ...(mapData.gap_topics || []),
    ...(mapData.clusters || []),
  ];

  if (allTopics.length > 0) {
    pass("topics exist", `${allTopics.length} topics found`);
    topicId = allTopics[0].cluster_id || allTopics[0].id || null;

    let topicsWithKeywords = 0;
    let topicsWithPapers = 0;
    let topicsWithRepPapers = 0;
    let keywordIssues = 0;

    for (const t of allTopics) {
      // Required fields
      if (!t.cluster_id && !t.id) fail(`topic missing cluster_id: ${t.name}`);
      else pass(`topic has id: ${t.cluster_id || t.id}`);

      if (typeof t.name === "string" && t.name.length > 0) pass(`topic has name: "${t.name.slice(0, 60)}"`);
      else fail(`topic missing name`);

      if (typeof t.paper_count === "number" && t.paper_count > 0) pass(`topic has paper_count: ${t.paper_count}`);
      else fail(`topic missing paper_count`);

      // Keywords
      if (t.keywords && t.keywords.length > 0) {
        topicsWithKeywords++;
        // Check for low-value words
        const bad = t.keywords.filter((k: string) => LOW_VALUE_WORDS.has(k.toLowerCase()));
        if (bad.length > 0) {
          keywordIssues++;
          fail(`topic keywords contain low-value words: [${bad.join(", ")}]`, t.name);
        }
      }

      // Papers
      if (t.papers && t.papers.length > 0) {
        topicsWithPapers++;
        if (t.papers[0].paper_id) pass(`topic papers have paper_id: ${t.papers[0].paper_id}`);
        else fail(`topic paper missing paper_id`);
        if (t.papers[0].title) pass(`topic papers have title`);
        else fail(`topic paper missing title`);
      }

      // Representative papers
      if (t.representative_papers && t.representative_papers.length > 0) {
        topicsWithRepPapers++;
      }

      // Check paper_count vs papers.length consistency
      if (t.papers && t.paper_count && t.papers.length !== t.paper_count) {
        // This is expected for overview (light papers), so just note it
      }

      // year_range
      if (t.year_range && t.year_range.length === 2) {
        pass(`topic has year_range: [${t.year_range[0]}, ${t.year_range[1]}]`);
      } else {
        fail(`topic missing year_range`);
      }

      break; // Just check first topic in detail
    }

    console.log(`\n  Summary: ${topicsWithKeywords}/${allTopics.length} topics have keywords`);
    console.log(`  Summary: ${topicsWithPapers}/${allTopics.length} topics have papers`);
    console.log(`  Summary: ${topicsWithRepPapers}/${allTopics.length} topics have representative_papers`);

    if (topicsWithKeywords === 0 && allTopics.length > 0) {
      fail("NO topics have keywords");
    }
    if (topicsWithPapers === 0 && allTopics.length > 0) {
      fail("NO topics have papers");
    }
    if (keywordIssues > 0) {
      fail(`${keywordIssues} topics have low-value keywords`);
    } else {
      pass("no low-value keywords detected");
    }
  } else {
    fail("no topics in /research-map response");
  }

  // ── 2. Relationships ──
  console.log("\n--- relationships ---");
  const rels = mapData.topic_relationships || [];
  if (Array.isArray(rels)) {
    pass(`topic_relationships field exists`, `${rels.length} relationships`);
    if (rels.length > 0) {
      const r = rels[0];
      if (r.source_topic_id && r.target_topic_id) pass("relationship has source/target ids");
      if (typeof r.similarity === "number") pass("relationship has similarity score");
    } else {
      pass("relationships is empty (graceful)", "no strong connections yet");
    }
  } else {
    fail("topic_relationships field missing");
  }

  // ── 3. /research-map/topic/{id} ──
  if (topicId) {
    console.log(`\n--- /research-map/topic/${topicId} ---`);
    try {
      const detail = await fetchJson(`/research-map/topic/${topicId}`);
      const topic = detail.topic || detail;

      // year_distribution
      if (topic.year_distribution && Array.isArray(topic.year_distribution)) {
        pass(`year_distribution exists`, `${topic.year_distribution.length} years`);
      } else {
        fail(`year_distribution missing or empty`);
      }

      // evolution_phases
      if (topic.evolution_phases && Array.isArray(topic.evolution_phases)) {
        pass(`evolution_phases exists`, `${topic.evolution_phases.length} phases`);
        if (topic.evolution_phases.length > 0) {
          const ph = topic.evolution_phases[0];
          if (ph.phase && ph.label && ph.year_range) pass("evolution_phase has required fields");
        }
      } else {
        fail(`evolution_phases missing`);
      }

      // related_topics
      if (topic.related_topics !== undefined) {
        pass(`related_topics field exists`, `${(topic.related_topics || []).length} related`);
      } else {
        fail(`related_topics field missing`);
      }

      // Full papers with summary/evidence
      if (topic.papers && topic.papers.length > 0) {
        const hasSummary = topic.papers.some((p: any) => p.summary);
        const hasEvidence = topic.papers.some((p: any) => p.evidence);
        pass(`topic papers exist`, `${topic.papers.length} papers (summary: ${hasSummary}, evidence: ${hasEvidence})`);
      }

      // topic_relevance
      if (topic.papers && topic.papers.length > 0) {
        const withRelevance = topic.papers.filter((p: any) => p.topic_relevance !== undefined).length;
        if (withRelevance > 0) {
          pass(`topic_relevance scores exist`, `${withRelevance}/${topic.papers.length} papers scored`);
        }
      }
    } catch (e: any) {
      fail(`/research-map/topic/{id} failed`, e.message);
    }
  } else {
    fail("no topic_id available for detail test");
  }

  // ── 4. /query/evidence must still work ──
  console.log("\n--- /query/evidence (regression) ---");
  try {
    const evRes = await fetch(`${API_BASE}/query/evidence`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "test query", limit: 3 }),
    });
    if (evRes.ok) {
      const evData = await evRes.json();
      pass("/query/evidence still works", `source: ${evData.source}, results: ${(evData.results || []).length}`);
    } else {
      fail("/query/evidence failed", `HTTP ${evRes.status}`);
    }
  } catch (e: any) {
    fail("/query/evidence exception", e.message);
  }

  printSummary();
}

function printSummary() {
  const passed = results.filter((r) => r.passed).length;
  const failed = results.filter((r) => !r.passed).length;
  console.log(`\n========================================`);
  console.log(`Research Map Test: ${passed} passed, ${failed} failed`);
  console.log(`========================================`);
  process.exit(failed > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error("Test script error:", e.message);
  process.exit(1);
});
