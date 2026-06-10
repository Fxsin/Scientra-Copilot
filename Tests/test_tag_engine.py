from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scientra.tags import (  # noqa: E402
    assign_tags,
    load_dictionary,
    load_ontology,
    retag_all,
    retag_by_tag,
    validate_dictionary,
)


class TagEngineTests(unittest.TestCase):
    def test_assign_tags_uses_configured_dictionary(self) -> None:
        ontology = {
            "schema_version": "test.v1",
            "_config_hash": "ontology-hash",
            "categories": {"CATEGORY": ["ConfiguredTag"]},
        }
        dictionary = {
            "dictionary_version": "test.v1",
            "_config_hash": "dictionary-hash",
            "tags": {
                "ConfiguredTag": {
                    "synonyms": ["peritrophic membrane"],
                    "include_patterns": [r"\bperitrophic\s+membrane\b"],
                    "exclude_patterns": [r"\bpost\s+meridiem\b"],
                    "weight": 1.0,
                    "min_score": 1.0,
                }
            },
        }
        result = assign_tags(
            {"abstract": "The peritrophic membrane affected receptor binding."},
            ontology,
            dictionary,
        )
        self.assertEqual(result["assigned_tags"], {"CATEGORY": ["ConfiguredTag"]})
        self.assertIn("peritrophic membrane", result["evidence"]["ConfiguredTag"]["matched_terms"])

        excluded = assign_tags(
            {"abstract": "The abbreviation PM here means post meridiem."},
            ontology,
            dictionary,
        )
        self.assertEqual(excluded["assigned_tags"], {})

    def test_dictionary_must_match_ontology(self) -> None:
        ontology = {
            "schema_version": "test.v1",
            "_config_hash": "ontology-hash",
            "categories": {"CATEGORY": ["KnownTag"]},
        }
        dictionary = {
            "dictionary_version": "test.v1",
            "_config_hash": "dictionary-hash",
            "tags": {
                "OtherTag": {
                    "synonyms": [],
                    "include_patterns": [],
                    "exclude_patterns": [],
                    "weight": 1.0,
                    "min_score": 1.0,
                }
            },
        }
        with self.assertRaises(ValueError):
            validate_dictionary(dictionary, ontology)

    def test_retag_all_writes_tags_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_test_project(root)

            result = retag_all(
                root=root,
                update_sqlite=False,
                update_lancedb=False,
            )

            self.assertEqual(result["processed_papers"], 1)
            tags_path = root / "05_Index" / "tags" / "paper_test" / "tags.yaml"
            self.assertTrue(tags_path.exists())
            tags = yaml.safe_load(tags_path.read_text(encoding="utf-8"))
            self.assertFalse(tags["llm_used"])
            self.assertFalse(tags["summary_regenerated"])
            self.assertFalse(tags["embedding_regenerated"])
            self.assertEqual(tags["assigned_tags"]["CATEGORY"], ["ConfiguredTag"])
            self.assertTrue((root / "07_Workflows" / "reports" / "retag_report.md").exists())

            changed_only = retag_all(
                root=root,
                changed_only=True,
                update_sqlite=False,
                update_lancedb=False,
            )
            self.assertEqual(changed_only["processed_papers"], 0)
            self.assertEqual(changed_only["skipped_papers"], 1)

    def test_retag_by_tag_preserves_other_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_test_project(root)
            retag_all(root=root, update_sqlite=False, update_lancedb=False)

            dictionary_path = root / "Config" / "tag_dictionary.yaml"
            dictionary = yaml.safe_load(dictionary_path.read_text(encoding="utf-8"))
            dictionary["tags"]["ConfiguredTag"]["synonyms"] = ["not present"]
            dictionary["tags"]["ConfiguredTag"]["include_patterns"] = []
            dictionary["dictionary_version"] = "test.v2"
            dictionary_path.write_text(yaml.safe_dump(dictionary, sort_keys=False), encoding="utf-8")

            result = retag_by_tag(
                "ConfiguredTag",
                root=root,
                update_sqlite=False,
                update_lancedb=False,
            )
            self.assertEqual(result["processed_papers"], 1)
            tags_path = root / "05_Index" / "tags" / "paper_test" / "tags.yaml"
            tags = yaml.safe_load(tags_path.read_text(encoding="utf-8"))
            self.assertEqual(tags["assigned_tags"], {})

    def test_default_configs_load(self) -> None:
        ontology = load_ontology(PROJECT_ROOT / "Config" / "tag_ontology.yaml")
        dictionary = load_dictionary(PROJECT_ROOT / "Config" / "tag_dictionary.yaml")
        self.assertTrue(ontology["categories"])
        self.assertTrue(dictionary["tags"])
        self.assertTrue(validate_dictionary(dictionary, ontology))


def write_test_project(root: Path) -> None:
    (root / "Config").mkdir(parents=True)
    (root / "02_Metadata" / "yaml").mkdir(parents=True)
    (root / "03_Summary" / "raw_text").mkdir(parents=True)

    ontology = {
        "schema_version": "test.v1",
        "categories": {
            "CATEGORY": ["ConfiguredTag"],
            "OTHER": ["OtherConfiguredTag"],
        },
    }
    dictionary = {
        "dictionary_version": "test.v1",
        "tags": {
            "ConfiguredTag": {
                "synonyms": ["peritrophic membrane"],
                "include_patterns": [r"\bperitrophic\s+membrane\b"],
                "exclude_patterns": [r"\bpost\s+meridiem\b"],
                "weight": 1.0,
                "min_score": 1.0,
            },
            "OtherConfiguredTag": {
                "synonyms": ["absent phrase"],
                "include_patterns": [],
                "exclude_patterns": [],
                "weight": 1.0,
                "min_score": 1.0,
            },
        },
    }
    metadata = {
        "paper_id": "paper_test",
        "title": "Configured title",
        "abstract": "The peritrophic membrane changes binding.",
    }

    (root / "Config" / "tag_ontology.yaml").write_text(
        yaml.safe_dump(ontology, sort_keys=False),
        encoding="utf-8",
    )
    (root / "Config" / "tag_dictionary.yaml").write_text(
        yaml.safe_dump(dictionary, sort_keys=False),
        encoding="utf-8",
    )
    (root / "02_Metadata" / "yaml" / "paper_test.metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False),
        encoding="utf-8",
    )
    (root / "03_Summary" / "raw_text" / "paper_test.txt").write_text(
        "This raw text mentions peritrophic membrane once.",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
