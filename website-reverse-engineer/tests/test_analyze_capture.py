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
        self.assertIn("Original", report.title() if "original" in report else report)

    def test_rejects_unrecognized_schema_and_sanitizes_injected_text(self):
        with self.assertRaises(ValueError):
            module.summarize({"schema_version": 1, "pages": []})
        self.assertNotIn("<script>", module.clean("<script>alert('x')</script>"))


if __name__ == "__main__":
    unittest.main()
