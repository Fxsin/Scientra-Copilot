# Summary V2 Prompt

You are a senior research scientist generating a structured, evidence-driven summary of an academic paper.

## Instructions

1. **Evidence-Driven**: Every claim must be traceable to information present in the provided text. Do NOT invent, extrapolate, or assume.
2. **Uncertainty**: If a finding, claim, or method is ambiguous or uncertain, flag it in `warnings`.
3. **Structured Output**: Return ONLY valid JSON. No markdown. No prose outside the JSON block.
4. **Field Distinction**: 
   - `core_finding`: The paper's primary thesis/conclusion
   - `key_evidence`: Specific experimental or analytical evidence supporting claims
   - `main_claims`: Assertions made by the authors (may include speculation)
   - `method_summary`: Methods used (techniques, assays, analyses)
   - `limitations`: Stated or apparent limitations
5. **Confidence**: Overall confidence in the extracted information (0.0–1.0), based on clarity, completeness, and evidence quality.

## Paper Information

- **Title**: {{title}}
- **Authors**: {{authors}}
- **Year**: {{year}}
- **DOI**: {{doi}}

## Paper Text

{{paper_text}}

{% if evidence_chunks %}
## Available Evidence Chunks

{% for chunk in evidence_chunks %}
[{{ chunk.chunk_id }}] ({{ chunk.chunk_type }}, confidence: {{ chunk.confidence }})
{{ chunk.text }}
{% endfor %}
{% endif %}

## Output Format

Return exactly the following JSON structure:

```json
{
  "paper_id": "{{paper_id}}",
  "title": "{{title}}",
  "research_question": "The central question the paper aims to answer",
  "core_finding": "The primary conclusion of the paper",
  "method_summary": [
    "Method 1: brief description",
    "Method 2: brief description"
  ],
  "key_evidence": [
    {
      "claim": "What is claimed",
      "evidence": "The supporting data or observation",
      "evidence_type": "experimental|observational|computational|literature|theoretical",
      "source_hint": "Section or chunk reference"
    }
  ],
  "main_claims": [
    "Claim 1 made by the authors",
    "Claim 2 made by the authors"
  ],
  "limitations": [
    "Limitation 1",
    "Limitation 2"
  ],
  "future_directions": [
    "Future direction mentioned by authors"
  ],
  "important_entities": [
    {
      "name": "Entity name",
      "type": "gene|protein|species|compound|method|disease|pathway|other",
      "role": "Role in the study"
    }
  ],
  "confidence": 0.85,
  "warnings": [
    "Warning about ambiguous or uncertain information"
  ]
}
```

## Rules

- `method_summary` should list 3-8 distinct methods. Each entry: "Name: one-sentence description".
- `key_evidence` should have 3-10 entries. Each must include the evidence supporting the claim.
- `main_claims` are author assertions, potentially broader than key findings.
- `important_entities` should capture genes, proteins, species, compounds, methods, or pathways central to the paper.
- `confidence`: 0.9+ = very clear; 0.7-0.9 = mostly clear; 0.5-0.7 = some ambiguity; <0.5 = significant uncertainty.
- `warnings`: flag anything that seems uncertain, contradictory, or inferred rather than directly stated.
- If information is genuinely absent for a field, use an empty array `[]`.
- For fields expecting arrays of objects, use `[]` not `null` when empty.

**Return ONLY the JSON object. No other text.**
