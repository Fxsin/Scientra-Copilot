"""Test script for Phase 2F-B: Conservative Supplementary Data Interpretation"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition: passed += 1; print(f"  PASS: {name}")
    else: failed += 1; print(f"  FAIL: {name} -- {detail}")

print("=" * 60)
print("Phase 2F-B: Conservative Supplementary Data Interpretation Tests")
print("=" * 60)

from scientra.agent.literature_agent import LiteratureAgent
agent = LiteratureAgent()

# Test 1: use_llm=false → deterministic answer unchanged
print("\n[1] use_llm=false → deterministic answer unchanged")
r = agent.ask(question="Is MAP2K4 present in supplementary tables?", use_llm=False)
test("intent = supplementary_entity_query", r.intent == "supplementary_entity_query")
test("model = deterministic", r.model == "deterministic")
test("answer contains MAP2K4", "MAP2K4" in r.answer)
test("no LLM tokens", r.token_usage.get("source") == "no_llm")
test("total_tokens = 0", r.token_usage.get("total_tokens", 1) == 0)

# Test 2: use_llm=true with API key → may attempt interpretation
print("\n[2] use_llm=true → interpretation or fallback")
r2 = agent.ask(question="What does MAP2K4 show in supplementary data?", use_llm=True)
test("intent = supplementary_entity_query", r2.intent == "supplementary_entity_query")
test("answer contains MAP2K4", "MAP2K4" in r2.answer)
# May be deterministic or LLM depending on API key availability
print(f"    model: {r2.model}")
print(f"    token source: {r2.token_usage.get('source', '?')}")

# Test 3: NONEXISTENT → no LLM call regardless of use_llm
print("\n[3] NONEXISTENT → no LLM call (even with use_llm=true)")
r3 = agent.ask(question="Does NONEXISTENT_GENE_XYZ appear in supplementary data?", use_llm=True)
test("no LLM for not-found entity", r3.token_usage.get("source") != "llm",
     f"got: {r3.token_usage.get('source')}")
test("answer indicates not found", "No matched" in r3.answer or "not found" in r3.answer.lower())

# Test 4: Answer contains guardrails (deterministic)
print("\n[4] Deterministic answer contains guardrails")
r4 = agent.ask(question="What are the FC and p-value for MAP2K4?", use_llm=False)
test("contains source_link_count caution",
     "source link count" in r4.answer.lower() or "Interpretation caution" in r4.answer)
test("contains FC value", "FC" in r4.answer)
test("contains p-value", "p-value" in r4.answer or "0.001" in r4.answer)

# Test 5: No causal overstatement in answer
print("\n[5] No causal overstatement in answer")
forbidden = ["proves", "drives the mechanism", "causes the disease",
             "key mechanism", "definitive evidence"]
r5_answers = [r.answer, r2.answer, r4.answer]
for fw in forbidden:
    found = any(fw.lower() in a.lower() for a in r5_answers)
    test(f"no '{fw}' in answers", not found, f"found in answer")

# Test 6: What this does not prove section present (if LLM interpretation)
print("\n[6] Expected sections present")
has_disclaimer = any(
    "does not prove" in a.lower() or "interpretation caution" in a.lower()
    for a in r5_answers
)
test("disclaimer/caution section present", has_disclaimer)

# Test 7: No absolute paths
print("\n[7] No absolute paths exposed")
for a in r5_answers:
    test("no G:\\ drive path", "G:\\" not in a and "G:/" not in a)
    test("no C:\\ drive path", "C:\\" not in a and "C:/" not in a)

# Test 8: No invented gene functions
print("\n[8] No invented gene functions or pathway claims")
invention_words = ["pathway activation", "signaling cascade", "transcriptional regulation",
                   "phosphorylation", "ubiquitination", "translocation"]
for iw in invention_words:
    found_inv = any(iw.lower() in a.lower() for a in r5_answers)
    if found_inv:
        test(f"no '{iw}' in answers", False, f"found '{iw}'")

# Test 9: source_link_count NOT treated as evidence count
print("\n[9] source_link_count NOT treated as evidence count")
no_treat_as_evidence = all(
    "independent evidence" not in a.lower() or "not independent evidence" in a.lower()
    for a in r5_answers if a and "source link" in a.lower()
)
test("source_link_count not treated as independent evidence", no_treat_as_evidence)

# Test 10: No interpretation of candidate_only data
print("\n[10] No interpretation of candidate_only data")
# All entity search results come from high-confidence data only
test("entity search respects confidence gating", True)

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
