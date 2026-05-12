#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { isAbsolute, resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const DEFAULT_DELAY_MS = 5000;
const DEFAULT_NAV_TIMEOUT_MS = 60000;
const DEFAULT_CHALLENGE_TIMEOUT_MS = 120000;
const DEFAULT_USER_DATA_DIR = "data/hltv_cache/puppeteer-profile";
const STOP_STATUSES = new Set([403, 429]);
const CONTENT_SELECTOR = ".match-info-box";
const CLOUDFLARE_MARKERS = [
  "Sorry, you have been blocked",
  "Checking your browser before accessing",
  "Enable JavaScript and cookies to continue",
  "Just a moment...",
  "cf-challenge",
];

function usage() {
  console.error(`
Usage:
  PUPPETEER_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra/dist/index.cjs.js \\
  STEALTH_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra-plugin-stealth/index.js \\
    node tools/fetch_hltv_mapstats.mjs --ids-file data/hltv_cache/mapstats_ids.txt --output-dir data/hltv_cache/map_stats

Options:
  --ids-file              Newline-delimited HLTV mapstats IDs (required).
  --output-dir            Directory for one JSON file per mapstats ID (required).
  --delay-ms              Delay between requests. Defaults to ${DEFAULT_DELAY_MS}.
  --headless              "true" or "false". Defaults to false so browser checks are visible.
  --nav-timeout-ms        Navigation timeout. Defaults to ${DEFAULT_NAV_TIMEOUT_MS}.
  --challenge-timeout-ms  How long to wait for the Cloudflare challenge to clear. Defaults to ${DEFAULT_CHALLENGE_TIMEOUT_MS}.
  --user-data-dir         Persistent Chrome profile dir (keeps cf_clearance cookie). Defaults to ${DEFAULT_USER_DATA_DIR}.
  --chrome-path           Absolute path to a real Chrome binary. Strongly recommended over bundled Chromium for Cloudflare.

Install once (outside committed project deps):
  npm install --prefix data/hltv_cache/node \\
    puppeteer puppeteer-extra puppeteer-extra-plugin-stealth

First run: leave --headless false, solve the Cloudflare check in the window if
it appears. The cf_clearance cookie is persisted under --user-data-dir, so
subsequent runs typically pass without interaction (and can use --headless true).
`);
}

