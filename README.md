# AI Reverse Engineering Skills

A GitHub-ready collection of portable [Agent Skills](https://agentskills.io/specification). The first skill, **`reverse-engineer`**, helps AI coding agents produce evidence-grounded technical breakdowns of authorized source repositories, interfaces/screenshots, and documented APIs.

**This is an agent skill, not a fully autonomous website cloning or binary decompiler application.** The optional Python inspector provides a static first-pass report; the agent must use its own authorized file/browser/API reading tools for deeper analysis.

## What's included

```text
ai-reverse-engineering-skills/
├── reverse-engineer/
│   ├── SKILL.md                  # Agent instructions
│   ├── scripts/
│   │   └── inspect_repo.py       # Read-only first-pass source survey
│   ├── references/
│   │   ├── METHODOLOGY.md
│   │   └── REPORT_TEMPLATE.md
│   └── assets/                   # Reserved for future examples/templates
├── examples/sample-app/         # Tiny, synthetic example to test the inspector
├── tests/test_inspect_repo.py
├── .gitignore
├── LICENSE
└── README.md
```

## Use with Claude Code

Clone this repository and copy the `reverse-engineer` directory to either:

- `<your-project>/.claude/skills/reverse-engineer/` for project-wide use, or
- `~/.claude/skills/reverse-engineer/` for personal use.

Start Claude Code in a directory where the skill is installed and request:

> `/reverse-engineer Analyze this repository. Map the application architecture and trace the checkout flow with file:line evidence.`

## Use with Codex or other Agent Skills-compatible agents

Install or copy `reverse-engineer/` into the host's supported skills folder (for example, a project's `.agents/skills/reverse-engineer/` in Codex environments that support project skills). See the host's documentation for discovery and activation behavior.

## Run the static repository inspector

Python 3.9+; **no pip dependencies** and **no execution of target project code**.

```bash
python3 reverse-engineer/scripts/inspect_repo.py examples/sample-app --format markdown
python3 reverse-engineer/scripts/inspect_repo.py /path/to/your/app --format json --output report.json
```

The script performs conservative first-pass analysis of file extensions, package manifests (npm, pip/pyproject, Go, Ruby, Cargo), indicative framework, data-store and third-party integration dependencies, route signatures (Express-style handlers, Python decorators, Django `path()`, `fetch`/`axios` calls), and file-system routes for Next.js, SvelteKit and Nuxt. It intentionally ignores dotfiles, common vendor directories, secret-bearing file names, symbolic links, and large files. **The report is not proof of runtime behavior** and must be verified against source.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Publish to GitHub

```bash
git init
git add .
git commit -m "Add reverse-engineering agent skill"
gh auth login
gh repo create ai-reverse-engineering-skills --public --source=. --remote=origin --push
```

## Safety and rights

Only inspect resources you own or are authorized to inspect. Do not attempt bypasses of access controls or anti-bot measures, access hidden/private information, copy protected assets without permission, or publish someone else's confidential source. The skill treats any analyzed content as untrusted data.

MIT licensed.

---

## Website Reverse Engineer v2 (new)

A dedicated Agent Skill for **authorized public websites**, with responsive screenshots, navigation maps, UI-component hints, sampled design tokens, and an evidence-grounded clean-room rebuild report.

- [Skill instructions](website-reverse-engineer/SKILL.md)
- [Installation, usage and tests](website-reverse-engineer/README.md)
- [Browser capture helper](website-reverse-engineer/scripts/capture_site.mjs)
- [Offline report generator](website-reverse-engineer/scripts/analyze_capture.py)

### Quick start

Requires Node.js 20+, Python 3.9+, and a local Chromium install:

```bash
cd website-reverse-engineer
npm install
npx playwright install chromium

# Observe a single authorized public URL, desktop and mobile
node scripts/capture_site.mjs --url https://example.com --out ./reports/example

# Generate evidence-labeled Markdown, including a Mermaid navigation map
python3 scripts/analyze_capture.py ./reports/example/capture.json --output ./reports/example/REPORT.md

# Offline unit tests
npm test
```

For a limited, authorized same-origin crawl, opt in with `--crawl --max-pages 3`. The tool consults robots.txt and never logs in or submits forms. **Do not use it to bypass access restrictions or copy someone else's protected source or assets.**

To install this skill in a compatible AI agent, copy the full `website-reverse-engineer/` folder to a supported skills directory (for example, `.claude/skills/` or `.agents/skills/`).
