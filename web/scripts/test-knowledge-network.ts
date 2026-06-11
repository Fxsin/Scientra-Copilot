/**
 * Knowledge Network Data Integrity Test
 */
const KN_API = process.env.NEXT_PUBLIC_SCIENTRA_API_URL || `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}`;

interface TestResult { name: string; passed: boolean; detail?: string }
const knTestResults: TestResult[] = [];
function knp(n: string, d?: string) { knTestResults.push({name:n,passed:true,detail:d}); console.log(`  ✅ ${n}${d?" — "+d:""}`); }
function knf(n: string, d?: string) { knTestResults.push({name:n,passed:false,detail:d}); console.log(`  ❌ ${n}${d?" — "+d:""}`); }

async function run() {
  console.log("=== Knowledge Network Tests ===\n");
  let data: any;
  try {
    const res = await fetch(`${KN_API}/knowledge-network`);
    if (!res.ok) { knf("GET /knowledge-network", `HTTP ${res.status}`); print(); return; }
    data = await res.json(); knp("GET returns data");
  } catch (e: any) { knf("GET failed", e.message); print(); return; }

  if (data.status) knp(`status: ${data.status}`);
  if (data.paper_count === 55) knp("paper_count: 55"); else knf(`paper_count: ${data.paper_count}`);
  if (Array.isArray(data.nodes)) knp(`nodes: ${data.nodes.length}`); else knf("nodes missing");
  if (Array.isArray(data.edges)) knp(`edges: ${data.edges.length}`); else knf("edges missing");
  if (data.node_count === data.nodes?.length) knp("node_count matches"); else knf("node_count mismatch");
  if (data.edge_count === data.edges?.length) knp("edge_count matches"); else knf("edge_count mismatch");

  const raw = JSON.stringify(data);
  if (!raw.includes("Bt Toxin")) knp("no Bt Toxin mock"); else knf("contains mock");
  const hasBad = raw.includes(":null") || raw.includes(":undefined") || raw.includes(":NaN");
  if (!hasBad) knp("no null/undefined/NaN"); else knf("contains bad values");

  const nids = new Set(data.nodes?.map((n:any)=>n.id)||[]);
  let orphans = 0;
  for (const e of (data.edges||[])) { if (!nids.has(e.source) || !nids.has(e.target)) orphans++; }
  if (orphans === 0) knp("no orphan edges"); else knf(`${orphans} orphan edges`);

  print();
}

function print() {
  const p=knTestResults.filter(r=>r.passed).length, f=knTestResults.filter(r=>!r.passed).length;
  console.log(`\n========================================`);
  console.log(`Knowledge Network: ${p} passed, ${f} failed`);
  console.log(`========================================`);
  process.exit(f>0?1:0);
}
run().catch(e=>{console.error(e.message);process.exit(1);});
