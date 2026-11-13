/* Portal NBA · sitio web.
   Núcleo: utilidades, acceso a los datos, estado de la interfaz y piezas que comparten las páginas.
   Cada página se registra en App.pages (ver partidos.js, analisis.js, liga.js y seguimiento.js).
   La matemática (sideEval, edgeBucket) viene de calc.js, que se genera a partir de web/portal_template.html. */
(function () {
"use strict";
const NBA = window.NBA, IDX = NBA.index, LG = NBA.league;
const App = window.App = {pages: {}, needs: {}};

const $ = (s, el) => (el || document).querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const pct = (x, d) => x == null || isNaN(x) ? "–" : (100 * x).toFixed(d == null ? 0 : d) + " %";
const pp = x => x == null || isNaN(x) ? "–" : (x >= 0 ? "+" : "") + (100 * x).toFixed(1) + " pp";
const num = (x, d) => x == null || isNaN(x) ? "–" : Number(x).toFixed(d == null ? 1 : d);
const sgn = (x, d) => x == null || isNaN(x) ? "–" : (x > 0 ? "+" : "") + Number(x).toFixed(d == null ? 1 : d);
const L = IDX.labels;
const STATUS = {out: "baja", questionable: "duda", doubtful: "muy dudoso", probable: "probable", available: ""};
const POS = {G: "base o escolta", F: "alero", C: "pívot"};
// Color principal de cada equipo: solo decorativo (borde de la insignia).
const COLORS = {ATL: "#E03A3E", BOS: "#007A33", BKN: "#7a7f87", CHA: "#00788C", CHI: "#CE1141", CLE: "#860038", DAL: "#00538C", DEN: "#FEC524",
  DET: "#C8102E", GSW: "#FFC72C", HOU: "#CE1141", IND: "#FDBB30", LAC: "#C8102E", LAL: "#552583", MEM: "#5D76A9", MIA: "#98002E", MIL: "#00471B",
  MIN: "#236192", NOP: "#B4975A", NYK: "#F58426", OKC: "#007AC1", ORL: "#0077C0", PHI: "#006BB6", PHX: "#E56020", POR: "#E03A3E", SAC: "#5A2D81",
  SAS: "#C4CED4", TOR: "#CE1141", UTA: "#F9A01B", WAS: "#E31837"};

const ICONS = {
  cal: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4", search: "M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14zM20 20l-4-4",
  user: "M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8zM5 20c0-3.5 3-6 7-6s7 2.5 7 6",
  users: "M9 11a3.5 3.5 0 1 0 0-7a3.5 3.5 0 0 0 0 7zM2.5 20c0-3 2.8-5.5 6.5-5.5s6.5 2.5 6.5 5.5M16 4.2a3.5 3.5 0 0 1 0 6.6M18 14.8c2 .8 3.5 2.7 3.5 5.2",
  table: "M4 5h16v14H4zM4 10h16M10 5v14", pulse: "M3 12h4l3-7l4 14l3-7h4", chart: "M4 20V10M10 20V4M16 20v-8M21 20H3",
  book: "M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11",
  star: "M12 3.5l2.6 5.4l5.9.8l-4.3 4.1l1 5.9L12 16.9l-5.2 2.8l1-5.9L3.5 9.7l5.9-.8z",
  trophy: "M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 20h8M10 17h4",
  slip: "M7 3h10v18l-2.5-1.5L12 21l-2.5-1.500L7 21zM10 8h4M10 12h4",
  menu: "M4 6h16M4 12h16M4 18h16", chev: "M15 6l-6 6l6 6", arrow: "M5 12h14M13 6l6 6l-6 6", list: "M4 7h16M4 12h16M4 17h16",
};
const ic = n => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICONS[n]}"/></svg>`;

// ---- almacenamiento local (líneas manuales y favoritos de la jornada; puede no estar disponible) ----
const storeKey = "portal-nba-" + IDX.today;
const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || "null") || d; } catch (e) { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento: la página sigue funcionando */ } };
App.manual = load(storeKey, {});
App.favs = load(storeKey + "-fav", {});
App.saveManual = () => save(storeKey, App.manual);
App.saveFavs = () => save(storeKey + "-fav", App.favs);

