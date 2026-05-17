#!/usr/bin/env node
// Match-page scraper. For each HLTV match ID it visits /matches/{id}/-,
// pulls match-level aggregate stats and the list of mapstats links, then
// visits each mapstats page to embed per-side player stats. One combined
// JSON per match is written to --output-dir. Only completed matches are
// persisted; upcoming/forfeited ones are skipped without a marker so the
// next rerun re-attempts them. With --prune-ids the ids file becomes a
// self-draining queue (see main()): terminal ids are removed, retryable
// ones (not_completed / 403 / timeout) are kept.
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { hostname } from "node:os";
import {
  createBrowser,
  DEFAULT_CHALLENGE_TIMEOUT_MS,
  DEFAULT_DELAY_MS,
  DEFAULT_NAV_TIMEOUT_MS,
  DEFAULT_USER_DATA_DIR,
  gotoHltvPage,
  jitter,
  notifySlack,
  sleep,
  statusCode,
  STOP_STATUSES,
} from "./lib/hltv_browser.mjs";
import {
  extractMapstats,
  MAPSTATS_CONTENT_SELECTOR,
} from "./lib/hltv_mapstats_extract.mjs";
import { STATS_PARSERS_SOURCE } from "./lib/hltv_stats_parsers.mjs";
import {
  buildPreMatchRankings,
  getRankingsForDate,
  snapshotDateForMatch,
} from "./lib/hltv_rankings.mjs";

const DEFAULT_RANKINGS_DIR = "data/hltv_cache/rankings";
const DEFAULT_MAX_CONSECUTIVE_FAILURES = 5;

// .timeAndEvent shows on all match pages (completed, upcoming, even forfeit).
// We only check for stats AFTER it loads — the completed-ness check is done
// in extractMatchPage by looking for table.totalstats with player rows.
const MATCH_CONTENT_SELECTOR = ".timeAndEvent, .standard-box.teamsBox, .match-page";

