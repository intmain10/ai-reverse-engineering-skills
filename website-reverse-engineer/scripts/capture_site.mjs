#!/usr/bin/env node
/**
 * Read-only UI reconnaissance of authorized unauthenticated public pages.
 * Captures sanitized component/style metadata and screenshots; does not click,
 * fill, submit, authenticate, read cookies, or store network requests.
 * Requires: npm install && npx playwright install chromium
 */
import { chromium } from 'playwright';
import robotsParser from 'robots-parser';
import fs from 'node:fs/promises';
import path from 'node:path';

const USER_AGENT = 'WebsiteReverseEngineerBot';
const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};
const UNSAFE_PATH = /\/(?:login|log-in|signin|sign-in|signup|sign-up|logout|account|admin|dashboard|checkout|payment|billing|session|auth)(?:\/|$)/i;

function usage() {
  return `Usage: node scripts/capture_site.mjs --url https://example.com [--out ./reports/site] [--crawl] [--max-pages 5] [--delay-ms 1200]

By default only the exact starting public page is inspected.
--crawl opts into following visible same-origin links, up to --max-pages (1-10).
The script respects robots.txt; a blocked/unavailable robots policy stops capture.
Use ONLY on websites you have permission to inspect.`;
}

function parseArgs(argv) {
  const args = { out: './reports/site', crawl: false, maxPages: 5, delayMs: 1200 };
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (key === '--help' || key === '-h') return { help: true };
    if (key === '--crawl') { args.crawl = true; continue; }
    if (!['--url', '--out', '--max-pages', '--delay-ms'].includes(key)) throw new Error(`Unknown option: ${key}`);
    if (i + 1 >= argv.length) throw new Error(`Missing value for ${key}`);
    const value = argv[++i];
    if (key === '--url') args.url = value;
    if (key === '--out') args.out = value;
    if (key === '--max-pages') args.maxPages = Number(value);
    if (key === '--delay-ms') args.delayMs = Number(value);
  }
  if (!args.url) throw new Error('Provide --url');
  if (!Number.isInteger(args.maxPages) || args.maxPages < 1 || args.maxPages > 10) throw new Error('--max-pages must be an integer from 1 to 10');
  if (!Number.isInteger(args.delayMs) || args.delayMs < 800 || args.delayMs > 30_000) throw new Error('--delay-ms must be between 800 and 30000');
  const url = new URL(args.url);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Only credential-free http(s) URLs are allowed');
  if (UNSAFE_PATH.test(url.pathname)) throw new Error('Refusing account, authentication, payment or other sensitive paths');
  if (url.search) throw new Error('Remove query parameters before capturing (they may contain sensitive tokens)');
  url.hash = '';
  args.url = url.toString();
  return args;
}

function canonical(href, base) {
  try {
    const url = new URL(href, base);
    const expected = new URL(base);
    if (!['http:', 'https:'].includes(url.protocol) || url.origin !== expected.origin) return null;
    if (url.username || url.password || url.search || UNSAFE_PATH.test(url.pathname)) return null;
    if (/\.(?:png|jpe?g|gif|svg|webp|pdf|zip|js|css|xml|json|mp4|mp3)$/i.test(url.pathname)) return null;
    url.hash = '';
    return url.toString();
  } catch { return null; }
}

function fileSlug(url) {
  const pathname = new URL(url).pathname;
  const raw = pathname === '/' ? 'home' : pathname.replace(/^\/|\/$/g, '').replace(/[^a-zA-Z0-9_-]+/g, '-');
  return (raw || 'page').slice(0, 70);
}

function summarizePage() {
  const compact = value => (value || '').replace(/\s+/g, ' ').trim().slice(0, 90);
  const visible = el => {
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return rect.width >= 1 && rect.height >= 1 && cs.display !== 'none' && cs.visibility !== 'hidden';
  };
  const top = (array, limit = 12) => {
    const map = new Map();
    for (const value of array) {
      if (!value || ['transparent', 'rgba(0, 0, 0, 0)', 'none'].includes(value)) continue;
      map.set(value, (map.get(value) || 0) + 1);
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit)
      .map(([value, count]) => ({ value, count }));
  };
  const headings = [...document.querySelectorAll('h1,h2,h3')].filter(visible).slice(0, 35)
    .map(el => ({ level: el.tagName.toLowerCase(), text: compact(el.innerText) }));
  const landmarks = [...document.querySelectorAll('header,nav,main,footer,aside,section,article,form,[role="dialog"]')]
    .filter(visible).slice(0, 60).map(el => ({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      label: compact(el.getAttribute('aria-label')),
      classes: [...el.classList].slice(0, 3).map(c => c.slice(0, 60)),
    }));
  const controls = [...document.querySelectorAll('a,button,input,textarea,select,[role="button"],[role="tab"]')]
    .filter(visible).slice(0, 100).map(el => ({
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      type: el.getAttribute('type') || '',
      label: compact(el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || (el.matches('a,button,[role="button"],[role="tab"]') ? el.innerText : '')),
    }));
  const links = [...new Set([...document.querySelectorAll('a[href]')].filter(visible)
    .map(a => a.href))].slice(0, 120);
  const samples = [...document.querySelectorAll('body,header,nav,main,footer,section,article,div,button,a,h1,h2,h3,p')]
    .filter(visible).slice(0, 350).map(el => {
      const cs = getComputedStyle(el);
      return {
        color: cs.color, background: cs.backgroundColor, font: cs.fontFamily,
        size: cs.fontSize, radius: cs.borderRadius,
      };
    });
  const styles = getComputedStyle(document.documentElement);
  const cssVariables = [];
  for (let i = 0; i < styles.length && cssVariables.length < 35; i++) {
    const prop = styles.item(i);
    if (prop.startsWith('--') && /(color|primary|secondary|font|space|radius|gap)/i.test(prop)) {
      const value = compact(styles.getPropertyValue(prop));
      if (value && value.length <= 90) cssVariables.push({ name: prop, value });
    }
  }
  return {
    title: compact(document.title),
    headings, landmarks, controls, links,
    tokens: {
      text_colors: top(samples.map(s => s.color)),
      backgrounds: top(samples.map(s => s.background)),
      fonts: top(samples.map(s => s.font)),
      font_sizes: top(samples.map(s => s.size)),
      radii: top(samples.map(s => s.radius)),
      css_variables: cssVariables,
    },
    counts: { headings: headings.length, landmarks: landmarks.length, controls: controls.length },
  };
}

