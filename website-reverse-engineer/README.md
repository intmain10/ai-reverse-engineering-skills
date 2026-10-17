# Website Reverse Engineer v2

A portable Agent Skill for analyzing **authorized, public-facing websites** and planning an original responsive rebuild.

## Features

- Desktop (1440×900) and mobile (390×844) full-page screenshots
- Visible page landmarks, controls, headings and safe same-origin link paths
- Samples of computed colors, fonts, font sizes, and radii
- Optional, limited same-origin crawl that respects robots.txt and skips sensitive routes
- Offline report builder with a Mermaid sitemap and evidence/uncertainty notes
- No login, form submission, cookies, authorization headers or request-body recording

## Installation

Requires Node.js 20+, Python 3.9+ and a browser download:

```bash
cd website-reverse-engineer
npm install
npx playwright install chromium
```

## Inspect one page (default)

```bash
node scripts/capture_site.mjs --url https://example.com --out ./reports/example
python3 scripts/analyze_capture.py ./reports/example/capture.json --output ./reports/example/REPORT.md
```

Only proceed on sites you are authorized to inspect. To crawl **up to three authorized public pages**, explicitly opt in:

```bash
node scripts/capture_site.mjs --url https://example.com --out ./reports/example --crawl --max-pages 3 --delay-ms 1500
```

## Test the report generator (no network needed)

```bash
python3 -m unittest discover -s tests -v
python3 scripts/analyze_capture.py examples/sample_capture.json
node --check scripts/capture_site.mjs
```

The sample fixture is synthetic. The report generator is tested without contacting any real website. Browser-based capture additionally requires Playwright/Chromium and a site the operator is permitted to inspect.

## Use as an AI Skill

Copy this folder into `.claude/skills/website-reverse-engineer/` or your compatible host's supported skills path, for example `.agents/skills/website-reverse-engineer/`.

Ask your agent:

> Use website-reverse-engineer to analyze my public website at https://example.com, compare desktop and mobile layouts, map visible components and navigation, and produce a clean-room rebuild plan.

## Known limits

Two screenshots cannot prove exact breakpoints, inaccessible UI states, source framework, APIs, or database structure. The capture is a **public UI survey**, not source decompilation or a security assessment. Review screenshots for potentially visible private information before sharing.

MIT licensed (see repository root).
