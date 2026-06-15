"""Dataset benchmark runner for P6.5.

Benchmarks Dataset Intelligence:
  dataset manifest loading, card loading, entity index loading,
  entity query, dataset type query, comparison query.

Missing dataset intelligence → warning, no crash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scientra.benchmark.benchmark_schema import BenchmarkResult, BenchmarkTask, BenchmarkWarning, RuntimeMetric
from scientra.benchmark.runtime_timer import RuntimeTimer
from scientra.io.storage_layout import get_storage

DS_DIR = "05_Knowledge/dataset_intelligence"


def _resolve_root() -> Path:
    return get_storage().root


def _load_json(root: Path, *parts: str) -> Any:
    """Load a JSON file. Returns data or None."""
    p = root.joinpath(*parts)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_dataset_benchmark(root: Path | None = None) -> BenchmarkResult:
    """Run dataset benchmark."""
    if root is None:
        root = _resolve_root()

    tasks = [
        BenchmarkTask(task_id="dataset_manifest", category="dataset", description="Load dataset manifest", runner="dataset_benchmark_runner"),
        BenchmarkTask(task_id="dataset_cards", category="dataset", description="Load dataset cards", runner="dataset_benchmark_runner"),
        BenchmarkTask(task_id="dataset_entity_index", category="dataset", description="Load entity index", runner="dataset_benchmark_runner"),
        BenchmarkTask(task_id="dataset_entity_query", category="dataset", description="Entity query", runner="dataset_benchmark_runner"),
        BenchmarkTask(task_id="dataset_type_query", category="dataset", description="Dataset type query", runner="dataset_benchmark_runner"),
        BenchmarkTask(task_id="dataset_comparison", category="dataset", description="Comparison query", runner="dataset_benchmark_runner"),
    ]

    metrics: list[RuntimeMetric] = []
    warnings: list[BenchmarkWarning] = []

    # 1. Dataset manifest loading
    t = RuntimeTimer("dataset:manifest_loading")
    t.start()
    manifest = _load_json(root, DS_DIR, "dataset_manifest.json")
    if manifest is None:
        t.warn("dataset_manifest.json not found")
        warnings.append(BenchmarkWarning(module="dataset", message="dataset_manifest.json not found"))
        dataset_count = 0
    else:
        dataset_count = len(manifest) if isinstance(manifest, list) else 1
    t.add_metadata("dataset_count", dataset_count)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 2. Dataset card loading
    t = RuntimeTimer("dataset:card_loading")
    t.start()
    cards_dir = root / DS_DIR / "cards"
    card_count = 0
    if cards_dir.exists():
        card_files = list(cards_dir.glob("*.json"))
        card_count = len(card_files)
        if card_files:
            try:
                card = json.loads(card_files[0].read_text(encoding="utf-8"))
                t.add_metadata("sample_card_type", card.get("dataset_type", ""))
            except Exception:
                pass
    t.add_metadata("card_count", card_count)
    if card_count == 0:
        warnings.append(BenchmarkWarning(module="dataset", message="No dataset cards found"))
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 3. Entity index loading
    t = RuntimeTimer("dataset:entity_index_loading")
    t.start()
    entity_index = _load_json(root, DS_DIR, "entity_index.json")
    entity_count = 0
    if entity_index is not None:
        if isinstance(entity_index, dict):
            entity_count = len(entity_index)
        elif isinstance(entity_index, list):
            entity_count = len(entity_index)
    t.add_metadata("entity_count", entity_count)
    if entity_count == 0:
        warnings.append(BenchmarkWarning(module="dataset", message="Entity index empty or not found"))
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 4. Entity query (search entity index)
    t = RuntimeTimer("dataset:entity_query")
    t.start()
    query_hits = 0
    if entity_index and isinstance(entity_index, dict):
        for key in list(entity_index.keys())[:100]:
            if "expression" in str(key).lower() or "lc50" in str(key).lower():
                query_hits += 1
    t.add_metadata("query_hits", query_hits)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 5. Dataset type query
    t = RuntimeTimer("dataset:type_query")
    t.start()
    type_counts: dict[str, int] = {}
    if manifest and isinstance(manifest, list):
        for ds in manifest:
            ds_type = ds.get("type", ds.get("dataset_type", "unknown")) if isinstance(ds, dict) else "unknown"
            type_counts[str(ds_type)] = type_counts.get(str(ds_type), 0) + 1
    t.add_metadata("type_counts", type_counts)
    t.stop(success=True)
    metrics.append(t.to_metric())

    # 6. Comparison query
    t = RuntimeTimer("dataset:comparison_query")
    t.start()
    comparison_count = 0
    if entity_index and isinstance(entity_index, dict):
        # Find entities appearing in multiple datasets
        for key, val in entity_index.items():
            if isinstance(val, (list, dict)):
                count = len(val) if isinstance(val, list) else len(val)
                if count > 1:
                    comparison_count += 1
    t.add_metadata("comparable_entity_count", comparison_count)
    t.stop(success=True)
    metrics.append(t.to_metric())

    passed = sum(1 for m in metrics if m.success)
    total_ms = sum(m.duration_ms for m in metrics)

    return BenchmarkResult(
        category="dataset",
        tasks=tasks,
        runtime_metrics=metrics,
        warnings=warnings,
        passed=passed,
        warning_count=len(warnings),
        failed=len(metrics) - passed,
        total_duration_ms=round(total_ms, 3),
        success=True,
    )
