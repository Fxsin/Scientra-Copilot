import tempfile, csv
from pathlib import Path
import pytest
from scientra.datasets.intelligence.dataset_loader import load_dataset

class TestLoader:
    def test_csv(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            writer = csv.writer(f); writer.writerow(["Gene", "log2FC", "pvalue"]); writer.writerow(["GeneA", "2.5", "0.001"]); f.flush()
            r = load_dataset(f.name)
        Path(f.name).unlink()
        assert r["load_status"] == "loaded"; assert r["n_rows"] >= 2; assert "Gene" in r["headers"]

    def test_tsv(self):
        with tempfile.NamedTemporaryFile(suffix=".tsv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Gene\tlog2FC\tpvalue\nGeneA\t2.5\t0.001\n"); f.flush()
            r = load_dataset(f.name)
        Path(f.name).unlink()
        assert r["load_status"] == "loaded"

    def test_missing(self):
        r = load_dataset("/nonexistent/file.csv")
        assert r["load_status"] == "failed"