// ---- estado de la interfaz (filtros de cada página) ----
const DEFAULTS = {
  fxs: {sort: "hora"},
  fx: {tab: ""},
  pb: {market: "all", game: "", side: "all", win: "10", min20: false, lastDays: "", minHit: "", minOdds: "", maxOdds: "", minEdge: "0.06",
       hideDoubt: false, starters: false, onePer: true, q: "", sort: "edge", compact: false},
  tb: {game: "", market: "all", win: "10", minTeam: "", minOpp: "", minOdds: "", maxOdds: "", sort: "hora"},
  ps: {games: [], stat: "pts", mode: "tasa", n: "", win: "10", minRate: "60", pos: ["G", "F", "C"], minMin: "0", venue: ["casa", "fuera"],
       role: "todos", allTeams: true, hideDoubt: false, hideStarted: true},
  st: {game: "", market: "pts", q: "", sort: "mu", dir: -1},
  lg: {tab: "clasificacion", order: "balance", per: "partido", q: "", team: "", sort: "pts", dir: -1},
};
const ui = App.ui = JSON.parse(JSON.stringify(DEFAULTS));
const setPath = (path, v) => { const [a, b] = path.split("."); ui[a][b] = v; };
const getPath = path => { const [a, b] = path.split("."); return ui[a][b]; };

// ---- datos ----
const T = () => NBA.days[IDX.today];                       // la jornada de hoy: sobre ella trabajan las páginas de análisis
const dayInfo = d => IDX.days.find(x => x.date === d);
const gameOf = (date, gid) => { const D = NBA.days[date]; return D ? D.games.find(g => g.game_id === gid) : null; };
const playerOf = pid => T().players.find(p => p.pid === pid);
const team = abbr => LG.teams[abbr] || {name: abbr, w: 0, l: 0, form: [], rank: null, rating: null};
const pending = {};
function loadDay(date) {                                   // los días se cargan con una etiqueta script: funciona también con doble clic
  if (NBA.days[date]) return Promise.resolve();
  if (!dayInfo(date)) return Promise.reject(new Error("día no disponible"));
  if (!pending[date]) pending[date] = new Promise((ok, ko) => {
    const s = document.createElement("script");
    s.src = "data/day-" + date + ".js";
    s.onload = () => NBA.days[date] ? ok() : ko(new Error("datos vacíos"));
    s.onerror = () => { delete pending[date]; ko(new Error("no se pudo cargar")); };
    document.head.appendChild(s);
  });
  return pending[date];
}

// ---- fechas y textos ----
const asDate = d => new Date(d + "T12:00:00");
const fmtDay = (d, o) => asDate(d).toLocaleDateString("es-ES", o || {weekday: "long", day: "numeric", month: "long"});
const shortDay = d => asDate(d).toLocaleDateString("es-ES", {day: "2-digit", month: "2-digit"});
const tipDate = g => { const d = new Date(g.tip_utc); return isNaN(d) ? null : d; };
const tipTime = g => { const d = tipDate(g); return d ? d.toLocaleString("es-ES", {weekday: "short", hour: "2-digit", minute: "2-digit"}) + " h" : ""; };
const tipHour = g => { const d = tipDate(g); return d ? d.toLocaleTimeString("es-ES", {hour: "2-digit", minute: "2-digit"}) : "–"; };
const gameLabel = g => g.away + " @ " + g.home;
const record = abbr => { const t = team(abbr); return t.w + t.l ? t.w + "-" + t.l : ""; };
const badge = abbr => `<span class="badge" style="--tc:${COLORS[abbr] || "var(--bar)"}">${esc(abbr)}</span>`;
function gapReading(g) {
  if (g.gap_pts == null) return ["sin línea", ""];
  const sd = (IDX.evidence.games && IDX.evidence.games.gap_sd) || 3.3, z = Math.abs(g.gap_pts) / sd;
  if (z < 1) return ["alineado con el mercado", "good"];
  if (z < 1.5) return ["discrepancia moderada", "warn"];
  return ["discrepancia grande: revisa bajas y alineaciones", "bad"];
}

// ---- líneas y evaluación ----
// Línea vigente de un jugador y mercado: la escrita a mano si existe; si no, la de DraftKings.
function lineOf(pl, m) {
  const mk = pl.markets[m], base = mk.line || null, man = App.manual[pl.pid + "|" + m];
  if (man && man.line != null) {
    return {value: man.line, over: man.over != null ? man.over : (base && base.side_ok ? base.over : null),
            under: man.under != null ? man.under : (base && base.side_ok ? base.under : null), manual: true};
  }
  if (!base) return null;
  return {value: base.value, over: base.side_ok ? base.over : null, under: base.side_ok ? base.under : null, manual: false, src: base.src};
}
function evalOf(pl, m) {
  const ln = lineOf(pl, m);
  if (!ln) return null;
  const e = sideEval(pl.markets[m].sv, ln.value, ln.over, ln.under);
  e.line = ln;
  return e;
}

