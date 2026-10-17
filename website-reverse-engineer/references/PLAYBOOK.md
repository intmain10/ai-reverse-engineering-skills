# Website Reverse Engineering Playbook

## Prerequisites and ethics

Use only websites you are permitted to inspect; prefer your own properties or sites with explicit permission. Browser automation does not grant a license to copy site trademarks, media, or protected text. Observe publicly accessible pages; no credential injection, automated form submissions, CAPTCHA bypass, rate limit evasion, hidden endpoint probing, or aggressive crawling.

## Investigation stages

### 1. Establish evidence

Capture desktop and mobile at the same URL and record viewport, UTC timestamp, and screenshot filename. Use `--crawl` only when multi-page browsing is explicitly authorized; the browser script restricts to same-origin, checks robots.txt, and caps pages and delays. Do not use the tool for authenticated pages or forms containing PII.

### 2. Page IA (information architecture)

- Classify each page by purpose (landing, listing, detail, form, help).
- Group repeated links and nav sections.
- Draw the sitemap as a Mermaid `flowchart LR` with observed edges only.
- Extract hints for header, nav, hero, forms, cards, accordions, footer, and related layout containers.

### 3. Desktop/mobile comparison

Compare header collapse, column counts, typography, alignment, component ordering, navigation treatment and form widths. A pair of screenshots does not establish an exact CSS media-query breakpoint: mark breakpoints as inferred.

### 4. Tokens, UI components and accessibility

Use computed styles in the capture as samples, not definitive design system tokens. Visually inspect images for typography hierarchy, spacing grid, button variants, hover/focus clues, color contrasts, and semantics. Recommend keyboard access and proper headings without claiming that a static screenshot proves those behaviors.

### 5. Interactions

Do not autonomously submit forms, authenticate, transact, or click destructive controls. With authorization, a human or agent using a safe browser can inspect benign accordions, tabs, menus and accordions; record initial/triggered states separately.

### 6. Architecture and rebuild

Do not infer Next.js, React, database, API integrations, security or checkout implementations solely from appearances. If actual source files or permitted developer tooling are provided, verify claims with direct evidence. Propose independently authored components and routing, with clear assumptions and acceptance criteria.

## Quality rubric

1. Coverage: named pages, both breakpoints, links and basic controls.
2. Fidelity: screenshot-to-component mapping and explicit measured versus inferred values.
3. Evidence: each claim linked to a file/URL and viewport or line in supplied code.
4. Access and privacy: no unauthorised exploration or sensitive capture.
5. Deliverability: clear original build plan and smoke tests.

## Caveats

Capture runs may encounter dynamic animations, consent overlays, lazy-loading and personalization. Tools cannot reconstruct unseen states reliably. The default crawler does not interact with buttons or forms. Robots enforcement uses the robots-parser package and a named user agent, and the site may also impose additional terms or throttling. Do not try to circumvent restrictions.
