"""
Claim Quality Checker — validates claim-evidence quality.

Checks:
  1. claim has source_text (non-empty)
  2. claim originates from core_findings or discussion_points
  3. claim has linked result evidence
  4. evidence links exist
  5. claim is not too short/generic (< 30 chars)
  6. whether AI interpretation is needed

Adds fields: claim_quality_score, needs_ai_interpretation, evidence_link_status

Output: 06_PDF_DataAssets/07_claims_evidence/{paper_id}/claims_evidence.quality.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ClaimQualityChecker:
    """Validates claims and evidence links."""

    MIN_CLAIM_LENGTH = 30
    MAX_CLAIM_LENGTH = 3000
    GENERIC_PATTERNS = [
        "the present study shows",
        "in this study we",
        "our results demonstrate",
        "further studies are needed",
        "more research is required",
        "it is concluded that",
        "taken together",
        "in conclusion",
    ]

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.claims_dir = self.root / "06_PDF_DataAssets" / "07_claims_evidence"

    def check_paper(self, paper_id: str) -> dict[str, Any]:
        """Check claims for a paper. Returns summary + writes .quality.json."""
        source_path = self.claims_dir / paper_id / "claims_evidence.json"
        if not source_path.exists():
            return {"paper_id": paper_id, "status": "no_source", "total_claims": 0}

        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"paper_id": paper_id, "status": "parse_error", "error": str(e)}

        claims = data.get("claims", [])
        evidence_links = data.get("evidence_links", [])
        total = len(claims)
        links_total = len(evidence_links)

        if total == 0:
            return {"paper_id": paper_id, "status": "no_claims", "total_claims": 0}

        checked_claims: list[dict[str, Any]] = []
        scores: list[int] = []
        needs_ai_count = 0
        has_evidence_count = 0
        stats = {
            "has_source_text": 0,
            "has_evidence_link": 0,
            "too_short": 0,
            "is_generic": 0,
            "needs_ai_interpretation": 0,
            "from_core_findings": 0,
            "from_discussion_points": 0,
            "from_claims_list": 0,
        }

        for claim in claims:
            if not isinstance(claim, dict):
                continue
            score = 100
            flags: list[str] = []

            claim_text = str(claim.get("claim_text", ""))
            source_text = str(claim.get("source_text", ""))

            # 1. source_text
            if len(source_text.strip()) < 15:
                score -= 20
                flags.append("empty_source_text")
            else:
                stats["has_source_text"] += 1

            # 2. Source origin
            source_field = str(claim.get("metadata", {}).get("source_field", ""))
            if source_field == "core_findings":
                stats["from_core_findings"] += 1
            elif source_field == "discussion_points":
                stats["from_discussion_points"] += 1
            else:
                stats["from_claims_list"] += 1

            # 3. Has evidence links
            supporting = claim.get("supporting_evidence", [])
            opposing = claim.get("opposing_evidence", [])
            linked_results = claim.get("linked_result_ids", [])
            has_link = len(supporting) + len(opposing) + len(linked_results) > 0
            if has_link:
                stats["has_evidence_link"] += 1
                has_evidence_count += 1
            else:
                score -= 15
                flags.append("no_evidence_link")

            # 4. Claim length
            clen = len(claim_text.strip())
            if clen < self.MIN_CLAIM_LENGTH:
                score -= 15
                flags.append("too_short")
                stats["too_short"] += 1

            # 5. Generic claim detection
            claim_lower = claim_text.lower()
            is_generic = any(gp in claim_lower for gp in self.GENERIC_PATTERNS)
            if is_generic:
                score -= 10
                flags.append("generic_phrasing")
                stats["is_generic"] += 1

            # 6. Needs AI interpretation?
            needs_ai = (
                not has_link
                or clen < self.MIN_CLAIM_LENGTH
                or claim.get("confidence", "low") in ("low", "unknown")
            )
            if needs_ai:
                stats["needs_ai_interpretation"] += 1
                needs_ai_count += 1

            evidence_link_status = "none"
            if len(supporting) > 0:
                evidence_link_status = "has_supporting"
            elif len(opposing) > 0:
                evidence_link_status = "has_opposing"
            elif len(linked_results) > 0:
                evidence_link_status = "has_linked_results"

            claim["claim_quality_score"] = max(0, score)
            claim["needs_ai_interpretation"] = needs_ai
            claim["evidence_link_status"] = evidence_link_status
            claim["quality_flags"] = flags
            claim["quality_checked_at"] = datetime.now(timezone.utc).isoformat()

            checked_claims.append(claim)
            scores.append(max(0, score))

        # Update the data
        data["claims"] = checked_claims
        data["quality_summary"] = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "total_claims": total,
            "total_evidence_links": links_total,
            "average_quality_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "needs_ai_interpretation": needs_ai_count,
            "needs_ai_pct": round(needs_ai_count / total * 100, 1) if total > 0 else 0,
            "has_evidence_pct": round(has_evidence_count / total * 100, 1) if total > 0 else 0,
            "stats": stats,
        }

        # Write quality output
        output_path = self.claims_dir / paper_id / "claims_evidence.quality.json"
        tmp = output_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(output_path)

        return data.get("quality_summary", {})

    def get_summary(self, paper_id: str) -> dict[str, Any]:
        """Get cached quality summary, or compute."""
        quality_path = self.claims_dir / paper_id / "claims_evidence.quality.json"
        if quality_path.exists():
            try:
                data = json.loads(quality_path.read_text(encoding="utf-8"))
                return data.get("quality_summary", {})
            except Exception:
                pass
        return self.check_paper(paper_id)
