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


def to_mermaid_id(path: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_]", "_", path)
    return "page_" + (candidate.strip("_") or "home")[:50]


def summarize(data: dict) -> str:
    if data.get("schema_version") != 2:
        raise ValueError("Unsupported capture schema. Expected schema_version = 2")
    pages = data.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Capture must contain a pages array")
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
        viewports = page.get("viewports") or {}
        desktop = clean((viewports.get("desktop") or {}).get("screenshot", "Not captured"), 140)
        mobile = clean((viewports.get("mobile") or {}).get("screenshot", "Not captured"), 140)
        lines.append(f"| `{clean(path)}` | `{desktop}` | `{mobile}` |")
    lines += ["", "## Navigation graph (observed same-origin links)", "", "```mermaid", "flowchart LR"]
    route_ids = {path: to_mermaid_id(path) for path in seen_paths}
    for route in seen_paths:
        lines.append(f'    {route_ids[route]}["{clean(route, 45)}"]')
    edges = set()
    for page in pages:
        origin = page.get("path")
        desktop = (page.get("viewports") or {}).get("desktop") or {}
        for linked in desktop.get("links") or []:
            if linked in route_ids and linked != origin:
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
        for viewport, item in (page.get("viewports") or {}).items():
            landmarks = Counter(clean(x.get("role") or x.get("tag", "?"), 30)
                                for x in (item.get("landmarks") or []))
            landmark_text = ", ".join(f"{kind} ×{count}" for kind, count in landmarks.most_common(8))
            headings = "; ".join(clean(h.get("text", ""), 60) for h in (item.get("headings") or [])[:3])
            lines.append(f"| `{route}` | {clean(viewport)} | {landmark_text or 'None recorded'} | {len(item.get('controls') or [])} | {headings or 'None recorded'} |")
            for token_type in ("text_colors", "backgrounds", "fonts", "font_sizes", "radii"):
                for token in (item.get("tokens") or {}).get(token_type, [])[:12]:
                    key = (token_type, clean(token.get("value"), 90))
                    all_tokens[key] = all_tokens.get(key, 0) + int(token.get("count", 0))
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
    for warning in data.get("warnings") or []:
        lines.append(f"- Capture note: {clean(warning, 180)}")
    lines += ["", "## Privacy and copyright", "",
              "Inspect and redact screenshots before sharing them. Do not copy restricted brand assets, protected text, or confidential site data without permission.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Path to capture.json produced by capture_site.mjs")
    parser.add_argument("--output", type=Path, help="Markdown report path (default: stdout)")
    args = parser.parse_args(argv)
    data = json.loads(args.capture.read_text(encoding="utf-8"))
    report = summarize(data)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