// ---- historial de partidos de un jugador (filas de logs: ver nba_model/site.py::player_logs) ----
const COL = {min: 5, pts: 6, reb: 7, ast: 8, fg3m: 9};
const statVal = (r, m) => (IDX.combos[m] || [m]).reduce((s, k) => s + r[COL[k]], 0);
// Devuelve las filas (antiguo -> reciente) que cumplen los filtros y se queda con las `win` últimas.
function history(p, o) {
  let rows = T().logs[p.pid] || [];
  if (o.allTeams === false) rows = rows.filter(r => r[1] === p.team);
  if (o.minMin) rows = rows.filter(r => r[5] >= o.minMin);
  if (o.venue && o.venue.length === 1) rows = rows.filter(r => (r[3] ? "casa" : "fuera") === o.venue[0]);
  if (o.venue && o.venue.length === 0) rows = [];
  if (o.role === "titular") rows = rows.filter(r => r[4]);
  if (o.role === "suplente") rows = rows.filter(r => !r[4]);
  if (o.days) { const lim = asDate(IDX.today).getTime() - o.days * 864e5; rows = rows.filter(r => asDate(r[0]).getTime() >= lim); }
  return rows.slice(-(o.win || 10));
}
// Aciertos y racha de una serie (antiguo -> reciente) según la condición `ok`.
function hitInfo(vals, ok) {
  let st = 0;
  for (let i = vals.length - 1; i >= 0 && ok(vals[i]); i--) st++;
  return {h: vals.filter(ok).length, n: vals.length, st};
}
const sideOk = (line, side) => v => side === "under" ? v < line : v > line;