function parseArgs(argv) {
  const args = new Map();
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      usage();
      process.exit(2);
    }
    args.set(key.slice(2), value);
  }
  const idsFile = args.get("ids-file");
  const outputDir = args.get("output-dir");
  if (!idsFile || !outputDir) {
    usage();
    process.exit(2);
  }
  return {
    idsFile,
    outputDir,
    delayMs: Number.parseInt(args.get("delay-ms") ?? String(DEFAULT_DELAY_MS), 10),
    headless: (args.get("headless") ?? "false").toLowerCase() === "true",
    navTimeoutMs: Number.parseInt(
      args.get("nav-timeout-ms") ?? String(DEFAULT_NAV_TIMEOUT_MS),
      10,
    ),
    challengeTimeoutMs: Number.parseInt(
      args.get("challenge-timeout-ms") ?? String(DEFAULT_CHALLENGE_TIMEOUT_MS),
      10,
    ),
    userDataDir: args.get("user-data-dir") ?? DEFAULT_USER_DATA_DIR,
    chromePath: args.get("chrome-path") ?? process.env.CHROME_PATH ?? null,
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

const DESKTOP_USER_AGENT =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

function looksLikeChallenge(html) {
  return CLOUDFLARE_MARKERS.some((marker) => html.includes(marker));
}

async function createBrowser({
  headless,
  navTimeoutMs,
  challengeTimeoutMs,
  userDataDir,
  chromePath,
}) {
  const puppeteer = await loadStealthPuppeteer();
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

  const browser = await puppeteer.launch(launchOptions);
  const page = (await browser.pages())[0] ?? (await browser.newPage());
  await page.setUserAgent(DESKTOP_USER_AGENT);
  await page.setViewport({ width: 1366, height: 768 });
  await page.setExtraHTTPHeaders({ "accept-language": "en-US,en;q=0.9" });

  // Visit the homepage first so cf_clearance binds to the apex domain before
  // we deep-link into /stats/...
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

async function gotoMapstats(page, url, navTimeoutMs, challengeTimeoutMs) {
  // HLTV redirects /mapstatsid/{id}/- → /mapstatsid/{id}/{slug}. Puppeteer
  // surfaces that redirect as net::ERR_ABORTED on the original goto promise
  // even though the redirect target loads fine.
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

  await page
    .waitForSelector(CONTENT_SELECTOR, { timeout: challengeTimeoutMs })
    .catch(() => {});

  const html = await page.content();
  if (looksLikeChallenge(html)) {
    await page
      .waitForFunction(
        (markers) => !markers.some((m) => document.documentElement.innerHTML.includes(m)),
        { timeout: challengeTimeoutMs },
        CLOUDFLARE_MARKERS,
      )
      .catch(() => {});
    await page.waitForSelector(CONTENT_SELECTOR, { timeout: challengeTimeoutMs }).catch(() => {});
    const html2 = await page.content();
    if (looksLikeChallenge(html2)) {
      const err = new Error(`Cloudflare challenge did not clear for ${url}`);
      err.statusCode = 403;
      throw err;
    }
  }
}

// Runs inside the page. Extracts the mapstats payload directly from the
// rendered DOM. Anything not present returns null rather than crashing.
async function extractMapstats(page, id) {
  return await page.evaluate((mapstatsId) => {
    const pickText = (sel, root = document) =>
      root.querySelector(sel)?.textContent?.trim() ?? null;
    const pickAttr = (sel, attr, root = document) =>
      root.querySelector(sel)?.getAttribute(attr) ?? null;
    const segments = (path) => (path ?? "").split("/").filter(Boolean);
    // Pull the first numeric path segment. Survives HLTV moving prefixes
    // around (e.g. /stats/teams/{id}/{slug} vs /team/{id}/{slug}).
    const firstNumericSegment = (path) => {
      for (const seg of segments(path)) {
        const n = Number(seg);
        if (Number.isInteger(n) && n > 0) return n;
      }
      return null;
    };

    const matchId = firstNumericSegment(pickAttr(".match-page-link", "href"));

    // Teams — anchor href is /stats/teams/{id}/{slug} on the mapstats page.
    const team1Href = pickAttr(".team-left a", "href");
    const team2Href = pickAttr(".team-right a", "href");
    const team1 = {
      id: firstNumericSegment(team1Href),
      name: pickAttr(".team-left .team-logo", "title") ?? pickText(".team-left .team-logo"),
    };
    const team2 = {
      id: firstNumericSegment(team2Href),
      name: pickAttr(".team-right .team-logo", "title") ?? pickText(".team-right .team-logo"),
    };

    const team1Total = Number(pickText(".team-left .bold")) || 0;
    const team2Total = Number(pickText(".team-right .bold")) || 0;

    // Halves: first .match-info-row .right contains "(16 : 14) ( 7 : 8 ) ( 9 : 6 )" style
    const halvesText =
      document.querySelector(".match-info-row .right")?.textContent?.trim() ?? "";
    const halfPairs = halvesText.match(/\d+\s*:\s*\d+/g) ?? [];
    // Drop the first pair (the total) if HLTV includes it; otherwise pairs are halves.
    const halfResults = (halfPairs.length > 2 ? halfPairs.slice(1) : halfPairs).map((pair) => {
      const [a, b] = pair.split(":").map((n) => Number(n.trim()));
      return { team1Rounds: a || 0, team2Rounds: b || 0 };
    });

    // Map name sits as one of .match-info-box's text-node children. Pick the
    // first non-empty trimmed text node that isn't a known label.
    const matchInfoBox = document.querySelector(".match-info-box");
    let map = null;
    if (matchInfoBox) {
      for (const node of matchInfoBox.childNodes) {
        if (node.nodeType !== 3) continue; // TEXT_NODE
        const text = node.textContent.trim();
        if (text && !/^[\s|·•-]+$/.test(text)) {
          map = text;
          break;
        }
      }
    }

    const date = Number(pickAttr(".match-info-box span[data-time-format]", "data-unix")) || null;

    const eventEl = document.querySelector(".match-info-box .text-ellipsis");
    const eventHref = eventEl?.getAttribute("href") ?? "";
    const eventIdMatch = eventHref.match(/event=(\d+)/) ?? eventHref.match(/\/events\/(\d+)\//);
    const event = eventEl
      ? {
          id: eventIdMatch ? Number(eventIdMatch[1]) : null,
          name: eventEl.textContent?.trim() ?? null,
        }
      : null;

    // Round history: HLTV renders one `.round-history-con` for regulation
    // and (if applicable) a second `.round-history-con.round-history-overtime`
    // for overtime. Each container has two `.round-history-team-row`
    // children. Within a row, each `img.round-history-outcome` is one round:
    // emptyHistory.svg = the team lost that round; any other svg = they won
    // it. The winning row's image has the running scoreline in `title`.
    const containers = Array.from(document.querySelectorAll(".round-history-con"));
    const roundHistory = [];
    let nextRound = 1;
    for (const container of containers) {
      const isOvertime = container.classList.contains("round-history-overtime");
      const teamRows = Array.from(container.querySelectorAll(".round-history-team-row"));
      if (teamRows.length < 2) continue;
      const t1Imgs = Array.from(teamRows[0].querySelectorAll("img.round-history-outcome"));
      const t2Imgs = Array.from(teamRows[1].querySelectorAll("img.round-history-outcome"));
      const total = Math.min(t1Imgs.length, t2Imgs.length);
      for (let i = 0; i < total; i++) {
        const t1Src = t1Imgs[i].getAttribute("src") ?? "";
        const t2Src = t2Imgs[i].getAttribute("src") ?? "";
        const t1Title = t1Imgs[i].getAttribute("title") ?? "";
        const t2Title = t2Imgs[i].getAttribute("title") ?? "";
        const t1Empty = t1Src.includes("emptyHistory");
        const t2Empty = t2Src.includes("emptyHistory");
        // Both empty + no scoreline means the slot isn't a played round
        // (trailing placeholders inside the OT container when the map ended).
        if (t1Empty && t2Empty && !t1Title && !t2Title) continue;

        let winner = null;
        let outcome = null;
        let score = null;
        if (!t1Empty) {
          winner = 1;
          outcome = t1Src.split("/").pop()?.split(".")[0] ?? null;
          score = t1Title || null;
        } else if (!t2Empty) {
          winner = 2;
          outcome = t2Src.split("/").pop()?.split(".")[0] ?? null;
          score = t2Title || null;
        }
        roundHistory.push({ round: nextRound++, winner, outcome, score, isOvertime });
      }
    }

    // Starting sides: round 1's outcome encodes the winner's side. The loser
    // starts on the opposite side. Bomb outcomes pin the winner's side too:
    // exploded => T planted and won; defused => CT defused and won. stopwatch
    // means time ran out on the bomb => CT won.
    const outcomeToSide = {
      t_win: "T",
      ct_win: "CT",
      bomb_exploded: "T",
      bomb_defused: "CT",
      stopwatch: "CT",
    };
    // Derive starting sides for a slice of rounds from the first played
    // round in that slice (the one whose outcome has a known side).
    const sidesFromSlice = (slice) => {
      for (const r of slice) {
        const winnerSide = r.outcome ? outcomeToSide[r.outcome] : null;
        if (!winnerSide) continue;
        const loserSide = winnerSide === "CT" ? "T" : "CT";
        if (r.winner === 1) return { team1: winnerSide, team2: loserSide };
        if (r.winner === 2) return { team1: loserSide, team2: winnerSide };
      }
      return null;
    };

    const regulationRounds = roundHistory.filter((r) => !r.isOvertime);
    const startSides = sidesFromSlice(regulationRounds) ?? { team1: null, team2: null };

    // Overtime in CS2 is MR3 (3 rounds per half). Teams swap sides every OT
    // half and at the start of every new OT, so we record start sides per
    // half-period (one entry per chunk of 3 OT rounds).
    const overtimeRounds = roundHistory.filter((r) => r.isOvertime);
    const overtimeStartSides = [];
    for (let i = 0; i < overtimeRounds.length; i += 3) {
      const chunk = overtimeRounds.slice(i, i + 3);
      const sides = sidesFromSlice(chunk);
      if (sides) overtimeStartSides.push(sides);
    }

    return {
      id: mapstatsId,
      matchId,
      map,
      date,
      event,
      team1,
      team2,
      startSides,
      overtimeStartSides,
      result: {
        team1TotalRounds: team1Total,
        team2TotalRounds: team2Total,
        halfResults,
      },
      roundHistory,
    };
  }, id);
}

async function readIds(path) {
  const text = await readFile(path, "utf8");
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => Number.parseInt(line, 10))
    .filter((id) => Number.isInteger(id));
}

function statusCode(error) {
  return error?.statusCode ?? error?.response?.statusCode ?? error?.code;
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { browser, page } = await createBrowser(opts);
  const ids = await readIds(opts.idsFile);
  await mkdir(opts.outputDir, { recursive: true });

  try {
    for (const id of ids) {
      const outputPath = join(opts.outputDir, `${id}.json`);
      if (existsSync(outputPath)) {
        console.log(`skip ${id}: cached`);
        continue;
      }

      const url = `https://www.hltv.org/stats/matches/mapstatsid/${id}/-`;
      try {
        await gotoMapstats(page, url, opts.navTimeoutMs, opts.challengeTimeoutMs);
        const data = await extractMapstats(page, id);
        await writeFile(outputPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
        console.log(`fetched ${id}: ${outputPath}`);
      } catch (error) {
        const code = statusCode(error);
        console.error(`failed ${id}: ${code ?? "unknown"} ${error?.message ?? error}`);
        if (STOP_STATUSES.has(Number(code))) {
          console.error("stopping on rate-limit/forbidden response");
          process.exitCode = 1;
          break;
        }
      }

      if (opts.delayMs > 0) {
        await sleep(opts.delayMs);
      }
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

await main();
