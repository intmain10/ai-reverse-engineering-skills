# Reverse Engineering Methodology

## Source-code analysis

1. Inventory manifests: package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, pom.xml.
2. Locate startup files, routers, feature modules and test fixtures.
3. Record dependencies as *declared*, and identify code that actually imports them before making usage claims.
4. Trace top three user journeys through source references (include path and line).
5. Identify configuration and infra clues without opening or reporting secret files.
6. Draft a component/data-flow diagram and list any unresolved edges.

Use `scripts/inspect_repo.py` for a **first-pass static survey**. It recognizes only a small set of common framework and route conventions, so manually check results. It never installs packages, runs the analyzed repo, or uses network access.

## UI/screenshot analysis

- Observe: viewport, layout grid, visible controls, type sizes, palettes, modal/menu states and navigation.
- Record responsive differences only when multiple viewports are available.
- Distinguish visible state from behavior not yet observed.
- Specify accessible controls (labels, focus states, errors), and prioritize functional equivalence over pixel cloning.
- Do not copy trademarks, protected assets, gated resources, or private content without authorization.

## API analysis

- Prefer OpenAPI/GraphQL specs, API SDKs, approved traffic captures and contract tests.
- Document verbs, paths, authentication, request/response schemas, error states, retries and rate limits.
- Identify PII and sensitive fields for redaction.
- Do not guess API paths based solely on UI screenshots.
- Avoid unapproved penetration testing, brute-force, enumeration, or access-control bypass.

## Deliverable quality rubric

- Evidence quality: direct references supporting assertions.
- Coverage: complete journey from trigger through result when inputs permit.
- Uncertainty: explicit unknowns, not hand-waving.
- Reusability: another engineer can implement and validate the proposed design.
- Safety: no revealed secrets, unauthorized scraping, or unlicensed source duplication.