function usage() {
  console.error(`
Usage:
  PUPPETEER_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra/dist/index.cjs.js \\
  STEALTH_MODULE_PATH=data/hltv_cache/node/node_modules/puppeteer-extra-plugin-stealth/index.js \\
  CHROME_PATH=/usr/bin/chromium \\
  node tools/fetch_hltv_matches.mjs \\
    --ids-file data/hltv_cache/match_ids.txt \\
    --output-dir data/hltv_cache/matches \\
    --delay-ms 5000 \\
    --headless true

Options:
  --ids-file              Newline-delimited HLTV match IDs (required).
  --output-dir            Directory for one JSON file per match ID (required).
  --delay-ms              Delay between every HTTP fetch (match page AND each
                          mapstats page). Defaults to ${DEFAULT_DELAY_MS}.
  --headless              "true" or "false". Defaults to false so browser checks are visible.
  --nav-timeout-ms        Navigation timeout. Defaults to ${DEFAULT_NAV_TIMEOUT_MS}.
  --challenge-timeout-ms  How long to wait for the Cloudflare challenge to clear. Defaults to ${DEFAULT_CHALLENGE_TIMEOUT_MS}.
  --user-data-dir         Persistent Chrome profile dir (keeps cf_clearance cookie). Defaults to ${DEFAULT_USER_DATA_DIR}.
  --chrome-path           Absolute path to a real Chrome binary. Strongly recommended over bundled Chromium for Cloudflare.
  --rankings-dir          Directory for per-day HLTV Valve ranking snapshots. Defaults to ${DEFAULT_RANKINGS_DIR}.
  --max-consecutive-failures  Backstop: stop (and Slack-alert) after this many
                          *transient* failures in a row (nav timeout/ERR_*).
                          403/429 always stops immediately; HLTV soft-500s
                          (non-existent matches) never count. 0 disables the
                          backstop. Defaults to ${DEFAULT_MAX_CONSECUTIVE_FAILURES}.
  --prune-ids             "true"/"false". When true, ids are removed from
                          --ids-file as they resolve terminally (fetched,
                          cached, or non-existent 500); not_completed / 403 /
                          timeout stay for retry. Atomic rewrite. Default false.

Output schema:
  matchId, url, event, date, format, teams{team1,team2},
  result{team1Maps,team2Maps,winner},
  preMatchRankings{snapshotDate,team1{rank,points},team2{rank,points}},
  matchAggregateStats{team1[],team2[]},
  maps[]{ mapstatsId, map, date, result, startSides, overtimeStartSides,
          roundHistory, playerStats{team1{combined,t,ct},team2{combined,t,ct}} }

Completed matches only — upcoming/forfeited matches are skipped without
writing a marker, so reruns pick them up once results are posted.
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
    rankingsDir: args.get("rankings-dir") ?? DEFAULT_RANKINGS_DIR,
    maxConsecutiveFailures: Number.parseInt(
      args.get("max-consecutive-failures") ?? String(DEFAULT_MAX_CONSECUTIVE_FAILURES),
      10,
    ),
    // When true, terminal ids (fetched / cached / non-existent 500) are
    // removed from --ids-file as they resolve. Default false so Airflow and
    // local runs that pass a canonical id list never mutate it.
    pruneIds: (args.get("prune-ids") ?? "false").toLowerCase() === "true",
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

// Atomically rewrite the ids file keeping only ids still in `remaining`,
// preserving the original order. Writing to a temp file and renaming makes
// the swap atomic, so a process kill mid-write can never leave a truncated
// or corrupt queue — a restart simply resumes from the last good prune.
async function persistRemaining(path, orderedIds, remaining) {
  const body = orderedIds.filter((id) => remaining.has(id)).join("\n");
  const tmp = `${path}.tmp`;
  await writeFile(tmp, body ? `${body}\n` : "", "utf8");
  await rename(tmp, path);
}

// Extract everything we need from the match page in one round-trip.
// Returns `{ completed: false }` for pages with no aggregate stats so the
// caller can skip without writing.
async function extractMatchPage(page) {
  return await page.evaluate((parsersSrc) => {
    eval(parsersSrc);

    const text = (sel, root = document) => root.querySelector(sel)?.textContent?.trim() ?? null;
    const attr = (sel, a, root = document) =>
      root.querySelector(sel)?.getAttribute(a) ?? null;
    const num = (s) => {
      if (s == null) return null;
      const n = Number(s);
      return Number.isFinite(n) ? n : null;
    };

    // Mapstats links in DOM order = play order (map 1, map 2, ...).
    const mapstatsLinks = Array.from(document.querySelectorAll("a.results-stats"))
      .map((a) => {
        const href = a.getAttribute("href") ?? "";
        const m = href.match(/\/mapstatsid\/(\d+)\//);
        return m ? Number(m[1]) : null;
      })
      .filter((id) => Number.isInteger(id));

    // Aggregate totalstats — exactly two tables on a completed match page,
    // one per team, in team1/team2 order matching the match header.
    const totalstatsTables = Array.from(document.querySelectorAll("table.totalstats"));
    const dataRows = (tbl) =>
      Array.from(tbl.querySelectorAll("tr")).filter((r) => !r.classList.contains("header-row"));

    // Completed = has both aggregate tables with at least one player row each.
    // mapstatsLinks are not strictly required (rare default-win cases still
    // render totalstats), but we require at least one for a real scrape.
    const completed =
      totalstatsTables.length >= 2 &&
      dataRows(totalstatsTables[0]).length > 0 &&
      dataRows(totalstatsTables[1]).length > 0 &&
      mapstatsLinks.length > 0;

    if (!completed) return { completed: false };

    // Team identity comes from the totalstats header cell:
    //   <a class="teamName team" href="/team/{id}/{slug}">{name}</a>
    const teamFromTable = (tbl) => {
      const a = tbl.querySelector("a.teamName.team, a.teamName");
      if (!a) return { id: null, name: null };
      return {
        id: _firstNumericSegment(a.getAttribute("href") ?? ""),
        name: a.textContent.trim(),
      };
    };
    const teams = {
      team1: teamFromTable(totalstatsTables[0]),
      team2: teamFromTable(totalstatsTables[1]),
    };

    const matchAggregateStats = {
      team1: dataRows(totalstatsTables[0]).map(parseMatchTotalStatsRow),
      team2: dataRows(totalstatsTables[1]).map(parseMatchTotalStatsRow),
    };

    // Event link: /events/{id}/{slug}. Match pages usually expose it inside
    // .timeAndEvent .event, but the same anchor sometimes lives in the
    // header column. Try both.
    const eventAnchor =
      document.querySelector(".timeAndEvent .event a, .event a[href*='/events/']");
    let event = null;
    if (eventAnchor) {
      const href = eventAnchor.getAttribute("href") ?? "";
      const m = href.match(/\/events\/(\d+)\//);
      event = {
        id: m ? Number(m[1]) : null,
        name: eventAnchor.textContent.trim(),
      };
    }

    // Date is on .timeAndEvent .date as data-unix (milliseconds on HLTV).
    // We keep the raw value to match the existing mapstats schema.
    const dateAttr =
      attr(".timeAndEvent .date", "data-unix") ?? attr("[data-unix]", "data-unix");
    const date = dateAttr != null ? num(dateAttr) : null;

    // Format: usually rendered as "Best of N" inside .preformatted-text or
    // the veto-box. Fall back to mapstatsLinks.length-based inference.
    let format = null;
    const formatText =
      text(".preformatted-text") ?? text(".veto-box") ?? text(".padding.preformatted-text");
    const m = formatText?.match(/Best of\s+(\d+)/i);
    if (m) format = `bo${m[1]}`;

    return {
      completed: true,
      event,
      date,
      format,
      teams,
      mapstatsLinks,
      matchAggregateStats,
    };
  }, STATS_PARSERS_SOURCE);
}

// Compute the series result from per-map round totals. Returns null counts
// if any map has no rounds (e.g., unparseable result block).
function computeResult(maps) {
  let team1Maps = 0;
  let team2Maps = 0;
  for (const m of maps) {
    const r1 = m.result?.team1TotalRounds ?? 0;
    const r2 = m.result?.team2TotalRounds ?? 0;
    if (r1 > r2) team1Maps += 1;
    else if (r2 > r1) team2Maps += 1;
  }
  const winner = team1Maps > team2Maps ? 1 : team2Maps > team1Maps ? 2 : null;
  return { team1Maps, team2Maps, winner };
}

async function fetchMatch(page, matchId, opts) {
  const url = `https://www.hltv.org/matches/${matchId}/-`;
  await gotoHltvPage(page, url, {
    navTimeoutMs: opts.navTimeoutMs,
    challengeTimeoutMs: opts.challengeTimeoutMs,
    contentSelector: MATCH_CONTENT_SELECTOR,
  });
  const match = await extractMatchPage(page);
  if (!match.completed) {
    return { skipped: "not_completed" };
  }

  if (opts.delayMs > 0) await sleep(jitter(opts.delayMs));

  // Fetch each mapstats page in the same browser session so cf_clearance,
  // referer, and stealth state all stay warm.
  const maps = [];
  for (const mapstatsId of match.mapstatsLinks) {
    const msUrl = `https://www.hltv.org/stats/matches/mapstatsid/${mapstatsId}/-`;
    try {
      await gotoHltvPage(page, msUrl, {
        navTimeoutMs: opts.navTimeoutMs,
        challengeTimeoutMs: opts.challengeTimeoutMs,
        contentSelector: MAPSTATS_CONTENT_SELECTOR,
      });
      const ms = await extractMapstats(page, mapstatsId, { includePlayerStats: true });
      maps.push({
        mapstatsId: ms.id,
        map: ms.map,
        date: ms.date,
        result: ms.result,
        startSides: ms.startSides,
        overtimeStartSides: ms.overtimeStartSides,
        roundHistory: ms.roundHistory,
        playerStats: ms.playerStats,
      });
    } catch (error) {
      if (error?.hltvErrorPage) {
        // One bad mapstats page shouldn't kill the whole match — record a
        // stub so downstream code can tell something was missed.
        maps.push({ mapstatsId, error: "hltv_500" });
      } else {
        throw error;
      }
    }
    if (opts.delayMs > 0) await sleep(jitter(opts.delayMs));
  }

  const format = match.format ?? (maps.length > 0 ? `bo${Math.max(maps.length, 1)}` : null);

  // Day-before-match Valve ranking snapshot. Done after the mapstats loop so
  // the rankings page-load (and any backwalk) shares the same warmed-up
  // browser session and respects the same inter-request delay.
  let preMatchRankings = null;
  if (match.date != null) {
    const snapshotDate = snapshotDateForMatch(match.date);
    try {
      const rankings = await getRankingsForDate(page, snapshotDate, {
        rankingsDir: opts.rankingsDir,
        navTimeoutMs: opts.navTimeoutMs,
        challengeTimeoutMs: opts.challengeTimeoutMs,
        delayMs: opts.delayMs,
      });
      if (!rankings) {
        console.error(
          `warn ${matchId}: no Valve ranking snapshot within 14 days of ${snapshotDate}`,
        );
      }
      preMatchRankings = buildPreMatchRankings(
        rankings,
        match.teams.team1.id,
        match.teams.team2.id,
      );
    } catch (error) {
      // Don't let a ranking failure kill an otherwise-complete match scrape.
      // Re-throw rate-limit/forbidden so the outer loop can stop.
      const code = error?.statusCode ?? error?.code;
      if (code === 403 || code === 429) throw error;
      console.error(`warn ${matchId}: ranking lookup failed: ${error?.message ?? error}`);
    }
  }

  return {
    skipped: null,
    payload: {
      matchId,
      url,
      event: match.event,
      date: match.date,
      format,
      teams: match.teams,
      result: computeResult(maps),
      preMatchRankings,
      matchAggregateStats: match.matchAggregateStats,
      maps,
    },
  };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { browser, page } = await createBrowser(opts);
  const ids = await readIds(opts.idsFile);
  await mkdir(opts.outputDir, { recursive: true });

  // Self-pruning queue (opt-in via --prune-ids). Terminal outcomes — fetched,
  // already-cached, or a confirmed non-existent match (HLTV soft-500) — are
  // dropped from the ids file so reruns never re-walk them. Retryable
  // outcomes stay. Without --prune-ids the file is left untouched.
  const remaining = opts.pruneIds ? new Set(ids) : null;
  const pruneId = async (id) => {
    if (remaining && remaining.delete(id)) {
      await persistRemaining(opts.idsFile, ids, remaining);
    }
  };

  // Rate-limit guard. A 403/429 stops immediately (cf_clearance dead or IP
  // throttled — needs a human re-warm), which is the failure mode that
  // matters. HLTV soft-500s are EXPECTED (non-existent match ids) and never
  // count. The consecutive-failure stop is only a backstop for transient
  // errors and is disabled when --max-consecutive-failures is 0.
  const breakerEnabled = opts.maxConsecutiveFailures > 0;
  let consecutiveFailures = 0;

  try {
    for (const matchId of ids) {
      const outputPath = join(opts.outputDir, `${matchId}.json`);
      if (existsSync(outputPath)) {
        console.log(`skip ${matchId}: cached`);
        await pruneId(matchId); // already have the data — terminal
        continue;
      }

      try {
        const { skipped, payload } = await fetchMatch(page, matchId, opts);
        if (skipped) {
          // not_completed: match may finish later — keep it in the queue.
          console.log(`skip ${matchId}: ${skipped}`);
        } else {
          await writeFile(outputPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
          console.log(`fetched ${matchId}: ${outputPath} (${payload.maps.length} maps)`);
          await pruneId(matchId); // success — terminal
        }
        consecutiveFailures = 0; // healthy response — fetched or cleanly skipped
      } catch (error) {
        const code = Number(statusCode(error));

        // HLTV soft-500 = the match id does not exist. Expected and terminal:
        // prune it, don't count it against the breaker, keep going.
        if (error?.hltvErrorPage || code === 500) {
          console.log(`gone ${matchId}: 500 non-existent match page`);
          await pruneId(matchId);
          consecutiveFailures = 0;
          if (opts.delayMs > 0) await sleep(jitter(opts.delayMs));
          continue;
        }

        // 403/429 = rate-limited / cf_clearance dead. Stop now and KEEP the
        // id for retry after a human re-warm.
        if (STOP_STATUSES.has(code)) {
          console.error(`failed ${matchId}: ${code} ${error?.message ?? error}`);
          console.error(`stopping on rate-limit/forbidden response (${code})`);
          await notifySlack(
            `🛑 HLTV scraper on \`${hostname()}\` stopped: rate-limit/forbidden (${code}). ` +
              `Last attempted match ${matchId}. VNC in, re-tick the challenge, then ` +
              `restart — cached/non-existent matches are skipped automatically.`,
          );
          process.exitCode = 1;
          break;
        }

        // Anything else (nav timeout, ERR_*, transient): KEEP the id, log,
        // and continue. Only the optional backstop can stop the run here.
        consecutiveFailures += 1;
        console.error(
          `failed ${matchId}: ${code || "unknown"} ${error?.message ?? error}` +
            (breakerEnabled
              ? ` (consecutive ${consecutiveFailures}/${opts.maxConsecutiveFailures})`
              : ""),
        );
        if (breakerEnabled && consecutiveFailures >= opts.maxConsecutiveFailures) {
          console.error(
            `stopping on ${consecutiveFailures} consecutive transient failures`,
          );
          await notifySlack(
            `🛑 HLTV scraper on \`${hostname()}\` stopped: ${consecutiveFailures} ` +
              `consecutive transient failures. Last match ${matchId}.`,
          );
          process.exitCode = 1;
          break;
        }
      }

      if (opts.delayMs > 0) await sleep(jitter(opts.delayMs));
    }
  } finally {
    await browser.close().catch(() => {});
  }
}

await main();
