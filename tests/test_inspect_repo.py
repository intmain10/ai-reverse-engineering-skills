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


    def write(self, root, rel, text=""):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def routes(self, result):
        return {(route["kind"], route["path"]) for route in result["route_hints"]}

    def test_route_patterns_cover_common_shapes_without_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, "src/api.ts", "\n".join([
                "router.get(`/api/v1/items/${id}`, h)",
                "app.route('/api/orders').post(h)",
                "fetch('https://api.example.com/v1/orders')",
                "fetch('https://user:pw@internal.example.com/admin')",
                "userRouter.delete('/users/:id', h)",
                "cache.get('/not-a-route')",
            ]))
            self.write(root, "main.py", '@app.get("/health")\n@users.post("/users")\n')
            self.write(root, "urls.py", "urlpatterns = [path('users/<int:pk>/', view)]\n")
            result = inspect.analyze(root)
            routes = self.routes(result)
            self.assertIn(("http-handler", "/api/v1/items/"), routes)
            self.assertIn(("http-handler", "/api/orders"), routes)
            self.assertIn(("http-handler", "/users/:id"), routes)
            self.assertIn(("outbound-request", "https://api.example.com/v1/orders"), routes)
            self.assertIn(("python-route", "/users"), routes)
            self.assertIn(("django-url", "/users/<int:pk>/"), routes)
            # A decorator matches exactly once, as a Python route.
            health = [r for r in result["route_hints"] if r["path"] == "/health"]
            self.assertEqual([r["kind"] for r in health], ["python-route"])
            dumped = json.dumps(result)
            self.assertNotIn("user:pw", dumped)
            self.assertNotIn("not-a-route", dumped)

    def test_file_system_routes_only_for_matching_framework(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, "src/pages/Home.tsx")
            self.assertEqual(inspect.analyze(root)["route_hints"], [])
            self.write(root, "package.json", json.dumps({"dependencies": {"next": "14"}}))
            self.write(root, "app/(marketing)/pricing/page.tsx")
            self.write(root, "app/api/users/route.ts")
            self.write(root, "app/_lib/page.tsx")
            self.write(root, "src/pages/_app.tsx")
            self.write(root, "src/pages/blog/index.tsx")
            routes = self.routes(inspect.analyze(root))
            self.assertIn(("nextjs-app-route", "/pricing"), routes)
            self.assertIn(("nextjs-app-route", "/api/users"), routes)
            self.assertIn(("nextjs-pages-route", "/blog"), routes)
            self.assertIn(("nextjs-pages-route", "/Home"), routes)
            self.assertFalse(any("_" in path for _, path in routes))

    def test_manifests_yield_datastore_and_integration_hints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.write(root, "package.json", json.dumps({"dependencies": {
                "@prisma/client": "5", "stripe": "1", "@aws-sdk/client-s3": "3", "ioredis": "5"}}))
            self.write(root, "pyproject.toml", "\n".join([
                "[project]", 'name = "demo"', "dependencies = [", '  "fastapi>=0.110",',
                '  "sqlalchemy[asyncio]",', "]", "[project.optional-dependencies]", 'dev = ["pytest"]',
            ]))
            self.write(root, "go.mod", "module x\nrequire (\n  github.com/gin-gonic/gin v1.9.0\n  gorm.io/gorm v1.25.0\n)\n")
            self.write(root, "Gemfile", "gem 'rails', '~> 7'\n")
            result = inspect.analyze(root)
            self.assertEqual(result["framework_hints"], ["FastAPI", "Gin", "Rails"])
            self.assertEqual(result["datastore_hints"], ["GORM", "Prisma ORM", "Redis", "SQLAlchemy"])
            self.assertEqual(result["integration_hints"], ["AWS SDK", "Stripe"])
            self.assertIn("pytest", result["declared_dependencies"])
            self.assertNotIn("demo", result["declared_dependencies"])

    def test_route_hints_are_capped_per_kind_and_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            limit = inspect.MAX_ROUTE_HINTS_PER_KIND
            self.write(root, "a.js", "".join(f"app.get('/r{i}', h)\n" for i in range(limit + 5)))
            self.write(root, "b.js", "fetch('/api/still-found')\n")
            result = inspect.analyze(root)
            self.assertEqual(sum(r["kind"] == "http-handler" for r in result["route_hints"]), limit)
            self.assertIn(("outbound-request", "/api/still-found"), self.routes(result))
            self.assertEqual(result["route_hints_truncated"], ["http-handler"])
            self.assertIn("Truncated", inspect.to_markdown(result))


if __name__ == "__main__":
    unittest.main()
