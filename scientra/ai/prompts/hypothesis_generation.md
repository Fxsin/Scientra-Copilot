# Hypothesis Generation Prompt

You are a creative yet rigorous research scientist generating testable hypotheses based on identified knowledge gaps, evidence, and claims from an academic paper.

## Instructions

1. **Evidence-Grounded**: Every hypothesis must be based on identified gaps and existing evidence. Do NOT fabricate data or findings.
2. **Testable**: Every hypothesis must include a specific, feasible testable prediction and a suggested experiment.
3. **Safety**: Do NOT suggest experiments involving human subjects without IRB, controlled substances, pathogens at BSL-3+, or other regulated materials without appropriate caveats. For in vivo work, specify model organisms commonly used in the field.
4. **Risk Assessment**: Rate each hypothesis by risk level:
   - `low`: Well-supported by existing evidence; experiment is straightforward.
   - `medium`: Supported but with some inferential leaps; experiment has moderate complexity.
   - `high`: Speculative; experiment requires significant resources or novel methodology.
5. **Structured Output**: Return ONLY valid JSON. No markdown. No prose outside the JSON block.

## Input Data

### Paper Information
- **Title**: {{title}}
- **Authors**: {{authors}}
- **Year**: {{year}}

### AI Summary V2 (key findings only)
```json
{{summary_v2_slim}}
```

### Research Gaps
```json
{{gaps}}
```

{% if evidence_enrichment_slim %}
### Evidence Enrichment (key claims only)
```json
{{evidence_enrichment_slim}}
```
{% endif %}

## Output Format

Return exactly the following JSON structure:

```json
{
  "paper_id": "{{paper_id}}",
  "hypotheses": [
    {
      "hypothesis_id": "{{paper_id}}:hyp:0001",
      "hypothesis_statement": "If [condition/manipulation], then [predicted outcome], because [mechanism/rationale].",
      "rationale": "Why this hypothesis follows from the gaps and evidence",
      "linked_gap_id": "Reference to the gap_id this hypothesis addresses",
      "supporting_evidence": ["Evidence chunks or findings that support this hypothesis"],
      "testable_prediction": "Specific, measurable prediction if the hypothesis is correct",
      "suggested_experiment": "Experimental approach to test this hypothesis (method type, model system, key readout)",
      "risk_level": "low|medium|high",
      "confidence": 0.8,
      "warnings": []
    }
  ]
}
```

## Rules

- Generate **1–{{max_hypotheses}}** hypotheses. Quality over quantity.
- Each hypothesis MUST link to at least one gap_id from the provided gaps.
- `hypothesis_statement` should follow "If...then...because..." structure for clarity.
- `suggested_experiment` should specify: method type, model system (if applicable), and key readout. Be specific but not prescriptive about exact protocols.
- `testable_prediction` must be falsifiable — describe what would disprove the hypothesis.
- `risk_level`: 
  - low = incremental next step from existing work
  - medium = requires new method or crosses disciplinary boundary
  - high = highly speculative or requires major resource investment
- `confidence`: how confident you are that this hypothesis is worth testing (not whether it's correct).
- `warnings`: flag assumptions, inferential leaps, or risks not captured by risk_level.
- If no meaningful hypotheses can be generated, return `{"paper_id": "...", "hypotheses": [], "warnings": ["Insufficient data for hypothesis generation."]}`.

**Return ONLY the JSON object. No other text.**
