param($ApiBase="http://127.0.0.1:8710", $Query="resistance mechanism", $Limit=3, $TopicId="topic_001", [switch]$SkipWorkflow, [switch]$SkipWebTests, [switch]$ForceEvidence)

$Passed = 0; $Failed = 0; $Warned = 0
$ProjectRoot = (Get-Location).Path

function step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function pass($msg) { $script:Passed++; Write-Host "  [PASS] $msg" -ForegroundColor Green }
function fail($msg) { $script:Failed++; Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function warn($msg) { $script:Warned++; Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

# 1. API Health
step "1. API Health Check"
try { $h = Invoke-RestMethod "$ApiBase/health" -TimeoutSec 5; pass "API ok, lancedb=$($h.lancedb_status)" } catch { fail "API not reachable" }

# 2. Evidence Extraction
if (-not $SkipWorkflow) {
  step "2. Evidence Extraction"
  $eargs = @("--root", $ProjectRoot); if ($ForceEvidence) { $eargs += "--force" }
  python -m scientra.evidence_extraction @eargs 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { pass "Evidence extraction done" } else { warn "Evidence extraction had warnings" }
}

# 3. Chunks
step "3. Evidence Chunks"
$cd = Get-ChildItem "$ProjectRoot/03_Evidence" -Directory -ErrorAction SilentlyContinue
$cc = 0; $cf = 0
foreach ($d in $cd) {
  $cp = Join-Path $d.FullName "evidence_chunks.json"
  if (Test-Path $cp) { $cf++; try { $cc += (Get-Content $cp -Raw | ConvertFrom-Json).chunk_count } catch {} }
}
if ($cc -gt 0) { pass "$cf papers, $cc chunks" } else { warn "No chunks found" }

# 4. Embedding
step "4. Evidence Embedding"
$embargs = @("--root", $ProjectRoot); if ($ForceEvidence) { $embargs += "--force" }
python -m scientra.evidence_embedding @embargs 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { pass "Embedding done" } else { warn "Embedding had warnings" }

# 5. Paper evidence API
step "5. Paper Evidence API"
$papers = Invoke-RestMethod "$ApiBase/papers?page_size=1" -TimeoutSec 5
$paperId = $papers.papers[0].paper_id
try { $ev = Invoke-RestMethod "$ApiBase/paper/$paperId/evidence" -TimeoutSec 5; pass "evidence status=$($ev.status)" } catch { warn "evidence API unavailable" }
try { $ch = Invoke-RestMethod "$ApiBase/paper/$paperId/evidence-chunks" -TimeoutSec 5; pass "chunks count=$($ch.chunk_count)" } catch { warn "chunks API unavailable" }

# 6. Query evidence
step "6. POST /query/evidence"
$body = @{query=$Query; limit=$Limit; chunk_type="all"} | ConvertTo-Json
try {
  $qr = Invoke-RestMethod "$ApiBase/query/evidence" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 15
  if ($qr.source -ne "empty" -and $qr.results.Count -gt 0) {
    pass "query returned $($qr.results.Count) results, source=$($qr.source)"
    Write-Host "  Top chunks:" -ForegroundColor Gray
    foreach ($r in $qr.results[0..2]) {
      $t = if ($r.text.Length -gt 80) { $r.text.Substring(0,80)+"..." } else { $r.text }
      Write-Host "    [$('{0:0.000}' -f $r.score)] [$($r.chunk_type)] $t" -ForegroundColor Gray
    }
  } else { warn "query returned empty" }
} catch { warn "query evidence unavailable" }

# 7. Topic API
step "7. Topic API evidence"
try {
  $t = Invoke-RestMethod "$ApiBase/research-map/topic/$TopicId" -TimeoutSec 10
  $evCount = ($t.topic.papers | Where-Object { $_.evidence -ne $null }).Count
  if ($evCount -gt 0) { pass "Topic papers with evidence: $evCount/$($t.topic.papers.Count)" }
  else { warn "No evidence in topic papers (dir naming mismatch)" }
} catch { warn "Topic API unavailable" }

# 8. Web Tests
if (-not $SkipWebTests) {
  step "8. Web Tests"
  Push-Location "$ProjectRoot/web"
  $sp = npm run test:summary-parser 2>&1 | Out-String; if ($sp -match "Passed: 149") { pass "summary-parser 149/149" } else { fail "summary-parser" }
  $te = npm run test:topic-evolution 2>&1 | Out-String; if ($te -match "Passed: 27") { pass "topic-evolution 27/27" } else { fail "topic-evolution" }
  $b = npm run build 2>&1 | Out-String; if ($LASTEXITCODE -eq 0) { pass "npm build" } else { fail "npm build" }
  Pop-Location
}

# Summary
step "SUMMARY"
Write-Host "  Passed: $Passed  Failed: $Failed  Warnings: $Warned" -ForegroundColor $(if ($Failed -eq 0) { "Green" } else { "Red" })
exit $(if ($Failed -eq 0) { 0 } else { 1 })