// ---- piezas de interfaz ----
const statusChip = p => p.status !== "available" ? `<span class="chip warn">${STATUS[p.status] || esc(p.status)}</span>` : "";
const star = key => `<button class="star ${App.favs[key] ? "on" : ""}" data-fav="${esc(key)}" title="${App.favs[key] ? "Quitar de favoritos" : "Guardar en favoritos"}" aria-label="Favorito">${ic("star")}</button>`;
const seg = (path, opts) => `<div class="seg">${opts.map(o => `<button data-set="${path}" data-v="${esc(o[0])}" class="${String(getPath(path)) === String(o[0]) ? "on" : ""}">${esc(o[1])}</button>`).join("")}</div>`;
const tog = (path, opts) => `<div class="seg">${opts.map(o => `<button data-tog="${path}" data-v="${o[0]}" class="${getPath(path).includes(o[0]) ? "on" : ""}">${o[1]}</button>`).join("")}</div>`;
const chk = (path, label) => `<label class="chk"><input type="checkbox" data-ui="${path}" ${getPath(path) ? "checked" : ""}> ${esc(label)}</label>`;
const sel = (path, opts) => `<select data-ui="${path}">${opts.map(o => `<option value="${esc(o[0])}" ${String(getPath(path)) === String(o[0]) ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
const gameSelect = (path, all) => sel(path, [["", all]].concat(T().games.map(g => [g.game_id, gameLabel(g)])));
const numIn = (path, ph, step) => `<input type="number" min="0" step="${step || 1}" data-ui="${path}" placeholder="${esc(ph)}" value="${esc(getPath(path))}">`;
const segbar = (p, n) => `<span class="segbar" title="${pct(p)}">${Array.from({length: n || 20}, (_, i) => `<i class="${i < Math.round((n || 20) * p) ? "h" : ""}"></i>`).join("")}</span>`;
const rate = (h, n) => n ? `<span class="rate"><b>${pct(h / n)}</b> <span class="mute">${h}/${n}</span></span>` : `<span class="mute">–</span>`;
// Fichas de los últimos partidos (el más reciente primero): valor, minutos, rival y fecha.
function tiles(rows, m, ok, mini) {
  if (!rows.length) return `<span class="sub">sin partidos con estos filtros</span>`;
  return `<div class="tiles ${mini ? "mini" : ""}">${rows.slice().reverse().map(r => { const v = statVal(r, m);
    return `<div class="tile ${ok ? (ok(v) ? "h" : "") : ""}" title="${esc(fmtDay(r[0]))} · ${r[3] ? "vs" : "@"} ${esc(r[2])} · ${r[5]} min${r[4] ? " · titular" : ""}"><b>${v}</b>${mini ? "" : `${r[5]}′<br>${r[3] ? "" : "@"}${esc(r[2])}<br>${shortDay(r[0])}`}</div>`; }).join("")}</div>`;
}
function pageHead(icon, title, sub, right) {
  return `<div class="phead"><div class="l"><div class="pic">${ic(icon)}</div><div><h1>${esc(title)}</h1><div class="sub">${esc(sub)}</div></div></div>${right ? `<div class="sub">${right}</div>` : ""}</div>`;
}
const updated = () => "Actualizado " + new Date(IDX.generated_utc).toLocaleString("es-ES", {day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"});

// ---- detalle de jugador (ventana) ----
function openPlayer(pid) {
  const p = playerOf(pid); if (!p) return;
  const g = gameOf(IDX.today, p.game_id), rows = history(p, {win: 10});
  const blocks = IDX.markets.map(m => {
    const mk = p.markets[m], e = evalOf(p, m), vals = rows.map(r => statVal(r, m)), mx = Math.max(1, ...vals, e ? e.line.value : 0);
    const over = e ? vals.filter(v => v > e.line.value).length : 0;
    const bars = vals.map(v => `<div class="${e && v > e.line.value ? "h" : ""}" style="height:${Math.max(3, 100 * v / mx)}%"><span>${v}</span></div>`).join("");
    return `<div class="card"><div class="row"><h3>${esc(L[m])}</h3><span><b>${num(mk.mu)}</b> proyectado</span></div>
      <div class="sub">Últ. 5: ${num(mk.l5)} · últ. 10: ${num(mk.l10)} · temporada: ${num(mk.season)} · rival ${sgn(100 * mk.def, 0)} %</div>
      <div class="bars" style="margin-top:20px">${bars}</div>
      <div class="sub" style="margin-top:6px">${e ? `Línea ${num(e.line.value)}${e.line.manual ? " (tuya)" : ""}: P(más) ${pct(e.p_over)} · P(menos) ${pct(e.p_under)}${e.edge != null ? ` · ventaja ${e.side === "over" ? "más" : "menos"} ${pp(e.edge)} · valor esperado ${sgn(100 * e.ev)} %` : ""} · ${over}/${vals.length} por encima` : "Sin línea: escríbela en la página Proyecciones para ver la probabilidad."}</div></div>`;
  }).join("");
  const log = rows.slice().reverse().map(r => `<tr><td class="l">${esc(fmtDay(r[0], {day: "numeric", month: "short"}))}</td><td class="l">${r[3] ? "vs" : "@"} ${esc(r[2])}</td><td class="c">${r[4] ? "sí" : "–"}</td><td>${r[5]}</td><td>${r[6]}</td><td>${r[7]}</td><td>${r[8]}</td><td>${r[9]}</td></tr>`).join("");
  $("#dlg").innerHTML = `<div class="row"><h2 style="margin:0">${esc(p.name)} <span class="sub">${esc(p.pos)} · ${esc(p.team)} ${p.home ? "vs" : "@"} ${esc(p.opp)}</span></h2><button class="btn small" id="dclose">Cerrar</button></div>
    <div class="sub" style="margin:6px 0 12px">Minutos proyectados ${num(p.min)} (media últimos 10: ${num(p.min_l10)}) · ${p.gp} partidos esta temporada${p.status !== "available" ? " · estado: " + (STATUS[p.status] || p.status) : ""}${g ? " · " + esc(tipTime(g)) : ""}. Barras: últimos partidos (izquierda = más antiguo); en verde los que superan la línea.</div>
    <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(300px,1fr))">${blocks}</div>
    <h3 style="margin-top:16px">Últimos partidos</h3><div class="tablewrap"><table><thead><tr><th class="l">Fecha</th><th class="l">Rival</th><th class="c">Titular</th><th>Min</th><th>Pts</th><th>Reb</th><th>Ast</th><th>3P</th></tr></thead><tbody>${log || `<tr><td colspan="8" class="l mute">Sin partidos registrados.</td></tr>`}</tbody></table></div>`;
  $("#dclose").onclick = () => $("#dlg").close();
  $("#dlg").showModal();
}

Object.assign(App, {NBA, IDX, LG, $, esc, pct, pp, num, sgn, L, STATUS, POS, COLORS, ic, DEFAULTS, setPath, getPath, T, dayInfo, gameOf, playerOf, team, loadDay,
  asDate, fmtDay, shortDay, tipTime, tipHour, gameLabel, record, badge, gapReading, lineOf, evalOf, statVal, history, hitInfo, sideOk,
  statusChip, star, seg, tog, chk, sel, gameSelect, numIn, segbar, rate, tiles, pageHead, updated, openPlayer, save, load});
})();
