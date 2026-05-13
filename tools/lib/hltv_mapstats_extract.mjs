// Mapstats-page extractor. Called by both fetch_hltv_mapstats.mjs (standalone,
// no playerStats) and fetch_hltv_matches.mjs (embedded, with per-side
// playerStats). The base payload shape stays identical across callers so
// existing standalone files remain backwards-compatible.
import { STATS_PARSERS_SOURCE } from "./hltv_stats_parsers.mjs";

export const MAPSTATS_CONTENT_SELECTOR = ".match-info-box";

export async function extractMapstats(page, id, { includePlayerStats = false } = {}) {
  return await page.evaluate(
    (parsersSrc, mapstatsId, withPlayerStats) => {
      eval(parsersSrc);

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

      // Per-side player stats: 6 `.stats-content` blocks on the page (3 per
      // team: combined/T/CT). Group by team name from the header, fall back
      // to assuming order [t1.combined, t1.t, t1.ct, t2.combined, t2.t, t2.ct]
      // if the names don't match.
      let playerStats = null;
      if (withPlayerStats) {
        const blocks = Array.from(document.querySelectorAll(".stats-content"));
        const tables = blocks
          .map((block) => block.querySelector("table.stats-table"))
          .filter(Boolean);
        const classify = (table) => {
          const cls = table.className;
          if (/\btotalstats\b/.test(cls)) return "combined";
          if (/\btstats\b/.test(cls)) return "t";
          if (/\bctstats\b/.test(cls)) return "ct";
          return null;
        };
        const norm = (s) => (s ?? "").trim().toLowerCase();
        const buckets = { team1: { combined: [], t: [], ct: [] }, team2: { combined: [], t: [], ct: [] } };
        let unmatched = 0;
        for (const [idx, table] of tables.entries()) {
          const type = classify(table);
          if (!type) continue;
          const rows = Array.from(table.querySelectorAll("tbody tr")).map(parseMapPlayerStatsRow);
          const headerName = table.querySelector("th.st-teamname")?.textContent?.trim();
          let teamKey = null;
          if (headerName) {
            if (norm(headerName) === norm(team1.name)) teamKey = "team1";
            else if (norm(headerName) === norm(team2.name)) teamKey = "team2";
          }
          // Fallback: first 3 tables = team1, next 3 = team2.
          if (!teamKey) {
            unmatched++;
            teamKey = idx < 3 ? "team1" : "team2";
          }
          buckets[teamKey][type] = rows;
        }
        playerStats = buckets;
        if (unmatched > 0) {
          // Surface the fallback path so callers can tell whether the
          // grouping is name-confirmed or order-inferred.
          playerStats._headerMatchUnmatched = unmatched;
        }
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
        ...(withPlayerStats ? { playerStats } : {}),
      };
    },
    STATS_PARSERS_SOURCE,
    id,
    includePlayerStats,
  );
}
