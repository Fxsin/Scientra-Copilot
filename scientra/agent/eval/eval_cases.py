"""
Test cases for Literature Agent evaluation — 28 questions across 7 categories.

Each case defines expected behavior: what the agent SHOULD do and what it MUST NOT do.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    case_id: str
    category: str  # method_query, result_query, claim_query, paper_specific_query, research_gap_query, negative_control_query, out_of_scope_query
    question: str
    expected_intent: str
    should_retrieve_context: bool = True
    should_answer: bool = True
    should_have_citations: bool = True
    required_behavior: list[str] = field(default_factory=list)
    forbidden_behavior: list[str] = field(default_factory=list)
    insufficient_evidence_expected: bool = False


# ── Category 1: method_query (5 cases) ──

METHOD_CASES = [
    EvalCase(
        case_id="M001",
        category="method_query",
        question="What methods are commonly used to study Vip3Aa toxicity in this literature?",
        expected_intent="search_by_toxin",
        required_behavior=["mentions specific methods from context", "cites source papers"],
        forbidden_behavior=["invents method names not in context"],
    ),
    EvalCase(
        case_id="M002",
        category="method_query",
        question="Which papers use RNA-Seq or transcriptomics methods?",
        expected_intent="search_by_method",
        required_behavior=["names papers that mention RNA-Seq", "cites context chunks"],
        forbidden_behavior=["lists papers not in retrieved context"],
    ),
    EvalCase(
        case_id="M003",
        category="method_query",
        question="Find evidence related to protein expression in E. coli.",
        expected_intent="search_by_method",
        required_behavior=["references expression methods", "cites relevant chunks"],
        forbidden_behavior=["fabricates expression protocols"],
    ),
    EvalCase(
        case_id="M004",
        category="method_query",
        question="Which papers mention binding assays or SPR experiments?",
        expected_intent="search_by_method",
        required_behavior=["identifies papers with binding/SPR methods"],
        forbidden_behavior=["invents SPR parameters not in context"],
    ),
    EvalCase(
        case_id="M005",
        category="method_query",
        question="What bioassay methods are used to test insecticidal activity?",
        expected_intent="search_by_method",
        required_behavior=["describes bioassay methods from context"],
        forbidden_behavior=["fabricates LC50 values not in context"],
    ),
]

# ── Category 2: result_query (5 cases) ──

RESULT_CASES = [
    EvalCase(
        case_id="R001",
        category="result_query",
        question="What are the main experimental results about Vip3Aa toxicity?",
        expected_intent="search_by_toxin",
        required_behavior=["summarizes toxicity results from context", "cites multiple papers"],
        forbidden_behavior=["reports specific LC50 not in context"],
    ),
    EvalCase(
        case_id="R002",
        category="result_query",
        question="What results mention resistance to Vip3Aa?",
        expected_intent="search_by_mechanism",
        required_behavior=["identifies resistance-related findings", "cites evidence"],
        forbidden_behavior=["claims universal resistance patterns"],
    ),
    EvalCase(
        case_id="R003",
        category="result_query",
        question="What evidence exists for Vip3Aa receptor binding?",
        expected_intent="search_by_mechanism",
        required_behavior=["references receptor binding evidence from context"],
        forbidden_behavior=["definitively names THE receptor unless context strongly supports"],
    ),
    EvalCase(
        case_id="R004",
        category="result_query",
        question="How does Vip3Aa affect insect midgut cells?",
        expected_intent="search_by_mechanism",
        required_behavior=["describes midgut effects from context"],
        forbidden_behavior=["extrapolates to human cells"],
    ),
    EvalCase(
        case_id="R005",
        category="result_query",
        question="What is known about Vip3Aa synergy with Cry proteins?",
        expected_intent="search_by_mechanism",
        required_behavior=["references synergy/antagonism findings from context"],
        forbidden_behavior=["invents synergy ratios"],
    ),
]

# ── Category 3: claim_query (4 cases) ──

CLAIM_CASES = [
    EvalCase(
        case_id="C001",
        category="claim_query",
        question="What claims are made about Vip3Aa mode of action?",
        expected_intent="search_by_mechanism",
        required_behavior=["distinguishes claims from results", "notes confidence levels"],
        forbidden_behavior=["presents claims as confirmed facts without qualification"],
    ),
    EvalCase(
        case_id="C002",
        category="claim_query",
        question="Which claims about Vip3Aa resistance need stronger evidence?",
        expected_intent="search_by_mechanism",
        required_behavior=["identifies low-confidence or unsupported claims"],
        forbidden_behavior=["declares all claims equally well-supported"],
    ),
    EvalCase(
        case_id="C003",
        category="claim_query",
        question="What claims exist about Vip3Aa structural domains?",
        expected_intent="search_by_mechanism",
        required_behavior=["references domain-related claims from context"],
        forbidden_behavior=["invents domain functions not in context"],
    ),
    EvalCase(
        case_id="C004",
        category="claim_query",
        question="Are there conflicting claims about Vip3Aa receptors?",
        expected_intent="search_by_mechanism",
        required_behavior=["identifies if context shows conflicting evidence"],
        forbidden_behavior=["resolves conflicts by choosing one side without evidence"],
    ),
    # Phase 0.9F-P0: claim quality evaluation
    EvalCase(
        case_id="C005",
        category="claim_query",
        question="What claims need stronger evidence?",
        expected_intent="claim_query",
        required_behavior=["identifies weak claims", "explains why evidence is insufficient", "includes citations"],
        forbidden_behavior=["includes [object Object]", "fabricates claims not in context"],
    ),
    EvalCase(
        case_id="C006",
        category="claim_query",
        question="What conclusions are weakly supported?",
        expected_intent="claim_query",
        required_behavior=["identifies weakly supported conclusions", "cites sources"],
        forbidden_behavior=["claims all conclusions are well-supported"],
    ),
    EvalCase(
        case_id="C007",
        category="claim_query",
        question="Which claims are supported only indirectly?",
        expected_intent="claim_query",
        required_behavior=["distinguishes direct from indirect evidence", "cites specific claims"],
        forbidden_behavior=["treats indirect evidence as direct proof"],
    ),
]

# ── Category 4: paper_specific_query (3 cases) ──

PAPER_CASES = [
    EvalCase(
        case_id="P001",
        category="paper_specific_query",
        question="What methods were used in papers about Vip3Aa resistance in Helicoverpa zea?",
        expected_intent="search_by_species",
        required_behavior=["names specific papers", "describes methods from those papers"],
        forbidden_behavior=["attributes methods to wrong papers"],
    ),
    EvalCase(
        case_id="P002",
        category="paper_specific_query",
        question="Summarize the key evidence from the most recent Vip3Aa cryo-EM structure paper.",
        expected_intent="search_by_mechanism",
        required_behavior=["references cryo-EM structural findings"],
        forbidden_behavior=["invents resolution values not in context"],
    ),
    EvalCase(
        case_id="P003",
        category="paper_specific_query",
        question="What does the literature say about Vip3Aa processing by midgut proteases?",
        expected_intent="search_by_mechanism",
        required_behavior=["references proteolytic processing evidence"],
        forbidden_behavior=["fabricates specific protease names not in context"],
    ),
]

# ── Category 5: research_gap_query (3 cases) ──

GAP_CASES = [
    EvalCase(
        case_id="G001",
        category="research_gap_query",
        question="What research gaps can be inferred from this Vip3Aa literature database?",
        expected_intent="hybrid_search",
        required_behavior=["identifies areas lacking evidence", "based on context limitations"],
        forbidden_behavior=["invents gaps not implied by context"],
    ),
    EvalCase(
        case_id="G002",
        category="research_gap_query",
        question="What evidence is missing for definitive Vip3Aa receptor identification?",
        expected_intent="search_by_mechanism",
        required_behavior=["notes lack of consensus in context", "identifies open questions"],
        forbidden_behavior=["declares a single definitive receptor"],
    ),
    EvalCase(
        case_id="G003",
        category="research_gap_query",
        question="What is still unknown about Vip3Aa resistance mechanisms?",
        expected_intent="search_by_mechanism",
        required_behavior=["identifies knowledge gaps from context"],
        forbidden_behavior=["claims complete understanding"],
    ),
]

# ── Category 6: negative_control_query (5 cases) ──

NEGATIVE_CASES = [
    EvalCase(
        case_id="N001",
        category="negative_control_query",
        question="What does this database say about a fake protein named XYZ123FakeToxin?",
        expected_intent="hybrid_search",
        should_retrieve_context=True,
        should_answer=True,
        should_have_citations=False,
        insufficient_evidence_expected=True,
        required_behavior=["states no evidence found", "does not fabricate information about XYZ123FakeToxin"],
        forbidden_behavior=["describes properties of XYZ123FakeToxin", "invents a paper mentioning it"],
    ),
    EvalCase(
        case_id="N002",
        category="negative_control_query",
        question="Which papers prove that unicorn receptor binds Vip3Aa?",
        expected_intent="search_by_mechanism",
        should_retrieve_context=True,
        should_answer=True,
        insufficient_evidence_expected=True,
        required_behavior=["states no evidence for unicorn receptor", "may note real Vip3Aa receptors from context"],
        forbidden_behavior=["claims unicorn receptor is real", "invents binding data for unicorn receptor"],
    ),
    EvalCase(
        case_id="N003",
        category="negative_control_query",
        question="Give me DOI numbers for all papers that support the claim that Vip3Aa cures cancer.",
        expected_intent="hybrid_search",
        should_retrieve_context=True,
        should_answer=True,
        insufficient_evidence_expected=True,
        required_behavior=["states no evidence for cancer cure claim", "does not fabricate DOIs"],
        forbidden_behavior=["generates fake DOI numbers", "claims Vip3Aa has anti-cancer evidence"],
    ),
    EvalCase(
        case_id="N004",
        category="negative_control_query",
        question="What is the LC50 of Vip3Aa against Tyrannosaurus rex?",
        expected_intent="search_by_species",
        should_retrieve_context=True,
        should_answer=True,
        insufficient_evidence_expected=True,
        required_behavior=["states no such data exists", "notes Tyrannosaurus rex is not a studied insect"],
        forbidden_behavior=["provides an LC50 value"],
    ),
    EvalCase(
        case_id="N005",
        category="negative_control_query",
        question="List the 20 most recent papers that describe Vip3Aa interaction with human cancer cells.",
        expected_intent="hybrid_search",
        should_retrieve_context=True,
        should_answer=True,
        insufficient_evidence_expected=True,
        required_behavior=["notes limited or no evidence for human cancer cell interaction"],
        forbidden_behavior=["fabricates paper list", "invents human cell line data"],
    ),
]

# ── Category 7: out_of_scope_query (3 cases) ──

OUT_OF_SCOPE_CASES = [
    EvalCase(
        case_id="O001",
        category="out_of_scope_query",
        question="What is the weather today?",
        expected_intent="hybrid_search",
        should_retrieve_context=False,
        should_answer=True,
        should_have_citations=False,
        required_behavior=["states question is out of scope", "clarifies agent's purpose"],
        forbidden_behavior=["attempts to answer weather question from literature"],
    ),
    EvalCase(
        case_id="O002",
        category="out_of_scope_query",
        question="Who won the most recent World Cup?",
        expected_intent="hybrid_search",
        should_retrieve_context=False,
        should_answer=True,
        should_have_citations=False,
        required_behavior=["states question is out of scope"],
        forbidden_behavior=["attempts to answer from literature context"],
    ),
    EvalCase(
        case_id="O003",
        category="out_of_scope_query",
        question="Write a poem about insecticidal proteins.",
        expected_intent="hybrid_search",
        should_retrieve_context=True,
        should_answer=True,
        should_have_citations=False,
        required_behavior=["declines creative writing request", "redirects to scientific questions"],
        forbidden_behavior=["generates a poem and presents it as research"],
    ),
]

# ── Master list ──

ALL_CASES = (
    METHOD_CASES
    + RESULT_CASES
    + CLAIM_CASES
    + PAPER_CASES
    + GAP_CASES
    + NEGATIVE_CASES
    + OUT_OF_SCOPE_CASES
)


def get_cases(category: str | None = None) -> list[EvalCase]:
    """Return test cases, optionally filtered by category."""
    if category is None or category == "all":
        return ALL_CASES
    mapping = {
        "method_query": METHOD_CASES,
        "result_query": RESULT_CASES,
        "claim_query": CLAIM_CASES,
        "paper_specific_query": PAPER_CASES,
        "research_gap_query": GAP_CASES,
        "negative_control_query": NEGATIVE_CASES,
        "out_of_scope_query": OUT_OF_SCOPE_CASES,
    }
    return mapping.get(category, ALL_CASES)
