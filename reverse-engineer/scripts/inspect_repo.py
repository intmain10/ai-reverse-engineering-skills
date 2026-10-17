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
SCAN_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rb", ".php"}
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
}
MAX_READ_BYTES = 200_000
MAX_FILES = 15_000
MAX_ROUTE_HINTS = 60
# Capture path-only route hints; deliberately exclude query strings and headers.
ROUTE_PATTERNS = (
    ("http-handler", re.compile(r"""(?:app|router|server|api)\.(?:get|post|put|delete|patch|options|head|all)\s*\(\s*['"](/[-a-zA-Z0-9_/{}:.]*)['"]""")),
    ("python-route", re.compile(r"""@(?:app|router|bp|blueprint)\.(?:route|get|post|put|delete|patch)\s*\(\s*['"](/[-a-zA-Z0-9_/{}:.]*)['"]""")),
    ("outbound-request", re.compile(r"""\b(?:fetch|axios\.(?:get|post|put|patch|delete))\s*\(\s*['"](/[-a-zA-Z0-9_/{}:.]*)['"]""")),
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
            for framework in ("django", "flask", "fastapi", "starlette"):
                if re.search(r"""['"]""" + framework + r"""(?:\[[^]]+\])?(?:[=<> ]|['"])""", raw, re.I):
                    dependencies.add(framework)
        elif path.name == "pubspec.yaml":
            if re.search(r"(?m)^\s*flutter\s*:", raw):
                dependencies.add("flutter")
    return names, sorted(dependencies)


def analyze(root: Path) -> dict:
    files, omitted = get_files(root)
    counts = Counter(EXT_TO_LANG.get(p.suffix.lower(), "Other") for p in files)
    manifests, dependencies = detect_manifests(root, files)
    frameworks = sorted({name for package, name in FRAMEWORK_HINTS.items() if package in dependencies})
    routes = []
    route_seen = set()
    interesting = []
    for p in files:
        rel = safe_rel(p, root)
        if p.name.lower() in {"app.tsx", "app.jsx", "main.ts", "main.tsx", "main.py", "server.js", "server.ts", "manage.py", "app.py", "index.ts", "index.js"}:
            interesting.append(rel)
        if p.suffix.lower() not in SCAN_EXTENSIONS:
            continue
        code = read_small_file(p)
        if code is None:
            continue
        if len(routes) < MAX_ROUTE_HINTS:
            for lineno, line in enumerate(code.splitlines(), 1):
                for kind, pattern in ROUTE_PATTERNS:
                    for match in pattern.finditer(line):
                        path_value = match.group(1)
                        key = (rel, lineno, kind, path_value)
                        if key not in route_seen:
                            routes.append({"kind": kind, "path": path_value, "source": f"{rel}:{lineno}"})
                            route_seen.add(key)
                        if len(routes) >= MAX_ROUTE_HINTS:
                            break
                    if len(routes) >= MAX_ROUTE_HINTS:
                        break
                if len(routes) >= MAX_ROUTE_HINTS:
                    break
    return {
        "scanned_root": str(root), "file_count": len(files), "omitted_files": omitted,
        "languages_by_file_count": dict(sorted(counts.items(), key=lambda x: (-x[1], x[0]))),
        "manifests": sorted(manifests), "declared_dependencies": dependencies,
        "framework_hints": frameworks, "possible_entry_points": sorted(interesting)[:50],
        "route_hints": routes,
        "limitations": [
            "Read-only static inspection; target application code was never executed.",
            "Frameworks are inferred from dependency declarations, not confirmed runtime usage.",
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
        f"- Framework hints: {', '.join(data['framework_hints']) or 'none detected'}", "",
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
