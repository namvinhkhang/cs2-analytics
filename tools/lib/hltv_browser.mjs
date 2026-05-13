// Shared Puppeteer + stealth + Cloudflare-clearance helpers for HLTV scrapers.
// Keeping this in one place lets fetch_hltv_mapstats.mjs and fetch_hltv_matches.mjs
// share the same launch options, warmup nav, and challenge-handling logic.
import { mkdir } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";
import { pathToFileURL } from "node:url";

export const DEFAULT_DELAY_MS = 5000;
export const DEFAULT_NAV_TIMEOUT_MS = 60000;
export const DEFAULT_CHALLENGE_TIMEOUT_MS = 120000;
export const DEFAULT_USER_DATA_DIR = "data/hltv_cache/puppeteer-profile";
export const STOP_STATUSES = new Set([403, 429]);

// HLTV serves a soft 500: HTTP 200 with an `error-body` page. Detect by class
// or by the `.error-500` block rendered inside it.
export const ERROR_PAGE_PROBE =
  "document.body && (document.body.classList.contains('error-body') || !!document.querySelector('.error-500'))";

export const CLOUDFLARE_MARKERS = [
  "Sorry, you have been blocked",
  "Checking your browser before accessing",
  "Enable JavaScript and cookies to continue",
  "Just a moment...",
  "cf-challenge",
];

export const DESKTOP_USER_AGENT =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export function statusCode(error) {
  return error?.statusCode ?? error?.response?.statusCode ?? error?.code;
}

export function looksLikeChallenge(html) {
  return CLOUDFLARE_MARKERS.some((marker) => html.includes(marker));
}

// Resolve a module specifier from env: a bare name OR a filesystem path we
// must convert to a file:// URL so dynamic import works on Linux.
function moduleSpecifier(envValue, fallback) {
  const value = envValue ?? fallback;
  if (!value) return null;
  if (!value.includes("/") && !value.includes("\\")) return value;
  return pathToFileURL(isAbsolute(value) ? value : resolve(value)).href;
}

async function loadStealthPuppeteer() {
  const puppeteerSpecifier = moduleSpecifier(
    process.env.PUPPETEER_MODULE_PATH,
    "puppeteer-extra",
  );
  const stealthSpecifier = moduleSpecifier(
    process.env.STEALTH_MODULE_PATH,
    "puppeteer-extra-plugin-stealth",
  );
  const puppeteerModule = await import(puppeteerSpecifier);
  const stealthModule = await import(stealthSpecifier);
  const puppeteer = puppeteerModule.default ?? puppeteerModule;
  const stealth = stealthModule.default ?? stealthModule;
  const plugin = stealth();
  // `user-agent-override` rewrites the UA mid-navigation, which Chromium
  // sometimes treats as a request change and aborts with net::ERR_ABORTED.
  plugin.enabledEvasions.delete("user-agent-override");
  puppeteer.use(plugin);
  return puppeteer;
}

export async function createBrowser({
  headless,
  navTimeoutMs,
  challengeTimeoutMs,
  userDataDir,
  chromePath,
}) {
  const puppeteer = await loadStealthPuppeteer();

  // When CHROME_REMOTE_URL is set we attach to a long-lived Chrome process via
  // CDP instead of letting puppeteer spawn its own. This is required when
  // Cloudflare has issued cf_clearance bound to the real Chrome fingerprint —
  // a fresh puppeteer-launched Chrome triggers a re-challenge even with the
  // cookie present, because subtle launch flags change the fingerprint.
  const remoteUrl = process.env.CHROME_REMOTE_URL;
  let browser;
  let page;

  if (remoteUrl) {
    browser = await puppeteer.connect({ browserURL: remoteUrl, defaultViewport: null });
    page = (await browser.pages())[0] ?? (await browser.newPage());
    // Don't override UA/viewport — must match the real Chrome that minted cf_clearance.
  } else {
    const resolvedProfile = isAbsolute(userDataDir) ? userDataDir : resolve(userDataDir);
    await mkdir(resolvedProfile, { recursive: true });

    const launchOptions = {
      headless,
      userDataDir: resolvedProfile,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--lang=en-US,en",
      ],
    };
    if (chromePath) launchOptions.executablePath = chromePath;

    browser = await puppeteer.launch(launchOptions);
    page = (await browser.pages())[0] ?? (await browser.newPage());
    await page.setUserAgent(DESKTOP_USER_AGENT);
    await page.setViewport({ width: 1366, height: 768 });
    await page.setExtraHTTPHeaders({ "accept-language": "en-US,en;q=0.9" });
  }

  // Visit the homepage first so cf_clearance binds to the apex domain before
  // we deep-link into /stats/... or /matches/...
  try {
    await page.goto("https://www.hltv.org/", {
      waitUntil: "domcontentloaded",
      timeout: navTimeoutMs,
    });
    await page
      .waitForFunction(
        (markers) => !markers.some((m) => document.documentElement.innerHTML.includes(m)),
        { timeout: challengeTimeoutMs },
        CLOUDFLARE_MARKERS,
      )
      .catch(() => {
        console.error(
          "Cloudflare challenge still present on homepage — solve it in the open window, then leave it running.",
        );
      });
  } catch (error) {
    console.error(`warmup navigation warning: ${error?.message ?? error}`);
  }

  return { browser, page };
}

// Navigate and wait for either the expected content selector or HLTV's soft
// 500 page. Throws with `statusCode`/`hltvErrorPage` set on known failures.
export async function gotoHltvPage(page, url, opts) {
  const { navTimeoutMs, challengeTimeoutMs, contentSelector } = opts;

  // HLTV often redirects /matches/{id}/- or /mapstatsid/{id}/- → slug URL.
  // Puppeteer surfaces that redirect as net::ERR_ABORTED on the original goto
  // promise even though the redirect target loads fine.
  try {
    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: navTimeoutMs,
      referer: "https://www.hltv.org/",
    });
  } catch (error) {
    if (!(error?.message ?? "").includes("net::ERR_ABORTED")) throw error;
    await page
      .waitForNavigation({ waitUntil: "domcontentloaded", timeout: navTimeoutMs })
      .catch(() => {});
  }

  // Race the content selector against HLTV's HTML 500 page. Without this,
  // an error page would block for the full challengeTimeoutMs before failing.
  const outcome = await Promise.race([
    page
      .waitForSelector(contentSelector, { timeout: challengeTimeoutMs })
      .then(() => "content")
      .catch(() => null),
    page
      .waitForFunction(ERROR_PAGE_PROBE, { timeout: challengeTimeoutMs })
      .then(() => "error")
      .catch(() => null),
  ]);

  if (outcome === "error") {
    const err = new Error(`HLTV rendered an error page for ${url}`);
    err.statusCode = 500;
    err.hltvErrorPage = true;
    throw err;
  }

  const html = await page.content();
  if (looksLikeChallenge(html)) {
    await page
      .waitForFunction(
        (markers) => !markers.some((m) => document.documentElement.innerHTML.includes(m)),
        { timeout: challengeTimeoutMs },
        CLOUDFLARE_MARKERS,
      )
      .catch(() => {});
    await page.waitForSelector(contentSelector, { timeout: challengeTimeoutMs }).catch(() => {});
    const html2 = await page.content();
    if (looksLikeChallenge(html2)) {
      const err = new Error(`Cloudflare challenge did not clear for ${url}`);
      err.statusCode = 403;
      throw err;
    }
  }
}