async function main() {
  let args;
  try { args = parseArgs(process.argv.slice(2)); }
  catch (err) { console.error(err.message); console.error(usage()); process.exitCode = 2; return; }
  if (args.help) { console.log(usage()); return; }
  const browser = await chromium.launch({ headless: true });
  try {
    const out = path.resolve(args.out);
    await fs.mkdir(path.join(out, 'screenshots'), { recursive: true });
    const robotsURL = new URL('/robots.txt', args.url).toString();
    const request = await browser.newContext({ serviceWorkers: 'block' });
    let robots;
    try {
      const response = await request.request.get(robotsURL, { timeout: 12_000, maxRedirects: 0 });
      if (response.status() === 404 || response.status() === 410) {
        robots = { isAllowed: () => true };
      } else {
        if (!response.ok()) throw new Error(`robots.txt HTTP ${response.status()}`);
        const text = await response.text();
        robots = robotsParser(robotsURL, text);
      }
    } finally { await request.close(); }

    const queue = [args.url], seen = new Set();
    const report = {
      schema_version: 2, target: args.url, captured_at: new Date().toISOString(),
      settings: { crawl: args.crawl, max_pages: args.crawl ? args.maxPages : 1, viewports: VIEWPORTS },
      pages: [], warnings: [
        'UI and computed styles only: no source-code, backend, API or accessibility audit.',
        'Screenshots may capture visible personal data; inspect and redact before sharing.'
      ],
    };
    while (queue.length && report.pages.length < (args.crawl ? args.maxPages : 1)) {
      const url = queue.shift();
      if (seen.has(url)) continue;
      seen.add(url);
      if (robots.isAllowed(url, USER_AGENT) === false) {
        report.warnings.push(`robots.txt disallows ${new URL(url).pathname}`);
        continue;
      }
      const entry = { path: new URL(url).pathname, viewports: {} };
      for (const [name, viewport] of Object.entries(VIEWPORTS)) {
        const context = await browser.newContext({ viewport, deviceScaleFactor: 1, reducedMotion: 'reduce', serviceWorkers: 'block' });
        const page = await context.newPage();
        try {
          const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20_000 });
          await page.waitForTimeout(500);
          const finalUrl = page.url();
          if (!canonical(finalUrl, args.url) || robots.isAllowed(finalUrl, USER_AGENT) === false) {
            report.warnings.push(`Navigation escaped approved page scope: ${new URL(url).pathname}`);
            continue;
          }
          const snapshot = await page.evaluate(summarizePage);
          snapshot.url_path = new URL(finalUrl).pathname;
          snapshot.http_status = response?.status() ?? null;
          snapshot.viewport = viewport;
          const imageFile = `screenshots/${fileSlug(url)}-${name}.png`;
          await page.screenshot({ path: path.join(out, imageFile), fullPage: true, animations: 'disabled', timeout: 20_000 });
          snapshot.screenshot = imageFile;
          // Store same-origin *paths* only, never full URL query/fragment strings.
          snapshot.links = [...new Set(snapshot.links.map(x => canonical(x, args.url)).filter(Boolean))]
            .map(x => new URL(x).pathname).slice(0, 90);
          entry.viewports[name] = snapshot;
          if (args.crawl && name === 'desktop') {
            for (const route of snapshot.links) {
              const normalized = canonical(route, args.url);
              if (normalized && !seen.has(normalized) && !queue.includes(normalized)) queue.push(normalized);
            }
          }
        } catch (err) {
          report.warnings.push(`Capture of ${entry.path} (${name}) failed: ${String(err.message).slice(0, 150)}`);
        } finally { await context.close(); }
      }
      if (Object.keys(entry.viewports).length) report.pages.push(entry);
      if (queue.length && args.crawl) await new Promise(resolve => setTimeout(resolve, args.delayMs));
    }
    await fs.writeFile(path.join(out, 'capture.json'), JSON.stringify(report, null, 2) + '\n');
    console.log(`Captured ${report.pages.length} page(s) to ${out}`);
    if (!report.pages.length) { console.error('No pages captured; inspect warnings in capture.json'); process.exitCode = 1; }
  } finally { await browser.close(); }
}

main().catch(err => { console.error(`Capture stopped: ${String(err.message).slice(0, 240)}`); process.exitCode = 1; });
