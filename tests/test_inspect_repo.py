import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "reverse-engineer" / "scripts" / "inspect_repo.py"
spec = importlib.util.spec_from_file_location("inspect_repo", SCRIPT_PATH)
inspect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspect)


class InspectRepoTests(unittest.TestCase):
    def test_inspects_manifest_and_route_without_exposing_env(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "package.json").write_text(json.dumps({"dependencies": {"react": "1.0", "express": "2.0"}}))
            (root / "server.js").write_text("app.get('/api/items', handler);\nfetch('/api/public');\n")
            (root / ".env").write_text("TOKEN=super-secret")
            (root / "credentials.json").write_text('{"private": "secret"}')
            (root / "node_modules").mkdir()
            (root / "node_modules" / "skip.js").write_text("app.get('/secret', handler)")
            result = inspect.analyze(root)
            self.assertEqual(result["file_count"], 2)
            self.assertEqual(result["framework_hints"], ["Express", "React"])
            self.assertEqual([route["path"] for route in result["route_hints"]], ["/api/items", "/api/public"])
            self.assertNotIn("secret", json.dumps(result))

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            result = inspect.analyze(Path(td))
            self.assertEqual(result["file_count"], 0)
            self.assertEqual(result["route_hints"], [])
            self.assertIn("Static Repository", inspect.to_markdown(result))


if __name__ == "__main__":
    unittest.main()
