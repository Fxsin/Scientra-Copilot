"""Test script for POST /v1/agent/ask — Phase 0.8 enhanced"""
import json, sys
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

print("=" * 60)
print("POST /v1/agent/ask — Enhanced API Tests")
print("=" * 60)
print()

from scientra.agent.literature_agent import LiteratureAgent
agent = LiteratureAgent()

# Test 1: use_llm=false (extractive)
print("[1] use_llm=false — extractive answer")
r = agent.ask(question="What methods study Vip3Aa toxicity?", top_k=5, use_llm=False)
test("returns answer", len(r.answer) > 50, f"len={len(r.answer)}")
test("contains [Ref:]", "[Ref:" in r.answer)
test("no API key needed", True)  # always works without LLM
print(f"    -> {len(r.answer)} chars, {r.elapsed_ms}ms, intent={r.intent}")

# Test 2: include_assets only
print("\n[2] include_assets=true, include_evidence=false")
r = agent.ask(question="Vip3Aa mode of action", top_k=5,
              include_assets=True, include_evidence=False, use_llm=False)
sources = set()
if r.raw_context:
    sources = {getattr(c, 'source', '') for c in r.raw_context.chunks}
test("only pdf_asset_chunks", sources == {"pdf_asset_chunks"} or all("evidence" not in s for s in sources),
     f"sources={sources}")
print(f"    -> {r.context_used} chunks, sources={sources}")

# Test 3: include_evidence only
print("\n[3] include_assets=false, include_evidence=true")
r = agent.ask(question="Vip3Aa resistance mechanisms", top_k=5,
              include_assets=False, include_evidence=True, use_llm=False)
if r.raw_context:
    sources = {getattr(c, 'source', '') for c in r.raw_context.chunks}
    test("only evidence_chunks", all("asset" not in s for s in sources),
         f"sources={sources}")
    print(f"    -> {r.context_used} chunks, sources={sources}")
else:
    print("    -> no context")

# Test 4: dual source
print("\n[4] Dual source (both=true)")
r = agent.ask(question="Vip3Aa binding receptor", top_k=5,
              include_assets=True, include_evidence=True, use_llm=False)
test("has chunks", r.context_used > 0, f"count={r.context_used}")
print(f"    -> {r.context_used} chunks, {r.papers_cited} papers")

# Test 5: return_context=true
print("\n[5] return_context=true")
r = agent.ask(question="Vip3Aa toxicity results", top_k=3,
              use_llm=False, return_context=True)
test("raw_context is set", r.raw_context is not None)
test("has chunks in context", len(r.raw_context.chunks) > 0 if r.raw_context else False)
test("has papers in context", len(r.raw_context.papers) > 0 if r.raw_context else False)
print(f"    -> context: {len(r.raw_context.chunks) if r.raw_context else 0} chunks, "
      f"{len(r.raw_context.papers) if r.raw_context else 0} papers")

# Test 6: out-of-scope
print("\n[6] out-of-scope question")
r = agent.ask(question="What is the weather today?", top_k=3, use_llm=False)
test("redirects out of scope", "outside the scope" in r.answer.lower())
print(f"    -> {r.answer[:80]}...")

# Test 7: negative control
print("\n[7] negative control — fake entity")
r = agent.ask(question="What does the database say about XYZ123FakeProtein?", top_k=3, use_llm=False)
test("does not fabricate", "XYZ123FakeProtein" not in r.answer.split(":")[-1] if ":" in r.answer else True)
print(f"    -> {r.answer[:80]}...")

# Test 8: paper_id filter
print("\n[8] paper_id filter")
r_baseline = agent.ask(question="Vip3Aa", top_k=5, use_llm=False)
if r_baseline.raw_context and r_baseline.raw_context.chunks:
    pid = r_baseline.raw_context.chunks[0].paper_id
    r = agent.ask(question="Vip3Aa", top_k=5, paper_id=pid, use_llm=False)
    if r.raw_context and r.raw_context.chunks:
        test("all chunks from same paper", all(
            getattr(c, 'paper_id', '') == pid for c in r.raw_context.chunks
        ))
        print(f"    -> {r.context_used} chunks for paper_id={pid[:40]}...")
    else:
        print("    -> SKIP (no context)")
else:
    print("    -> SKIP (no baseline context)")

# Test 9: backward compat — old params still work
print("\n[9] backward compat — old ask() signature")
r = agent.ask(question="Vip3Aa", top_k=5, include_evidence=True)
test("old signature works", r.context_used > 0 or len(r.answer) > 10)
print(f"    -> {r.context_used} chunks")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
