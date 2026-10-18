#!/usr/bin/env python3
"""Create an evidence-labeled website UI report from capture_site.mjs output.

Python 3.9+; standard library only. This is NOT a backend/framework audit.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re


def clean(value, width: int = 100) -> str:
    """Make untrusted page-derived strings inert and compact inside Markdown."""
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"[<>\\`|\[\]]", "", text)
    return re.sub(r"\s+", " ", text)[:width]


def as_dict(value) -> dict:
    """Treat anything that is not a JSON object as empty (captures are untrusted input)."""
    return value if isinstance(value, dict) else {}


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def safe_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def mermaid_label(value, width: int = 45) -> str:
    """Quote-safe Mermaid node label: a stray quote would otherwise end the label early."""
    return clean(value, width).replace('"', "#quot;")


def to_mermaid_id(path: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_]", "_", path)
    return "page_" + (candidate.strip("_") or "home")[:50]


def unique_mermaid_ids(paths: list) -> dict:
    """Map each path to a distinct node id; '/a-b' and '/a_b' would otherwise collide."""
    ids, used = {}, set()
    for path in paths:
        if path in ids:
            continue
        base = candidate = to_mermaid_id(path)
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        ids[path] = candidate
        used.add(candidate)
    return ids


def summarize(data: dict) -> str:
    if not isinstance(data, dict):
        raise ValueError("Capture must be a JSON object")
    if data.get("schema_version") != 2:
        raise ValueError("Unsupported capture schema. Expected schema_version = 2")
    pages = data.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Capture must contain a pages array")
    pages = [page for page in pages if isinstance(page, dict)]
    lines = [
        "# Website Reverse Engineering v2 | UI Reconnaissance",
        "",
        "> This is **observed UI evidence**, not proof of hidden app code, frameworks, databases or API behavior.",
        "",
        "## Scope and capture provenance", "",
        f"- Target: `{clean(data.get('target'), 160)}`",
        f"- Captured (UTC): `{clean(data.get('captured_at'), 50)}`",
        f"- Pages analyzed: **{len(pages)}**", "",
        "## Pages and screenshots", "",
        "| Route | Desktop | Mobile |",
        "| --- | --- | --- |",
    ]
    seen_paths = []
    for page in pages:
        path = str(page.get("path", "/"))
        seen_paths.append(path)
        viewports = as_dict(page.get("viewports"))
        desktop = clean(as_dict(viewports.get("desktop")).get("screenshot", "Not captured"), 140)
        mobile = clean(as_dict(viewports.get("mobile")).get("screenshot", "Not captured"), 140)
        lines.append(f"| `{clean(path)}` | `{desktop}` | `{mobile}` |")
    lines += ["", "## Navigation graph (observed same-origin links)", "", "```mermaid", "flowchart LR"]
    route_ids = unique_mermaid_ids(seen_paths)
    for route, node_id in route_ids.items():
        lines.append(f'    {node_id}["{mermaid_label(route)}"]')
    edges = set()
    for page in pages:
        origin = str(page.get("path", "/"))
        desktop = as_dict(as_dict(page.get("viewports")).get("desktop"))
        for linked in as_list(desktop.get("links")):
            if isinstance(linked, str) and linked in route_ids and linked != origin:
                edges.add((origin, linked))
    for origin, target in sorted(edges):
        lines.append(f"    {route_ids[origin]} --> {route_ids[target]}")
    if not seen_paths:
        lines.append('    none["No captured pages"]')
    lines += ["```", "", "## Candidate component inventory", "",
              "| Route | Viewport | Observed landmarks | Controls | Key headings |",
              "| --- | --- | --- | ---: | --- |"]
    all_tokens = {}
    for page in pages:
        route = clean(page.get("path", "/"))
        for viewport, item in as_dict(page.get("viewports")).items():
            item = as_dict(item)
            landmarks = Counter(clean(x.get("role") or x.get("tag", "?"), 30)
                                for x in as_list(item.get("landmarks")) if isinstance(x, dict))
            landmark_text = ", ".join(f"{kind} ×{count}" for kind, count in landmarks.most_common(8))
            headings = "; ".join(clean(h.get("text", ""), 60)
                                 for h in as_list(item.get("headings"))[:3] if isinstance(h, dict))
            lines.append(f"| `{route}` | {clean(viewport)} | {landmark_text or 'None recorded'} | {len(as_list(item.get('controls')))} | {headings or 'None recorded'} |")
            for token_type in ("text_colors", "backgrounds", "fonts", "font_sizes", "radii"):
                for token in as_list(as_dict(item.get("tokens")).get(token_type))[:12]:
                    if not isinstance(token, dict):
                        continue
                    key = (token_type, clean(token.get("value"), 90))
                    all_tokens[key] = all_tokens.get(key, 0) + safe_int(token.get("count"))
    lines += ["", "## Computed-style samples (not verified design tokens)", "",
              "| Property | Candidate value | Sample occurrences | Confidence |",
              "| --- | --- | ---: | --- |"]
    for (category, value), count in sorted(all_tokens.items(), key=lambda x: -x[1])[:25]:
        lines.append(f"| {clean(category)} | `{value}` | {count} | Sampled / observed |")
    if not all_tokens:
        lines.append("| None recorded | | 0 | Unknown |")
    lines += ["", "## Desktop/mobile comparison and component hypotheses", "",
              "Review the referenced screenshots manually to establish layout changes, grid counts, hero placement, heading scale, mobile navigation, and responsive behavior.",
              "**Do not assert exact CSS breakpoints or component reuse from two viewport screenshots alone.**", "",
              "## Suggested original rebuild roadmap", "",
              "1. Design an original page shell with accessible header, navigation, main and footer.",
              "2. Recreate the observed page structure using original assets and licensed copy.",
              "3. Implement responsive grids and type scales; visually compare both screenshot sizes.",
              "4. Rebuild verified public interactions as accessible stateful components.",
              "5. Validate routes, keyboard flows, contrast, responsive snapshots and error states.", "",
              "## Evidence, risks and unknowns", "",
              "| Finding | Evidence | Confidence |",
              "| --- | --- | --- |",
              "| Page structure and visible controls | capture.json, pages[].viewports[].landmarks/controls | Observed sample |",
              "| Link graph | capture.json, pages[].viewports.desktop.links | Observed sample |",
              "| Layout details | screenshots, review required | Unverified pending visual review |",
              "| Backend, APIs, state management, hosting | No relevant source inspected | Unknown |",
              "| True framework or CSS breakpoints | UI evidence alone is insufficient | Unknown |", ""]
    for warning in as_list(data.get("warnings")):
        lines.append(f"- Capture note: {clean(warning, 180)}")
    lines += ["", "## Privacy and copyright", "",
              "Inspect and redact screenshots before sharing them. Do not copy restricted brand assets, protected text, or confidential site data without permission.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Path to capture.json produced by capture_site.mjs")
    parser.add_argument("--output", type=Path, help="Markdown report path (default: stdout)")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.capture.read_text(encoding="utf-8"))
        report = summarize(data)
    except (OSError, ValueError) as err:
        parser.exit(2, f"Cannot analyze {args.capture}: {err}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
