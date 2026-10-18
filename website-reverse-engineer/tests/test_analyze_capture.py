"""Tests for the browser capture Markdown analyzer (offline fixture)."""
import importlib.util
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "analyze_capture.py"
spec = importlib.util.spec_from_file_location("analyze_capture", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def fixture(self):
        return json.loads((ROOT / "examples" / "sample_capture.json").read_text())

    def test_report_includes_navigation_and_responsive_evidence(self):
        report = module.summarize(self.fixture())
        self.assertIn("flowchart LR", report)
        self.assertIn("page_home --> page_about", report)
        self.assertIn("screenshots/home-mobile.png", report)
        self.assertIn("Suggested original rebuild roadmap", report)

    def test_rejects_unrecognized_schema_and_sanitizes_injected_text(self):
        with self.assertRaises(ValueError):
            module.summarize({"schema_version": 1, "pages": []})
        self.assertNotIn("<script>", module.clean("<script>alert('x')</script>"))


    def test_mermaid_labels_cannot_break_out_and_ids_stay_unique(self):
        data = {"schema_version": 2, "pages": [
            {"path": '/a"]-->x["evil', "viewports": {}},
            {"path": "/a-b", "viewports": {}},
            {"path": "/a_b", "viewports": {}},
        ]}
        report = module.summarize(data)
        mermaid = report.split("```mermaid", 1)[1].split("```", 1)[0]
        node_lines = [line for line in mermaid.splitlines() if "[" in line]
        self.assertEqual(len(node_lines), 3)
        for line in node_lines:
            label = line.split("[", 1)[1]
            # Exactly one opening and one closing quote: the label never ends early.
            self.assertEqual(label.count('"'), 2, line)
        ids = [line.split("[", 1)[0].strip() for line in node_lines]
        self.assertEqual(len(set(ids)), 3)

    def test_malformed_capture_fields_do_not_crash(self):
        data = {"schema_version": 2, "warnings": "not-a-list", "pages": [
            "not-a-page",
            {"path": "/", "viewports": {
                "desktop": {"tokens": {"fonts": [{"value": "Inter", "count": "abc"}, "junk"]},
                            "landmarks": ["junk", {"tag": "main"}], "links": [None, 5, "/"],
                            "headings": [None]},
                "mobile": "junk"}},
        ]}
        report = module.summarize(data)
        self.assertIn("`Inter` | 0 |", report)
        self.assertIn("main ×1", report)
        with self.assertRaises(ValueError):
            module.summarize(["not", "an", "object"])

    def test_cli_reports_bad_input_without_traceback(self):
        import subprocess, sys, tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write("{not json")
        proc = subprocess.run([sys.executable, str(MODULE_PATH), handle.name], capture_output=True, text=True)
        Path(handle.name).unlink()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Cannot analyze", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
