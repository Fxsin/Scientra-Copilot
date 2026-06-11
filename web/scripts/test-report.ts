const RPT_API = process.env.NEXT_PUBLIC_SCIENTRA_API_URL || `http://127.0.0.1:${process.env.NEXT_PUBLIC_SCIENTRA_API_PORT || "8710"}`;
interface RptResult { name: string; passed: boolean; detail?: string }
const rptResults: RptResult[] = [];
function rptPass(n: string, d?: string) { rptResults.push({name:n,passed:true,detail:d}); console.log(`  ✅ ${n}${d?" — "+d:""}`); }
function rptFail(n: string, d?: string) { rptResults.push({name:n,passed:false,detail:d}); console.log(`  ❌ ${n}${d?" — "+d:""}`); }

async function runReportTest() {
  console.log("=== Report Tests ===\n");
  let data: any;
  try {
    const res = await fetch(`${RPT_API}/report`);
    if (!res.ok) { rptFail("GET /report", `HTTP ${res.status}`); rptPrint(); return; }
    data = await res.json(); rptPass("GET returns data");
  } catch (e: any) { rptFail("GET failed", e.message); rptPrint(); return; }

  if (data.status) rptPass(`status: ${data.status}`);
  if (data.paper_count === 55) rptPass("paper_count: 55"); else rptFail(`paper_count: ${data.paper_count}`);
  for (const f of ["executive_summary","coverage_summary","research_map_summary","hotspots_summary","research_gaps_summary","knowledge_network_summary","evidence_summary","recommended_actions","sections"]) {
    if (f in data) rptPass(`${f} exists`, Array.isArray(data[f])?`count=${data[f].length}`:"object"); else rptFail(`${f} missing`);
  }
  const raw = JSON.stringify(data);
  if (!raw.includes("Bt Toxin")) rptPass("no Bt Toxin mock"); else rptFail("contains mock");
  if (!raw.includes("Vip3A pore")) rptPass("no Vip3A pore mock"); else rptFail("contains mock");
  const bad = raw.includes(":null")||raw.includes(":undefined")||raw.includes(":NaN");
  if (!bad) rptPass("no null/undefined/NaN"); else rptFail("contains bad values");
  rptPrint();
}
function rptPrint() {
  const p=rptResults.filter(x=>x.passed).length, f=rptResults.filter(x=>!x.passed).length;
  console.log(`\n========================================`);
  console.log(`Report Test: ${p} passed, ${f} failed`);
  console.log(`========================================`);
  process.exit(f>0?1:0);
}
runReportTest().catch(e=>{console.error(e.message);process.exit(1);});
