// HLTV Valve ranking snapshot fetcher. One file per day under rankingsDir
// keyed by ISO date (`YYYY-MM-DD.json`). The match scraper calls
// `getRankingsForDate(page, date, opts)` on demand; cache hits are free,
// misses cost one ranking page-load that's then reused for every other
// match scraped against the same day.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { gotoHltvPage, sleep } from "./hltv_browser.mjs";

const MONTH_NAMES = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
];

const RANKING_CONTENT_SELECTOR = ".ranked-team";
const DEFAULT_BACKWALK_DAYS = 14;

// Build a `YYYY-MM-DD` string from a Date in UTC. We index everything in UTC
// to match HLTV's `data-unix` semantics — the calendar date HLTV publishes
// the snapshot under is always UTC.
function toIsoDate(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, "0");
  const d = String(date.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// "Day before match" in UTC. HLTV's data-unix is UTC milliseconds, so subtract
// one day worth of ms before truncating to a calendar date.
export function snapshotDateForMatch(matchUnixMs) {
  return toIsoDate(new Date(matchUnixMs - 86_400_000));
}

// Walk one day earlier. Used by the backwalk when a specific date's ranking
// page is missing (pre-Valve-era dates, rare gaps).
function previousDate(isoDate) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return toIsoDate(d);
}

// HLTV's URL is lowercase-full-month, no zero-pad on the day:
//   /valve-ranking/teams/2025/december/15
export function rankingUrlForDate(isoDate) {
  const [yStr, mStr, dStr] = isoDate.split("-");
  const month = MONTH_NAMES[Number(mStr) - 1];
  return `https://www.hltv.org/valve-ranking/teams/${Number(yStr)}/${month}/${Number(dStr)}`;
}

export function rankingsCachePath(rankingsDir, isoDate) {
  return join(rankingsDir, `${isoDate}.json`);
}

async function readCacheIfPresent(rankingsDir, isoDate) {
  const path = rankingsCachePath(rankingsDir, isoDate);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

async function writeCache(rankingsDir, isoDate, payload) {
  await mkdir(rankingsDir, { recursive: true });
  await writeFile(
    rankingsCachePath(rankingsDir, isoDate),
    `${JSON.stringify(payload, null, 2)}\n`,
    "utf8",
  );
}

// Browser-side extractor. Each `.ranked-team` box is one team entry.
async function extractRankingsPage(page) {
  return await page.evaluate(() => {
    const boxes = Array.from(document.querySelectorAll(".ranked-team"));
    return boxes.map((box) => {
      // Position cell: "#1" → 1
      const positionText = box.querySelector(".position")?.textContent?.trim() ?? "";
      const rankMatch = positionText.match(/\d+/);
      const rank = rankMatch ? Number(rankMatch[0]) : null;

      const name = box.querySelector(".teamLine .name")?.textContent?.trim() ?? null;

      // Points cell renders as "(2070 Valve points)".
      const pointsText = box.querySelector(".teamLine .points")?.textContent ?? "";
      const pointsMatch = pointsText.match(/\d+/);
      const points = pointsMatch ? Number(pointsMatch[0]) : null;

      const region = box.querySelector(".teamLine .region")?.textContent?.trim() ?? null;

      // Team id from any `/team/{id}/{slug}` anchor. The HLTV Team profile
      // link inside `.lineup-con` is the most reliable spot.
      const teamLink = box.querySelector('a[href^="/team/"]');
      let teamId = null;
      if (teamLink) {
        const m = (teamLink.getAttribute("href") ?? "").match(/\/team\/(\d+)\//);
        if (m) teamId = Number(m[1]);
      }

      // Players from the lineup table (hidden by default in DOM but present).
      const players = Array.from(box.querySelectorAll("td.player-holder a")).map((a) => {
        const href = a.getAttribute("href") ?? "";
        const m = href.match(/\/player\/(\d+)\//);
        const nickEl = a.querySelector(".nick");
        const nickname = nickEl ? nickEl.textContent.trim() : null;
        return { id: m ? Number(m[1]) : null, nickname };
      });

      return { rank, id: teamId, name, points, region, players };
    });
  });
}

// One page-fetch attempt for a specific date. Returns the payload on success
// or `null` if the date has no rankings (timeout on selector / HLTV error
// page). Re-throws Cloudflare/rate-limit errors so the outer loop can stop.
async function tryFetchRankings(page, isoDate, opts) {
  const url = rankingUrlForDate(isoDate);
  try {
    await gotoHltvPage(page, url, {
      navTimeoutMs: opts.navTimeoutMs,
      challengeTimeoutMs: opts.challengeTimeoutMs,
      contentSelector: RANKING_CONTENT_SELECTOR,
    });
  } catch (error) {
    const message = error?.message ?? "";
    // Soft failures we want to treat as "no rankings for this date":
    // - HLTV's 500 error page (rendered for non-existent dates).
    // - Selector timeout (page loaded but no .ranked-team).
    if (error?.hltvErrorPage || /timeout|waiting for selector/i.test(message)) {
      return null;
    }
    throw error;
  }
  const teams = await extractRankingsPage(page);
  if (teams.length === 0) return null;
  return { date: isoDate, url, teams };
}

// Cache-aware fetch with backwalk. Returns the snapshot for `requestedDate`
// if available, otherwise walks back up to `maxBackwalkDays` looking for the
// nearest prior snapshot. Returns `null` if nothing found.
//
// Important: we ONLY cache successful fetches under their actual date. A
// backwalk that lands on day D-3 caches `D-3.json`, but does NOT write a
// marker at D, D-1, or D-2. That keeps the cache truthful — if HLTV later
// publishes a missing day, we'd want to pick it up on rerun rather than
// being stuck on a stale negative cache.
export async function getRankingsForDate(page, requestedDate, opts) {
  const {
    rankingsDir,
    navTimeoutMs,
    challengeTimeoutMs,
    delayMs = 0,
    maxBackwalkDays = DEFAULT_BACKWALK_DAYS,
  } = opts;

  let date = requestedDate;
  for (let i = 0; i <= maxBackwalkDays; i++) {
    const cached = await readCacheIfPresent(rankingsDir, date);
    if (cached) return cached;

    const fetched = await tryFetchRankings(page, date, {
      navTimeoutMs,
      challengeTimeoutMs,
    });
    if (fetched) {
      await writeCache(rankingsDir, date, fetched);
      if (delayMs > 0) await sleep(delayMs);
      return fetched;
    }
    if (delayMs > 0) await sleep(delayMs);
    date = previousDate(date);
  }
  return null;
}

// Build the embedded preMatchRankings block from a rankings payload and the
// match's team identities. Returns `null` if rankings is null. A team that
// isn't on the ranking that day comes back as `{ rank: null, points: null }`
// rather than being omitted.
export function buildPreMatchRankings(rankings, team1Id, team2Id) {
  if (!rankings) return null;
  const byId = new Map(rankings.teams.map((t) => [t.id, t]));
  const lookup = (id) => {
    const t = id != null ? byId.get(id) : null;
    return t ? { rank: t.rank, points: t.points } : { rank: null, points: null };
  };
  return {
    snapshotDate: rankings.date,
    team1: lookup(team1Id),
    team2: lookup(team2Id),
  };
}
