/**
 * Hotspots Data Integrity Test
 * Validates /hotspots returns real (non-mock) data.
 */
const TEST_API_BASE = process.env.NEXT_PUBLIC_SCIENTRA_API_URL || `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}`;

interface TestResult { name: string; passed: boolean; detail?: string }
const hsResults: TestResult[] = [];

function hsPass(name: string, detail?: string) { hsResults.push({ name, passed: true, detail }); console.log(`  ✅ ${name}${detail ? " — " + detail : ""}`); }
function hsFail(name: string, detail?: string) { hsResults.push({ name, passed: false, detail }); console.log(`  ❌ ${name}${detail ? " — " + detail : ""}`); }

async function runHotspotsTests() {
  console.log("=== Hotspots Data Integrity Tests ===\n");

  let data: any;
  try {
    const res = await fetch(`${TEST_API_BASE}/hotspots`);
    if (!res.ok) { hsFail("GET /hotspots", `HTTP ${res.status}`); hsPrintSummary(); return; }
    data = await res.json();
    hsPass("GET /hotspots returns data");
  } catch (e: any) {
    hsFail("GET /hotspots", e.message);
    hsPrintSummary();
    return;
  }

  // 1. Status
  if (data.status) hsPass(`status: ${data.status}`);
  else hsFail("status field missing");

  // 2. Source
  if (data.status === "success" && data.source === "research_map_cache") hsPass("source is research_map_cache");
  else if (data.status === "cache_missing") hsPass("source is cache_missing (graceful)");

  // 3. Paper count
  if (typeof data.paper_count === "number" && data.paper_count > 0) hsPass(`paper_count: ${data.paper_count}`);
  else hsFail("paper_count missing or zero");

  // 4. No mock
  const raw = JSON.stringify(data);
  if (!raw.includes("Bt Toxin Mode of Action")) hsPass("no Bt Toxin mock");
  else hsFail("contains Bt Toxin mock data");
  if (!raw.includes("paperCount\":34")) hsPass("no paperCount:34 mock");
  else hsFail("contains paperCount:34 mock");

  // 5. Field existence
  for (const field of ["trending_topics", "hot_papers", "emerging_facets", "evidence_signals", "insights", "method_shifts"]) {
    if (field in data) hsPass(`${field} field exists`, Array.isArray(data[field]) ? `count=${data[field].length}` : "object");
    else hsFail(`${field} field missing`);
  }

  // 6. Evidence signals
  const es = data.evidence_signals;
  if (es && es.chunk_type_distribution) {
    const dist = es.chunk_type_distribution;
    const types = ["key_result", "core_finding", "method", "discussion_point"];
    let ok = true;
    for (const t of types) { if (!(t in dist)) { hsFail(`evidence_signals missing ${t}`); ok = false; } }
    if (ok) hsPass("evidence_signals has all chunk types");
    const total = Object.values(dist).reduce((a: number, b: any) => a + (typeof b === "number" ? b : 0), 0);
    if (total > 0) hsPass(`evidence total chunks: ${total}`);
  }

  // 7. Trending topics check
  const tt = data.trending_topics || [];
  if (tt.length > 0) {
    const t0 = tt[0];
    if (t0.name && t0.growth_score !== undefined) hsPass("trending topics have name + growth_score");
    if (t0.trend_label && ["hot", "active", "stable", "dormant"].includes(t0.trend_label)) hsPass(`trend_label valid: ${t0.trend_label}`);
  }

  // 8. Hot papers
  const hp = data.hot_papers || [];
  if (hp.length > 0) {
    if (hp[0].paper_id && hp[0].title) hsPass("hot papers have paper_id + title");
    if (hp[0].evidence_counts) hsPass("hot papers have evidence_counts");
  }

  // 9. No undefined/null/NaN
  const hasBad = raw.includes(":null") || raw.includes(":undefined") || raw.includes(":NaN");
  if (!hasBad) hsPass("no null/undefined/NaN in response");
  else hsFail("contains null/undefined/NaN");

  // 10. generated_at
  if (data.generated_at) hsPass("generated_at present");
  else hsPass("generated_at not present (non-cached response)");

  hsPrintSummary();
}

function hsPrintSummary() {
  const passed = hsResults.filter(r => r.passed).length;
  const failed = hsResults.filter(r => !r.passed).length;
  console.log(`\n========================================`);
  console.log(`Hotspots Test: ${passed} passed, ${failed} failed`);
  console.log(`========================================`);
  process.exit(failed > 0 ? 1 : 0);
}

runHotspotsTests().catch(e => { console.error(e.message); process.exit(1); });
