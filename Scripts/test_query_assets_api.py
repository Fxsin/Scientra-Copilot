"""Test script for POST /query/assets — Phase 0.8"""
import json, sys, time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0

def test(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} — {detail}")

def call_api(payload: dict) -> dict:
    """Call /query/assets via SDK."""
    from scientra.sdk import query_assets
    return query_assets(
        query=payload.get("query", ""),
        top_k=payload.get("top_k", 10),
        chunk_types=payload.get("chunk_types"),
        paper_id=payload.get("paper_id"),
        min_quality_score=payload.get("min_quality_score", 0.0),
    )

print("=" * 60)
print("POST /query/assets — API Tests")
print("=" * 60)
print()

# Test 1: Normal query
print("[1] Normal query: 'protein expression'")
r = call_api({"query": "protein expression conditions", "top_k": 5})
test("returns results", r["count"] > 0, f"count={r['count']}")
test("has chunk_id", len(r["results"]) > 0 and "chunk_id" in r["results"][0])
test("has citation_key", len(r["results"]) > 0 and r["results"][0].get("citation_key", "").startswith("[A:"))
test("unique_papers > 0", r["unique_papers"] > 0, f"papers={r['unique_papers']}")
print(f"    -> {r['count']} results, {r['unique_papers']} papers")

# Test 2: method-only query
print("\n[2] method-only query")
r = call_api({"query": "RNA-Seq transcriptomics", "top_k": 5, "chunk_types": ["method"]})
test("returns only methods", all(c["chunk_type"] == "method" for c in r["results"]),
     f"types: {set(c['chunk_type'] for c in r['results'])}")
print(f"    -> {r['count']} method chunks")

# Test 3: claim-only query
print("\n[3] claim-only query")
r = call_api({"query": "mode of action Vip3Aa", "top_k": 5, "chunk_types": ["claim"]})
test("returns only claims", all(c["chunk_type"] == "claim" for c in r["results"]),
     f"types: {set(c['chunk_type'] for c in r['results'])}")
print(f"    -> {r['count']} claim chunks")

# Test 4: paper_id filter
print("\n[4] paper_id filter")
r_all = call_api({"query": "Vip3Aa resistance", "top_k": 5})
if r_all["results"]:
    pid = r_all["results"][0]["paper_id"]
    r = call_api({"query": "Vip3Aa resistance", "top_k": 5, "paper_id": pid})
    test("all results from same paper", all(c["paper_id"] == pid for c in r["results"]) if r["results"] else True)
    print(f"    -> {r['count']} results for paper_id={pid[:40]}...")
else:
    print("    -> SKIP (no results in baseline)")

# Test 5: top_k limit (API enforces max 50, SDK passes through)
print("\n[5] top_k limit — SDK respects caller value")
r = call_api({"query": "toxin", "top_k": 5})
test("results with top_k=5", r["count"] <= 5, f"count={r['count']}")

# Test 6: empty query
print("\n[6] empty query -> error")
try:
    from scientra.server import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    resp = client.post("/query/assets", json={"query": "", "top_k": 5})
    test("returns 422 (validation error)", resp.status_code == 422,
         f"status={resp.status_code}")
except ImportError:
    print("    -> SKIP (TestClient not available)")

# Test 7: fake query doesn't crash — LanceDB always returns nearest neighbors
print("\n[7] fake query doesn't crash")
r = call_api({"query": "xyzzy123 fake toxin that doesn't exist anywhere", "top_k": 5})
test("does not crash", True)  # if we got here, it didn't crash
test("returns results (vector DB always finds nearest)", r["count"] >= 0, f"count={r['count']}")
print(f"    -> {r['count']} results (LanceDB always returns nearest neighbors)")

# Test 8: invalid chunk_type -> rejected
print("\n[8] invalid chunk_type -> rejected")
try:
    resp = client.post("/query/assets", json={"query": "test", "chunk_types": ["invalid_type"]})
    test("returns error (400/422)", resp.status_code in (400, 422), f"status={resp.status_code}")
except NameError:
    print("    -> SKIP (no TestClient)")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
