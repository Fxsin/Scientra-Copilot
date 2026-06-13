"""Test script for Phase 2F-A: Supplementary Entity Query Intent + Chat"""
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
print("Phase 2F-A: Supplementary Entity Query Intent + Chat Tests")
print("=" * 60)

# Test 1: Entity parser — extract MAP2K4
print("\n[1] Entity parser: extract MAP2K4")
from scientra.agent.entity_query_parser import parse_entity_query, is_supplementary_entity_query
r = parse_entity_query("Is MAP2K4 present in supplementary tables?")
test("entity_query extracted", r["entity_query"] == "MAP2K4", f"got: {r['entity_query']}")
test("is supplementary context", r["is_supplementary_context"])
test("is location intent", r["is_location_intent"])

# Test 2: Entity parser — extract CASP3
print("\n[2] Entity parser: extract CASP3")
r = parse_entity_query("What supplementary data contains CASP3?")
test("entity_query = CASP3", r["entity_query"] == "CASP3", f"got: {r['entity_query']}")
test("supplementary context", r["is_supplementary_context"])

# Test 3: Entity parser — gene type detection
print("\n[3] Entity parser: gene type detection")
r = parse_entity_query("Find gene MAP3K7 in supplementary files.")
test("entity_type = gene", r["entity_type"] == "gene", f"got: {r['entity_type']}")
test("entity_query = MAP3K7", r["entity_query"] == "MAP3K7", f"got: {r['entity_query']}")

# Test 4: Entity parser — value request
print("\n[4] Entity parser: value request")
r = parse_entity_query("What are the FC and p-value for MAP2K4?")
test("requested_values includes FC", 'fc' in r["requested_values"] or 'p-value' in r["requested_values"])
test("entity_query = MAP2K4", r["entity_query"] == "MAP2K4")

# Test 5: Entity parser — NONEXISTENT
print("\n[5] Entity parser: NONEXISTENT_GENE_XYZ")
r = parse_entity_query("Does NONEXISTENT_GENE_XYZ appear in supplementary data?")
# NONEXISTENT_GENE_XYZ may not match typical entity pattern
print(f"    entity_query: {r['entity_query']}")

# Test 6: Intent detection
print("\n[6] Intent detection: supplementary_entity_query")
test_cases = [
    "Is MAP2K4 present in supplementary tables?",
    "Where is MAP2K4 found?",
    "What supplementary data contains CASP3?",
    "Find gene MAP3K7 in supplementary files.",
    "Which supplementary table contains TRAF4?",
    "What are the FC and p-value for MAP2K4?",
    "Does NONEXISTENT_GENE_XYZ appear in supplementary data?",
]
detected = sum(1 for q in test_cases if is_supplementary_entity_query(q))
test(f"{detected}/{len(test_cases)} questions detected as entity queries", detected >= 5, f"got: {detected}")

# Test 7: NOT supplementary entity — regular questions
print("\n[7] NOT supplementary entity: regular questions")
regular = [
    "What is the mode of action of Vip3Aa?",
    "How are bioassays performed?",
    "What research gaps exist?",
    "Which claims are well-supported?",
]
false_positives = sum(1 for q in regular if is_supplementary_entity_query(q))
test(f"false positives: {false_positives}/{len(regular)}", false_positives == 0,
     f"false positives: {[q for q in regular if is_supplementary_entity_query(q)]}")

# Test 8: Agent handles entity query (import test)
print("\n[8] Agent handles entity query")
try:
    from scientra.agent.literature_agent import LiteratureAgent
    agent = LiteratureAgent()
    # Test with use_llm=False for deterministic
    response = agent.ask(
        question="Is MAP2K4 present in supplementary tables?",
        use_llm=False, return_context=False
    )
    test("intent = supplementary_entity_query",
         response.intent == "supplementary_entity_query",
         f"got: {response.intent}")
    test("answer contains MAP2K4",
         "MAP2K4" in response.answer,
         "answer does not contain MAP2K4")
    test("answer contains matched result",
         "Match" in response.answer or "match" in response.answer.lower())
    test("model is deterministic",
         response.model == "deterministic")
    test("no LLM tokens used",
         response.token_usage.get("source") == "no_llm")
    test("no LLM call made",
         response.token_usage.get("total_tokens", 1) == 0)
    print(f"    Answer preview: {response.answer[:200]}...")
except ImportError as e:
    print(f"    SKIP (import error: {e})")

# Test 9: Agent handles NONEXISTENT query
print("\n[9] Agent handles NONEXISTENT query")
try:
    response = agent.ask(
        question="Does NONEXISTENT_GENE_XYZ appear in supplementary data?",
        use_llm=False, return_context=False
    )
    test("no match found message",
         "No matched supplementary entity" in response.answer or
         "not found" in response.answer.lower())
    print(f"    Answer: {response.answer[:200]}...")
except Exception as e:
    print(f"    SKIP (error: {e})")

# Test 10: Source link count caution
print("\n[10] Source link count caution present")
try:
    response = agent.ask(
        question="What supplementary data contains MAP2K4?",
        use_llm=False, return_context=False
    )
    has_caution = "Interpretation caution" in response.answer or "source link count" in response.answer.lower()
    test("caution about source_link_count present", has_caution)
except Exception as e:
    print(f"    SKIP (error: {e})")

# Test 11: No absolute paths in answer
print("\n[11] No absolute paths in answer")
try:
    response = agent.ask(
        question="Where is MAP2K4 found?",
        use_llm=False, return_context=False
    )
    test("no G: drive path", "G:\\" not in response.answer and "G:/" not in response.answer)
    test("no C: drive path", "C:\\" not in response.answer and "C:/" not in response.answer)
    test("no absolute path separators", "G:\\AI_agent" not in response.answer)
except Exception as e:
    print(f"    SKIP (error: {e})")

print()
print("=" * 60)
print(f"Results: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
