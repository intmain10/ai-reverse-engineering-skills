#!/usr/bin/env python3
"""Read-only, dependency-free first-pass survey of an authorized source repository.

This program does NOT execute project code or make network requests. Heuristics
are leads for manual verification, not statements about runtime behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import sys

IGNORE_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "vendor", "dist", "build",
    "coverage", "target", "__pycache__", ".next", ".nuxt", ".cache", "tmp", "temp"
}
IGNORE_FILES = {
    "id_rsa", "id_ed25519", "credentials.json", "secrets.json", "config.private.json",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "cargo.lock"
}
SCAN_EXTENSIONS = {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".rb", ".php"}
EXT_TO_LANG = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JSX", ".ts": "TypeScript",
    ".tsx": "TSX", ".go": "Go", ".java": "Java", ".rb": "Ruby", ".php": "PHP",
    ".rs": "Rust", ".swift": "Swift", ".kt": "Kotlin", ".dart": "Dart",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".vue": "Vue",
    ".svelte": "Svelte", ".sql": "SQL", ".sh": "Shell", ".json": "JSON",
}
MANIFESTS = {
    "package.json", "requirements.txt", "pyproject.toml", "Pipfile", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "pubspec.yaml", "Gemfile"
}
FRAMEWORK_HINTS = {
    "react": "React", "next": "Next.js", "vue": "Vue", "nuxt": "Nuxt", "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit", "angular": "Angular", "@angular/core": "Angular",
    "express": "Express", "fastify": "Fastify", "nestjs": "NestJS", "@nestjs/core": "NestJS",
    "django": "Django", "flask": "Flask", "fastapi": "FastAPI", "starlette": "Starlette",
    "react-native": "React Native", "expo": "Expo", "flutter": "Flutter", "vite": "Vite",
    "hono": "Hono", "koa": "Koa", "remix": "Remix", "@remix-run/react": "Remix", "astro": "Astro",
    "rails": "Rails", "sinatra": "Sinatra", "github.com/gin-gonic/gin": "Gin",
    "github.com/labstack/echo/v4": "Echo", "github.com/gofiber/fiber/v2": "Fiber",
    "actix-web": "Actix Web", "axum": "Axum",
}
# Declared dependencies that suggest persistence or third-party services. A key ending in "/"
# matches every package under that scope (e.g. all "@aws-sdk/" clients).
DATASTORE_HINTS = {
    "pg": "PostgreSQL", "postgres": "PostgreSQL", "psycopg2": "PostgreSQL", "psycopg2-binary": "PostgreSQL",
    "psycopg": "PostgreSQL", "asyncpg": "PostgreSQL", "mysql": "MySQL", "mysql2": "MySQL",
    "pymysql": "MySQL", "sqlite3": "SQLite", "better-sqlite3": "SQLite", "mongodb": "MongoDB",
    "mongoose": "MongoDB", "pymongo": "MongoDB", "motor": "MongoDB", "redis": "Redis", "ioredis": "Redis",
    "@prisma/client": "Prisma ORM", "prisma": "Prisma ORM", "typeorm": "TypeORM", "sequelize": "Sequelize",
    "drizzle-orm": "Drizzle ORM", "knex": "Knex", "sqlalchemy": "SQLAlchemy", "gorm.io/gorm": "GORM",
    "diesel": "Diesel", "activerecord": "ActiveRecord", "@elastic/elasticsearch": "Elasticsearch",
    "elasticsearch": "Elasticsearch", "@supabase/supabase-js": "Supabase", "supabase": "Supabase",
    "firebase": "Firebase", "firebase-admin": "Firebase", "@aws-sdk/client-dynamodb": "DynamoDB",
}
INTEGRATION_HINTS = {
    "stripe": "Stripe", "@stripe/": "Stripe", "@aws-sdk/": "AWS SDK", "boto3": "AWS SDK",
    "aws-sdk": "AWS SDK", "@google-cloud/": "Google Cloud", "twilio": "Twilio",
    "@sendgrid/mail": "SendGrid", "sendgrid": "SendGrid", "nodemailer": "SMTP email",
    "@sentry/": "Sentry", "sentry-sdk": "Sentry", "openai": "OpenAI API",
    "@anthropic-ai/sdk": "Anthropic API", "anthropic": "Anthropic API", "next-auth": "NextAuth",
    "@auth0/": "Auth0", "@clerk/": "Clerk", "passport": "Passport auth", "graphql": "GraphQL",
    "@apollo/client": "Apollo GraphQL", "@trpc/server": "tRPC", "socket.io": "Socket.IO",
    "kafkajs": "Kafka", "amqplib": "RabbitMQ", "celery": "Celery", "bullmq": "BullMQ",
}
MAX_READ_BYTES = 200_000
MAX_FILES = 15_000
MAX_ROUTE_HINTS_PER_KIND = 40
# Capture path-only route hints; deliberately exclude query strings and headers. The opening
# quote may be a backtick so template literals such as `/api/items/${id}` yield "/api/items/".
_Q = r"""['"`]"""
_PATH = r"(/[-a-zA-Z0-9_/{}:.<>]*)"
_HTTP = r"(?:get|post|put|delete|patch|options|head|all)"
_RECEIVER = r"(?:app|router|server|api|routes?|fastify|[a-z]\w*Router|[a-z]\w*Routes)"
JS_EXT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte"}
ROUTE_PATTERNS = (
    # (?<!@) keeps Python decorators like @app.get from also matching as JS handlers.
    ("http-handler", None, re.compile(r"(?<![@\w.])" + _RECEIVER + r"\." + _HTTP + r"\s*\(\s*" + _Q + _PATH)),
    ("http-handler", JS_EXT, re.compile(r"(?<![@\w.])" + _RECEIVER + r"\.route\s*\(\s*" + _Q + _PATH)),
    ("python-route", {".py"}, re.compile(r"@\w+\.(?:route|api_route|websocket|" + _HTTP + r")\s*\(\s*" + _Q + _PATH)),
    ("django-url", {".py"}, re.compile(r"\b(?:re_)?path\s*\(\s*r?['\"]\^?([-a-zA-Z0-9_/<>:.]+)")),
    ("outbound-request", None, re.compile(r"\b(?:fetch|axios(?:\." + _HTTP + r")?|\$fetch|ky|got)\s*\(\s*" + _Q + _PATH)),
    # Absolute API URLs: host and path only. The host class excludes "@", so URLs carrying
    # user:password credentials never match.
    ("outbound-request", None, re.compile(r"\b(?:fetch|axios(?:\." + _HTTP + r")?|\$fetch|ky|got|requests\.\w+|httpx\.\w+)\s*\(\s*[rf]?" + _Q + r"(https?://[-a-zA-Z0-9.:]+/[-a-zA-Z0-9_/{}:.]*)")),
)
# File-system routing conventions: (kind, required framework hint, path regex relative to the repo).
# Gated on the framework so an ordinary src/pages/ folder in a React Router app is not misread.
FILE_ROUTE_DIRS = (
    ("nextjs-app-route", "Next.js", re.compile(r"(?:^|/)(?:src/)?app/(.*?)/?(?:page|route)\.(?:jsx?|tsx?|mdx)$")),
    ("nextjs-pages-route", "Next.js", re.compile(r"(?:^|/)(?:src/)?pages/(.*)\.(?:jsx?|tsx?|mdx)$")),
    ("sveltekit-route", "SvelteKit", re.compile(r"(?:^|/)src/routes/(.*?)/?\+(?:page|server)(?:\.server)?\.(?:svelte|js|ts)$")),
    ("nuxt-page", "Nuxt", re.compile(r"(?:^|/)pages/(.*)\.vue$")),
)


def safe_rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace(os.sep, "/")


def eligible_file(name: str) -> bool:
    low = name.lower()
    if name.startswith(".") or low in IGNORE_FILES:
        return False
    if low.endswith((".key", ".pem", ".p12", ".pfx", ".keystore", ".jks", ".sqlite", ".db")):
        return False
    if "secret" in low or "credential" in low or "password" in low or "private-key" in low:
        return False
    return True


def get_files(root: Path):
    files = []
    omitted = 0
    for dirname, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(
            d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")
            and not (Path(dirname) / d).is_symlink()
        )
        for name in sorted(names):
            p = Path(dirname) / name
            if not eligible_file(name) or p.is_symlink() or not p.is_file():
                omitted += 1
                continue
            if len(files) >= MAX_FILES:
                omitted += 1
                continue
            files.append(p)
    return files, omitted


def read_small_file(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def toml_section_keys(raw: str, sections: tuple[str, ...]) -> set[str]:
    """Keys of simple TOML tables such as [dependencies] (dependency names in Cargo/Poetry)."""
    names, current = set(), None
    for line in raw.splitlines():
        header = re.match(r"\s*\[([^\]]+)\]\s*$", line)
        if header:
            current = header.group(1).strip()
            continue
        key = re.match(r"\s*([A-Za-z][\w.-]*)\s*=", line)
        if key and current in sections:
            names.add(key.group(1).lower())
    return names


def pyproject_dependencies(raw: str) -> set[str]:
    """PEP 621 dependency arrays plus Poetry dependency tables, without a TOML parser (3.9 compat)."""
    names = toml_section_keys(raw, ("tool.poetry.dependencies", "tool.poetry.dev-dependencies",
                                    "tool.poetry.group.dev.dependencies"))
    names.discard("python")
    current, collecting = None, False
    for line in raw.splitlines():
        header = re.match(r"\s*\[([^\]]+)\]\s*$", line)
        if header and not collecting:
            current = header.group(1).strip()
            continue
        if not collecting:
            array = re.match(r"\s*([\w-]+)\s*=\s*\[(.*)", line)
            in_group_table = current in ("project.optional-dependencies", "dependency-groups")
            if not array or not (array.group(1) == "dependencies" or in_group_table):
                continue
            line, collecting = array.group(2), True
        for item in re.finditer(r"""['"]\s*([A-Za-z][\w.-]*)""", line.split("]")[0] if "]" in line else line):
            names.add(item.group(1).lower())
        if "]" in line:
            collecting = False
    return names


def detect_manifests(root: Path, files: list[Path]):
    names = []
    dependencies = set()
    for path in files:
        if path.name not in MANIFESTS:
            continue
        relative = safe_rel(path, root)
        names.append(relative)
        raw = read_small_file(path)
        if raw is None:
            continue
        if path.name == "package.json":
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict):
                    for key in ("dependencies", "devDependencies", "peerDependencies"):
                        if isinstance(obj.get(key), dict):
                            dependencies.update(str(name).lower() for name in obj[key])
            except (ValueError, TypeError):
                pass
        elif path.name == "requirements.txt":
            for line in raw.splitlines():
                name = re.match(r"\s*([a-zA-Z][\w-]*)\s*(?:[<=>!~;\[]|$)", line)
                if name:
                    dependencies.add(name.group(1).lower())
        elif path.name == "pyproject.toml":
            dependencies.update(pyproject_dependencies(raw))
        elif path.name == "go.mod":
            # "require x v1" and lines inside a "require ( ... )" block.
            for match in re.finditer(r"(?m)^\s*(?:require\s+)?([a-z0-9.-]+\.[a-z]{2,}/[^\s]+)\s+v\d", raw):
                dependencies.add(match.group(1).lower())
        elif path.name == "Gemfile":
            for match in re.finditer(r"""(?m)^\s*gem\s+['"]([\w.-]+)['"]""", raw):
                dependencies.add(match.group(1).lower())
        elif path.name == "Cargo.toml":
            dependencies.update(toml_section_keys(raw, ("dependencies", "dev-dependencies")))
        elif path.name == "pubspec.yaml":
            if re.search(r"(?m)^\s*flutter\s*:", raw):
                dependencies.add("flutter")
    return names, sorted(dependencies)


def file_route(rel: str, frameworks: set[str]) -> tuple[str, str] | None:
    """Translate a file-system routing convention into a URL path, e.g. app/users/[id]/page.tsx -> /users/[id]."""
    for kind, framework, pattern in FILE_ROUTE_DIRS:
        match = pattern.search(rel) if framework in frameworks else None
        if not match:
            continue
        # Route groups "(marketing)" and private folders "_components" are not URL segments.
        segments = [seg for seg in match.group(1).split("/") if seg and not seg.startswith("(")]
        if any(seg.startswith("_") for seg in segments):
            return None
        if segments and segments[-1] == "index":
            segments.pop()
        return kind, "/" + "/".join(segments)
    return None


def hint_names(dependencies: list[str], table: dict) -> list[str]:
    found = set()
    for dep in dependencies:
        for key, label in table.items():
            if dep == key or (key.endswith("/") and dep.startswith(key)):
                found.add(label)
    return sorted(found)


def analyze(root: Path) -> dict:
    files, omitted = get_files(root)
    counts = Counter(EXT_TO_LANG.get(p.suffix.lower(), "Other") for p in files)
    manifests, dependencies = detect_manifests(root, files)
    frameworks = sorted({name for package, name in FRAMEWORK_HINTS.items() if package in dependencies})
    routes = []
    route_seen = set()
    per_kind = Counter()
    truncated = set()
    interesting = []

    def add_route(kind: str, path_value: str, source: str) -> None:
        # One hint per source line and path, whichever pattern matched first.
        key = (source, path_value)
        if key in route_seen:
            return
        route_seen.add(key)
        if per_kind[kind] >= MAX_ROUTE_HINTS_PER_KIND:
            truncated.add(kind)
            return
        per_kind[kind] += 1
        routes.append({"kind": kind, "path": path_value, "source": source})

    for p in files:
        rel = safe_rel(p, root)
        if p.name.lower() in {"app.tsx", "app.jsx", "main.ts", "main.tsx", "main.py", "main.go", "server.js", "server.ts", "manage.py", "app.py", "index.ts", "index.js", "urls.py", "wsgi.py", "asgi.py"}:
            interesting.append(rel)
        routed = file_route(rel, set(frameworks))
        if routed:
            add_route(routed[0], routed[1], f"{rel}:1")
        suffix = p.suffix.lower()
        if suffix not in SCAN_EXTENSIONS:
            continue
        code = read_small_file(p)
        if code is None:
            continue
        for lineno, line in enumerate(code.splitlines(), 1):
            for kind, extensions, pattern in ROUTE_PATTERNS:
                if extensions is not None and suffix not in extensions:
                    continue
                for match in pattern.finditer(line):
                    path_value = match.group(1)
                    if kind == "django-url" and not path_value.startswith("/"):
                        path_value = "/" + path_value
                    add_route(kind, path_value, f"{rel}:{lineno}")
    return {
        "scanned_root": str(root), "file_count": len(files), "omitted_files": omitted,
        "languages_by_file_count": dict(sorted(counts.items(), key=lambda x: (-x[1], x[0]))),
        "manifests": sorted(manifests), "declared_dependencies": dependencies,
        "framework_hints": frameworks, "possible_entry_points": sorted(interesting)[:50],
        "datastore_hints": hint_names(dependencies, DATASTORE_HINTS),
        "integration_hints": hint_names(dependencies, INTEGRATION_HINTS),
        "route_hints": routes,
        "route_hints_truncated": sorted(truncated),
        "limitations": [
            "Read-only static inspection; target application code was never executed.",
            "Frameworks, data stores and integrations are inferred from dependency declarations, not confirmed runtime usage.",
            "Routes are simple text patterns; dynamic routing and generated endpoints can be missed.",
            "Secrets, dotfiles, symlinks, vendor folders, and large files are intentionally skipped.",
            "Review output before publishing it, as repository structure and route paths may be sensitive.",
        ],
    }


def md_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("`", "'")


def to_markdown(data: dict) -> str:
    lines = [
        "# Static Repository Reconnaissance", "", "**Assessment:** preliminary, read-only heuristics, not a verified architecture report.", "",
        f"- Root: `{md_cell(data['scanned_root'])}`",
        f"- Files included: {data['file_count']}",
        f"- Files omitted: {data['omitted_files']}",
        f"- Framework hints: {', '.join(data['framework_hints']) or 'none detected'}",
        f"- Data store hints: {', '.join(data['datastore_hints']) or 'none detected'}",
        f"- Integration hints: {', '.join(data['integration_hints']) or 'none detected'}", "",
        "## Language inventory", "", "| Type | File count |", "| --- | ---: |"
    ]
    lines += [f"| {md_cell(k)} | {v} |" for k, v in data["languages_by_file_count"].items()]
    lines += ["", "## Manifests", ""]
    lines += [f"- `{md_cell(p)}`" for p in data["manifests"]] or ["- None found"]
    lines += ["", "## Possible entry points", ""]
    lines += [f"- `{md_cell(p)}`" for p in data["possible_entry_points"]] or ["- None detected"]
    lines += ["", "## Route and request hints", "", "| Kind | Path | Evidence |", "| --- | --- | --- |"]
    lines += [f"| {md_cell(item['kind'])} | `{md_cell(item['path'])}` | `{md_cell(item['source'])}` |" for item in data["route_hints"]]
    if not data["route_hints"]:
        lines.append("| None found | | |")
    if data["route_hints_truncated"]:
        lines += ["", f"_Truncated at {MAX_ROUTE_HINTS_PER_KIND} hints per kind for: {', '.join(data['route_hints_truncated'])}._"]
    lines += ["", "## Limitations", ""]
    lines += [f"- {md_cell(item)}" for item in data["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, help="Directory you are authorized to inspect")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="Optional report output file")
    args = parser.parse_args(argv)
    root = args.repository.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        parser.error(f"repository must be an existing directory: {root}")
    report = analyze(root)
    content = json.dumps(report, indent=2) + "\n" if args.format == "json" else to_markdown(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(f"Wrote report to {args.output}")
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
