import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exposure_training", ROOT / "api/models/explosure_classifier.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ExposureTests(unittest.TestCase):
    def row(self, rid="a", text="An ordinary post", family="family"):
        return {"id": rid, "text": text, "labels": [], "evidence": [],
                "scenario_family": family, "review_status": "pending", "needs_review": False}

    def test_current_source_parses_without_execution(self):
        rows = m.load_rows(ROOT / "api/app/knowledge/explosure_examples.py")
        self.assertEqual(len(rows), 20)
        self.assertEqual(m.audit(rows)["errors"], [])
        self.assertTrue(all(r["review_status"] in {"pending", "approved", "rejected"} for r in rows))
        self.assertTrue(any(r["review_status"] == "approved" for r in rows))

    def test_invalid_evidence_and_unknown_label_rejected(self):
        r = self.row()
        r["labels"] = [m.LABELS[0]]
        r["evidence"] = [{"label": m.LABELS[0], "quote": "absent"}]
        self.assertTrue(m.audit([r])["errors"])
        r["labels"] = ["UNKNOWN"]
        self.assertTrue(m.audit([r])["errors"])

    def test_duplicate_id_rejected(self):
        self.assertTrue(m.audit([self.row(), self.row()])["errors"])

    def test_pair_and_family_links_are_transitive(self):
        a = self.row("a", "Text A", "one")
        b = self.row("b", "Text B", "one")
        c = self.row("c", "Text C", "two")
        b["pair_id"] = c["pair_id"] = "pair"
        self.assertEqual(len(set(m.groups_for([a, b, c]))), 1)

    def test_normalized_duplicate_grouping(self):
        a = self.row("a", "Hello   World", "one")
        b = self.row("b", "hello world", "two")
        self.assertEqual(len(set(m.groups_for([a, b]))), 1)


if __name__ == "__main__":
    unittest.main()
