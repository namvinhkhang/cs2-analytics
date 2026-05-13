// Browser-side row parsers shared between the match-page aggregate scraper
// and the mapstats-page per-side scraper. The source is exported as a string
// so callers can inject it inside page.evaluate via eval — page.evaluate
// only serializes the top-level function, not its lexical closure, so this
// is the simplest way to share helpers across multiple page contexts.
export const STATS_PARSERS_SOURCE = `
function _firstNumericSegment(path) {
  for (const seg of (path ?? "").split("/").filter(Boolean)) {
    const n = Number(seg);
    if (Number.isInteger(n) && n > 0) return n;
  }
  return null;
}

// "33-32" or "0 : 1" -> [33, 32] / [0, 1]. Missing parts become null.
function _splitDuoNumeric(text, sep) {
  if (!text) return [null, null];
  const parts = text.split(sep).map((s) => Number(s.trim()));
  return [
    Number.isFinite(parts[0]) ? parts[0] : null,
    Number.isFinite(parts[1]) ? parts[1] : null,
  ];
}

// "12 (3)" -> [12, 3]; "15" -> [15, null]. Handles negatives + decimals.
function _splitMainParen(text) {
  if (!text) return [null, null];
  const m = text.match(/^\\s*(-?\\d+(?:\\.\\d+)?)\\s*(?:\\(\\s*(-?\\d+(?:\\.\\d+)?)\\s*\\))?/);
  if (!m) return [null, null];
  return [Number(m[1]), m[2] !== undefined ? Number(m[2]) : null];
}

// Strip "%" / surrounding text and return the numeric value, sign preserved.
function _percent(text) {
  if (!text) return null;
  const m = text.match(/-?\\d+(?:\\.\\d+)?/);
  return m ? Number(m[0]) : null;
}

function _num(text) {
  if (text == null) return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

function _playerIdFromAnchor(a) {
  return a ? _firstNumericSegment(a.getAttribute("href")) : null;
}

function _nickname(a) {
  return a ? a.textContent.trim() : null;
}

function _country(flagImg) {
  return flagImg ? (flagImg.getAttribute("title") ?? null) : null;
}

// Match-page aggregate row columns:
//   K-D, eK-eD, Swing, ADR, eADR, KAST, eKAST, Rating
// Eco columns share a base class with the traditional ones and are toggled
// via the "hidden" class on screen — we still parse them, since the DOM
// always contains both.
function parseMatchTotalStatsRow(row) {
  const a = row.querySelector(".players a, td.players a");
  const flag = row.querySelector(".players img.flag, td.players img.flag");
  const cell = (sel) => row.querySelector(sel)?.textContent?.trim() ?? null;
  const [kills, deaths] = _splitDuoNumeric(cell(".kd.traditional-data"), "-");
  const [ecoKills, ecoDeaths] = _splitDuoNumeric(cell(".kd.eco-adjusted-data"), "-");
  // Match-page renders both the full-name div (with .player-nick span) and a
  // mobile-only nickname-only div under the same anchor — textContent on the
  // anchor would concatenate both. Prefer the dedicated nickname element.
  const nickname =
    row.querySelector(".players .player-nick")?.textContent?.trim() ??
    row.querySelector(".players .smartphone-only.statsPlayerName")?.textContent?.trim() ??
    _nickname(a);
  return {
    playerId: _playerIdFromAnchor(a),
    nickname,
    country: _country(flag),
    kills,
    deaths,
    ecoKills,
    ecoDeaths,
    swing: _percent(cell(".roundSwing")),
    adr: _num(cell(".adr.traditional-data")),
    ecoAdr: _num(cell(".adr.eco-adjusted-data")),
    kast: _percent(cell(".kast.traditional-data")),
    ecoKast: _percent(cell(".kast.eco-adjusted-data")),
    rating: _num(cell(".rating")),
  };
}

// Mapstats-page per-side row columns. Same parser works for totalstats,
// tstats, and ctstats tables — column structure is identical.
//   Op.K-D, Op.eK-eD, MKs, KAST, eKAST, 1vsX, K(hs), eK(hs), A(f),
//   D(t), eD(t), ADR, eADR, KAST(mobile), eKAST(mobile), Swing, Rating
function parseMapPlayerStatsRow(row) {
  const a = row.querySelector(".st-player a");
  const flag = row.querySelector(".st-player img.flag");
  const cell = (sel) => row.querySelector(sel)?.textContent?.trim() ?? null;
  const [openingKills, openingDeaths] = _splitDuoNumeric(cell(".st-opkd.traditional-data"), ":");
  const [ecoOpeningKills, ecoOpeningDeaths] = _splitDuoNumeric(cell(".st-opkd.eco-adjusted-data"), ":");
  const [kills, headshots] = _splitMainParen(cell(".st-kills.traditional-data"));
  const [ecoKills, ecoHeadshots] = _splitMainParen(cell(".st-kills.eco-adjusted-data"));
  const [assists, flashAssists] = _splitMainParen(cell(".st-assists"));
  const [deaths, tradedDeaths] = _splitMainParen(cell(".st-deaths.traditional-data"));
  const [ecoDeaths, ecoTradedDeaths] = _splitMainParen(cell(".st-deaths.eco-adjusted-data"));
  return {
    playerId: _playerIdFromAnchor(a),
    nickname: _nickname(a),
    country: _country(flag),
    openingKills,
    openingDeaths,
    ecoOpeningKills,
    ecoOpeningDeaths,
    multiKillRounds: _num(cell(".st-mks")) ?? 0,
    kast: _percent(cell(".st-kast.traditional-data")),
    ecoKast: _percent(cell(".st-kast.eco-adjusted-data")),
    clutchesWon: _num(cell(".st-clutches")) ?? 0,
    kills,
    headshots,
    ecoKills,
    ecoHeadshots,
    assists,
    flashAssists,
    deaths,
    tradedDeaths,
    ecoDeaths,
    ecoTradedDeaths,
    adr: _num(cell(".st-adr.traditional-data")),
    ecoAdr: _num(cell(".st-adr.eco-adjusted-data")),
    swing: _percent(cell(".st-roundSwing")),
    rating: _num(cell(".st-rating")),
  };
}
`;
