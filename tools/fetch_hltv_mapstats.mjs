#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  createBrowser,
  DEFAULT_CHALLENGE_TIMEOUT_MS,
  DEFAULT_DELAY_MS,
  DEFAULT_NAV_TIMEOUT_MS,
  DEFAULT_USER_DATA_DIR,
  gotoHltvPage,
  sleep,
  statusCode,
  STOP_STATUSES,
} from "./lib/hltv_browser.mjs";
import {
  extractMapstats,
  MAPSTATS_CONTENT_SELECTOR,
} from "./lib/hltv_mapstats_extract.mjs";

function usage() {
  console.error(`
Usage:
  PUPPETEER_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra/dist/index.cjs.js \\
  STEALTH_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra-plugin-stealth/index.js \\
  CHROME_PATH=/usr/bin/chromium \\
  node tools/fetch_hltv_mapstats.mjs \\
    --ids-file data/hltv_cache/mapstats_ids.txt \\
    --output-dir data/hltv_cache/map_stats \\
    --delay-ms 5000 \\
    --headless true

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

async function readIds(path) {
  const text = await readFile(path, "utf8");
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => Number.parseInt(line, 10))
    .filter((id) => Number.isInteger(id));
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
        await gotoHltvPage(page, url, {
          navTimeoutMs: opts.navTimeoutMs,
          challengeTimeoutMs: opts.challengeTimeoutMs,
          contentSelector: MAPSTATS_CONTENT_SELECTOR,
        });
        const data = await extractMapstats(page, id);
        await writeFile(outputPath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
        console.log(`fetched ${id}: ${outputPath}`);
      } catch (error) {
        if (error?.hltvErrorPage) {
          // Persist a marker so the next run skips this id via existsSync.
          const marker = { id, error: "hltv_500", skipped: true };
          await writeFile(outputPath, `${JSON.stringify(marker, null, 2)}\n`, "utf8");
          console.log(`skipped ${id}: HLTV 500 error page`);
        } else {
          const code = statusCode(error);
          console.error(`failed ${id}: ${code ?? "unknown"} ${error?.message ?? error}`);
          if (STOP_STATUSES.has(Number(code))) {
            console.error("stopping on rate-limit/forbidden response");
            process.exitCode = 1;
            break;
          }
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
