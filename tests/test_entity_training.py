"""Offline regression tests: no downloads, torch or transformers required."""
import importlib.util
import argparse
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "api/models/entity_extraction_fine-tuned.py"
SPEC = importlib.util.spec_from_file_location("entity_training", PATH)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class EntityTrainingTests(unittest.TestCase):
    def row(self, text="Meet Alice.", name="Alice", uid="1"):
        start = text.index(name)
        return m.validate_record({"uid": uid, "text": text, "spans": repr([
            {"start": start, "end": start + len(name), "text": name, "label": "name"}
        ])}, "train", 0)

    def test_literal_spans_preserve_text_and_offsets(self):
        row = self.row("Hi,\n  Alice!")
        self.assertEqual(row["text"], "Hi,\n  Alice!")
        self.assertEqual(row["spans"][0]["start"], 6)

    def test_mismatched_value_rejected(self):
        with self.assertRaisesRegex(ValueError, "mismatch"):
            m.validate_record({"text": "Alice", "spans": [
                {"start": 0, "end": 5, "text": "alice", "label": "name"}]}, "train", 0)

    def test_bad_offsets_and_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, "offsets"):
            m.validate_record({"text": "Alice", "spans": [
                {"start": -1, "end": 5, "text": "Alice", "label": "name"}]}, "train", 0)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            m.validate_record({"text": "Alice", "spans": [
                {"start": 0, "end": 5, "text": "Alice", "label": "name"},
                {"start": 1, "end": 5, "text": "lice", "label": "other"}]}, "train", 0)

    def test_code_is_not_evaluated(self):
        with self.assertRaises((ValueError, SyntaxError)):
            m.validate_record({"text": "Alice", "spans": "__import__('os').getcwd()"}, "train", 0)

    def test_template_groups_and_unrelated_text(self):
        rows = [self.row(uid="a"), self.row("Meet Bob.", "Bob", "b"),
                self.row("Alice travels.", "Alice", "c")]
        self.assertEqual(sorted(map(len, m.group_rows(rows))), [1, 2])

    def test_source_id_connects_groups_transitively(self):
        rows = [self.row(uid="a"), self.row("Meet Bob.", "Bob", "b"),
                self.row("Bob travels.", "Bob", "b")]
        self.assertEqual(len(m.group_rows(rows)), 1)

    def test_subtokens_and_adjacent_entities(self):
        spans = [{"start": 0, "end": 5, "label": "name"},
                 {"start": 6, "end": 9, "label": "name"}]
        result = m.align_labels([(0, 0), (0, 2), (2, 5), (6, 9), (0, 0)], spans,
                                {"O": 0, "B-name": 1, "I-name": 2})
        self.assertEqual(result, [-100, 1, 2, 1, -100])

    def test_clipped_or_unrepresentable_span_is_masked(self):
        mapping = {"O": 0, "B-name": 1, "I-name": 2}
        self.assertEqual(m.align_labels([(2, 5)], [{"start": 0, "end": 5, "label": "name"}], mapping), [-100])
        self.assertEqual(m.align_labels([(0, 5)], [{"start": 1, "end": 4, "label": "name"}], mapping), [-100])

    def test_decoding_exact_spans_and_metrics(self):
        predicted = m.decode_spans([(0, 2), (2, 5), (6, 9), (9, 10)],
                                   ["B-name", "I-name", "B-name", "O"])
        self.assertEqual(predicted, {(0, 5, "name"), (6, 9, "name")})
        self.assertEqual(m.scores(1, 2, 3)["f1"], 0.4)
        self.assertEqual(m.scores(0, 0, 0)["f1"], 0)

    def test_prepare_quarantines_and_keeps_connected_test_rows_held_out(self):
        class Tokenizer:
            is_fast = True
            init_kwargs = {"_commit_hash": "offline-fixture"}

            def __call__(self, text, **kwargs):
                return {"input_ids": list(range(len(re.findall(r"\S+", text))))}

            def save_pretrained(self, path):
                Path(path).mkdir()

        def raw(row):
            return {"uid": row["id"], "text": row["text"], "spans": row["spans"]}

        data = {"train": [raw(self.row(uid="a")),
                          {"uid": "bad", "text": "", "spans": []}],
                "test": [raw(self.row("Meet Bob.", "Bob", "b"))]}
        modules = {
            "datasets": SimpleNamespace(load_from_disk=lambda _: data),
            "transformers": SimpleNamespace(
                AutoTokenizer=SimpleNamespace(from_pretrained=lambda *a, **k: Tokenizer())),
        }
        test_root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(dir=test_root, prefix="ner-test-") as directory, patch.dict("sys.modules", modules):
            self.assertTrue(Path(directory).resolve().is_relative_to(test_root))
            output = Path(directory) / "prepared"
            m.prepare(argparse.Namespace(raw=Path(directory) / "raw", output=output,
                                        checkpoint="fixture", seed=42, max_rows=0))
            self.assertEqual(list(m.read_jsonl(output / "train.jsonl")), [])
            self.assertEqual(len(list(m.read_jsonl(output / "test.jsonl"))), 2)
            self.assertEqual(len(list(m.read_jsonl(output / "quarantine.jsonl"))), 1)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["splits"]["test"]["unseen_training_labels"], ["name"])
            for row in m.read_jsonl(output / "test.jsonl"):
                self.assertNotIn("text_tagged", row)
                self.assertNotIn("document_description", row)


if __name__ == "__main__":
    unittest.main()
