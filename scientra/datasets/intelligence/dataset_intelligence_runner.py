"""Dataset Intelligence Runner — orchestrator for P5.3 pipeline.

Stages: manifest → load → schema → entities → numerics → evidence → cards → quality
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scientra.datasets.intelligence.dataset_manifest_builder import DatasetManifestBuilder
from scientra.datasets.intelligence.dataset_loader import load_dataset
from scientra.datasets.intelligence.dataset_schema_inferer import infer_schema
from scientra.datasets.intelligence.dataset_entity_extractor import extract_entities
from scientra.datasets.intelligence.dataset_numeric_profiler import profile_numerics
from scientra.datasets.intelligence.dataset_evidence_extractor import extract_evidence as extract_ds_evidence
from scientra.datasets.intelligence.dataset_card_builder import build_card
from scientra.datasets.intelligence.dataset_quality_checker import check_quality

OUTPUT_DIR = "03_Assets/dataset_intelligence"


class DatasetIntelligenceRunner:
    """Orchestrate dataset intelligence pipeline."""

    def __init__(self, root: str | Path | None = None, max_sample: int = 50, embed: bool = False) -> None:
        if root is None:
            root = Path(__file__).resolve().parent.parent.parent.parent
        self.root = Path(root)
        self.max_sample = max_sample
        self.embed = embed

    def run(self, paper_id: str, force: bool = False) -> dict[str, Any]:
        out = self.root / OUTPUT_DIR
        cards_path = out / "dataset_cards" / f"{paper_id}.json"
        if not force and cards_path.exists():
            try:
                cards = json.loads(cards_path.read_text(encoding="utf-8"))
                return {"paper_id": paper_id, "success": True, "dataset_count": len(cards) if isinstance(cards, list) else 0, "cached": True}
            except Exception:
                pass

        # Stage 1: Manifest
        mb = DatasetManifestBuilder(self.root)
        manifests = mb.build(paper_id)
        if not manifests:
            return {"paper_id": paper_id, "success": True, "dataset_count": 0, "message": "No dataset assets found."}

        # Stage 2-8: Per dataset
        schemas, loader_results, all_entities, all_numerics, all_evidence, cards, qualities = [], [], [], [], [], [], []
        for m in manifests:
            fp = m.get("source_relative_path", "")
            # Load
            lr = load_dataset(fp, self.max_sample)
            lr["dataset_id"] = m["dataset_id"]
            lr["asset_id"] = m["asset_id"]
            loader_results.append(lr)

            # Schema
            headers = lr.get("headers", [])
            samples = lr.get("sample_rows", [])
            schema = infer_schema(headers, samples)
            schema["dataset_id"] = m["dataset_id"]
            schema["paper_id"] = paper_id
            schema["asset_id"] = m["asset_id"]
            schemas.append(schema)

            # Entities
            did = m["dataset_id"]
            aid = m["asset_id"]
            entities = extract_entities(headers, samples, paper_id, did, aid)
            all_entities.append(entities)

            # Numerics
            numerics = profile_numerics(headers, samples)
            numerics["dataset_id"] = did
            numerics["paper_id"] = paper_id
            numerics["asset_id"] = aid
            all_numerics.append(numerics)

            # Evidence
            evidence = extract_ds_evidence(schema, entities, numerics, paper_id, did, aid)
            all_evidence.append(evidence)

            # Quality
            q = check_quality(m, lr, schema, entities, numerics)
            q["dataset_id"] = did
            qualities.append(q)

            # Card
            card = build_card(m, schema, lr, entities, numerics, evidence, q)
            cards.append(card)

        # Write outputs
        for sub, data in [("dataset_manifests", manifests), ("dataset_schemas", schemas),
                           ("entity_indexes", [e for el in all_entities for e in el]),
                           ("numeric_profiles", all_numerics), ("dataset_evidence", [e for el in all_evidence for e in el]),
                           ("dataset_cards", cards), ("dataset_quality", qualities)]:
            (out / sub).mkdir(parents=True, exist_ok=True)
            (out / sub / f"{paper_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Summary MD
        (out / "summaries").mkdir(parents=True, exist_ok=True)
        lines = [f"# Dataset Intelligence — {paper_id}", f"Generated: {datetime.now(timezone.utc).isoformat()}",
                  f"Datasets: {len(cards)}"]
        for c in cards:
            lines.append(f"- {c['dataset_type']}: {c['n_rows']}×{c['n_columns']} (quality: {c['quality_score']:.2f})")
        (out / "summaries" / f"{paper_id}.md").write_text("\n".join(lines), encoding="utf-8")

        return {"paper_id": paper_id, "success": True, "dataset_count": len(cards), "cached": False,
                "generated_at": datetime.now(timezone.utc).isoformat()}

    def get_cards(self, paper_id: str) -> dict[str, Any]:
        p = self.root / OUTPUT_DIR / "dataset_cards" / f"{paper_id}.json"
        if not p.exists():
            return {"paper_id": paper_id, "available": False, "datasets": [], "message": "Not yet built."}
        try:
            return {"paper_id": paper_id, "available": True, "datasets": json.loads(p.read_text(encoding="utf-8"))}
        except Exception:
            return {"paper_id": paper_id, "available": False, "datasets": []}

    def get_card(self, paper_id: str, dataset_id: str) -> dict[str, Any]:
        data = self.get_cards(paper_id)
        if not data.get("available"):
            return {"available": False, "card": None}
        for c in data["datasets"]:
            if c.get("dataset_id") == dataset_id:
                return {"available": True, "card": c}
        return {"available": False, "card": None}
