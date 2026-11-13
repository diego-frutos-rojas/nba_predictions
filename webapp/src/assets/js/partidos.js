/* Páginas «Partidos» (un día: anterior, hoy o próximo) y ficha de partido con sus pestañas. */
(function () {
"use strict";
const A = window.App, {NBA, IDX, $, esc, pct, num, sgn, pp, L, STATUS, COLORS, ic, ui, T, team, asDate, fmtDay, tipTime, tipHour, gameLabel,
  record, badge, gapReading, pageHead, seg} = A;

const relDay = d => { const n = Math.round((asDate(d) - asDate(IDX.today)) / 864e5); return n === 0 ? "Hoy" : n === -1 ? "Ayer" : n === 1 ? "Mañana" : fmtDay(d, {weekday: "long"}); };
const winner = g => g.home_pts > g.away_pts ? g.home : g.away;
const modelFav = g => g.model.prob_home >= 0.5 ? g.home : g.away;
const marketFav = g => g.market.prob_home == null ? null : (g.market.prob_home >= 0.5 ? g.home : g.away);
// Resultado de una línea guardada: lado que prefería el modelo frente a la estadística real.
function lineResult(mk) {
  const e = mk.eval || {};
  if (!e.side) return null;
  if (mk.y == null) return "anulada";
  if (mk.y === mk.line.value) return "empate";
  return (e.side === "over" ? mk.y > mk.line.value : mk.y < mk.line.value) ? "acierto" : "fallo";
}
function dayLines(D, gid, minEdge) {
  const out = [];
  for (const p of D.players) {
    if (gid && p.game_id !== gid) continue;
    for (const m of IDX.markets) {
      const mk = p.markets[m]; if (!mk) continue;
      const res = lineResult(mk); if (!res || (mk.eval.edge || 0) < minEdge) continue;
      out.push({p, m, mk, res});
    }
  }
  return out;
}
const tally = lines => { const a = lines.filter(x => x.res === "acierto").length, f = lines.filter(x => x.res === "fallo").length; return {a, f, n: a + f}; };

// ---------------------------------------------------------------- Partidos (lista de un día)
function fxRow(D, g) {
  const href = `#/partido/${D.date}/${esc(g.game_id)}`, rec = t => { const r = record(t); return r ? ` <span class="sub">${r}</span>` : ""; };
  const teams = (extraA, extraH) => `<div class="teams"><div>${badge(g.away)}<span class="tn">${esc(g.away_name)}${rec(g.away)}</span>${extraA || ""}</div><div>${badge(g.home)}<span class="tn">${esc(g.home_name)}${rec(g.home)}</span>${extraH || ""}</div></div>`;
  if (D.kind === "futuro") {
    return `<a class="fx" href="${href}"><div class="t"><div>${esc(tipHour(g))}</div><div class="sub">–</div></div>${teams()}
      <div class="nums sub"><div>nivel #${team(g.away).rank}</div><div>nivel #${team(g.home).rank}</div></div>
      <div class="x"><span class="chip">proyecciones el día del partido</span><span class="btn small">Vista previa ${ic("arrow")}</span></div></a>`;
  }
  const ph = g.model.prob_home;
  if (D.kind === "pasado") {
    const done = g.state === "post", w = done ? winner(g) : null, mf = modelFav(g), kf = marketFav(g), t = tally(dayLines(D, g.game_id, 0));
    const mark = (ok, lab) => `<span class="chip ${ok ? "good" : "bad"}">${lab} ${ok ? "✓" : "✗"}</span>`;
    return `<a class="fx" href="${href}"><div class="t"><div>${done ? "Final" : "–"}</div></div>${teams()}
      <div class="nums"><div class="${w === g.away ? "" : "lose"}">${done ? g.away_pts : "–"}</div><div class="${w === g.home ? "" : "lose"}">${done ? g.home_pts : "–"}</div></div>
      <div class="x">${done ? mark(mf === w, `modelo: ${esc(mf)} ${pct(Math.max(ph, 1 - ph))}`) + (kf ? mark(kf === w, `mercado: ${esc(kf)} ${pct(Math.max(g.market.prob_home, 1 - g.market.prob_home))}`) : "") : `<span class="chip">sin resultado en los datos</span>`}
        ${t.n ? `<span class="chip">líneas ${t.a}/${t.n}</span>` : ""}<span class="btn small">Ver resultado ${ic("arrow")}</span></div></a>`;
  }
  const [txt, cls] = gapReading(g), pre = g.state === "pre", nInj = g.injuries.home.length + g.injuries.away.length;
  const b2b = s => g.rest[s] <= 1 ? `<span class="chip warn">jugó ayer</span>` : "";
  const st = pre ? "–" : g.state === "in" ? `<span class="pos">● ${esc(g.detail)}</span>` : "Final";
  return `<a class="fx" href="${href}"><div class="t"><div>${esc(tipHour(g))}</div><div class="sub">${st}</div></div>${teams(b2b("away"), b2b("home"))}
    <div class="nums" title="${pre ? "Probabilidad de victoria según el modelo" : "Marcador"}"><div>${pre ? pct(1 - ph) : g.away_pts}</div><div>${pre ? pct(ph) : g.home_pts}</div></div>
    <div class="x"><span class="chip ${cls}">${txt}</span><span class="chip ${nInj ? "warn" : ""}">Bajas ${nInj}</span><span class="chip">${g.n_lines ? g.n_lines + " líneas" : "sin líneas"}</span><span class="btn small">${pre ? "Ver partido" : "Ver datos"} ${ic("arrow")}</span></div></a>`;
}
A.pages.partidos = (el, r) => {
  const date = r.a || IDX.today, D = NBA.days[date], days = IDX.days.map(d => d.date), i = days.indexOf(date);
  const nav = (d, cls) => `<a class="btn dbtn ${cls} ${d ? "" : "off"}" ${d ? `href="#/partidos/${d}"` : ""} title="${d ? esc(fmtDay(d)) : ""}" aria-label="${cls === "back" ? "Día anterior" : "Día siguiente"}">${ic("arrow")}</a>`;
  let games = D.games.slice();
  if (D.kind !== "futuro" && ui.fxs.sort === "discrepancia") games.sort((a, b) => Math.abs(b.gap_pts || 0) - Math.abs(a.gap_pts || 0));
  else games.sort((a, b) => String(a.tip_utc).localeCompare(String(b.tip_utc)));
  let summary = "";
  if (D.kind === "pasado") {
    const done = D.games.filter(g => g.state === "post"), wk = done.filter(g => marketFav(g));
    const t = tally(dayLines(D, "", 0));
    summary = done.length ? `<div class="info">El modelo acertó el ganador en <b>${done.filter(g => modelFav(g) === winner(g)).length} de ${done.length}</b> partidos${wk.length ? ` y el mercado en <b>${wk.filter(g => marketFav(g) === winner(g)).length} de ${wk.length}</b>` : ""}.${t.n ? ` De las líneas de jugador, el lado que prefería el modelo salió en ${t.a} de ${t.n} (${pct(t.a / t.n)}).` : ""} Un solo día no demuestra nada: el balance acumulado está en <a class="lnk" href="#/historial">Historial</a>.</div>` : "";
  }
  const sub = D.kind === "hoy" ? "Horarios, marcadores, probabilidad del modelo y lo que dice el mercado." : D.kind === "pasado" ? "Lo que predijo el portal ese día y lo que pasó de verdad." : "Calendario. Las proyecciones se calculan el día del partido, con las bajas y las líneas del momento.";
  el.innerHTML = pageHead("cal", "Partidos", sub) + `<div class="datebar">${nav(days[i - 1], "back")}
      <div class="datepill">${esc(relDay(date))}<small>${esc(asDate(date).toLocaleDateString("es-ES", {day: "2-digit", month: "short", year: "numeric"}).toUpperCase())}</small></div>${nav(days[i + 1], "fwd")}
      ${date !== IDX.today ? `<a class="btn" href="#/partidos">Volver a hoy</a>` : ""}<span class="sp"></span>
      ${D.kind !== "futuro" ? `<span class="sub">Ordenar por</span>${seg("fxs.sort", [["hora", "Hora"], ["discrepancia", "Discrepancia"]])}` : ""}</div>` +
    (games.length ? `<details class="league" open><summary><span><b>NBA</b> <span class="sub">Temporada ${IDX.season - 1}-${String(IDX.season).slice(2)} · ${games.length} partido${games.length === 1 ? "" : "s"}</span></span><span class="chev">${ic("chev")}</span></summary>${games.map(g => fxRow(D, g)).join("")}</details>`
      : `<div class="card">No hay partidos de la NBA en esta fecha.</div>`) + summary +
    (D.kind === "hoy" ? `<div class="info">Horas en tu zona horaria; el porcentaje es la probabilidad de victoria del modelo. El modelo de partidos no bate al mercado (log loss ${num(IDX.evidence.games ? IDX.evidence.games.log_loss.v2_elo : null, 4)} frente a ${num(IDX.evidence.games ? IDX.evidence.games.log_loss.mercado : null, 4)} en 2022-26). Úsalo para entender el partido, no para apostar contra la línea: una diferencia grande casi siempre es una noticia que el modelo no conoce.</div>` : "");
};

// ---------------------------------------------------------------- Ficha de partido
const TABS = {
  hoy: [["jugador", "Apuestas de jugador"], ["equipo", "Apuestas de equipo"], ["stats", "Estadísticas de jugadores"], ["h2h", "Cara a cara"], ["quintetos", "Quintetos"], ["modelo", "Modelo y mercado"]],
  pasado: [["resultado", "Resultado de las líneas"], ["modelo", "Modelo y mercado"]],
  futuro: [["h2h", "Cara a cara"]],
};
function formCard(abbr) {
  const t = team(abbr), f = t.form.slice(-10).reverse();
  return `<div class="card"><div class="row"><h3>${badge(abbr)} ${esc(t.name)}</h3><span class="sub">${t.w}-${t.l} · nivel #${t.rank}</span></div>
    <div style="display:flex;gap:4px;margin:8px 0;flex-wrap:wrap">${f.map(x => `<span class="wl ${x[3] > x[4] ? "w" : ""}" title="${esc(fmtDay(x[0]))}: ${x[2] ? "vs" : "@"} ${esc(x[1])} ${x[3]}-${x[4]}">${x[3] > x[4] ? "V" : "D"}</span>`).join("") || `<span class="sub">sin partidos esta temporada</span>`}</div>
    <ul class="lineup">${f.slice(0, 5).map(x => `<li><span>${esc(fmtDay(x[0], {day: "numeric", month: "short"}))} · ${x[2] ? "vs" : "@"} ${esc(x[1])}</span><span class="num"><b class="${x[3] > x[4] ? "pos" : "neg"}">${x[3] > x[4] ? "V" : "D"}</b> ${x[3]}-${x[4]}</span></li>`).join("")}</ul></div>`;
}
function h2hHtml(g) {
  const rows = (g.h2h || []).slice().reverse(), wh = rows.filter(x => (x[3] > x[4] ? x[1] : x[2]) === g.home).length;
  return `<div class="card" style="margin-bottom:12px"><h3>Últimos enfrentamientos</h3>${rows.length ? `<div class="sub" style="margin-bottom:8px">${esc(g.home_name)} ganó ${wh} de los últimos ${rows.length}; ${esc(g.away_name)}, ${rows.length - wh}.</div>
      <div class="tablewrap"><table><thead><tr><th class="l">Fecha</th><th class="l">Visitante</th><th class="c">Marcador</th><th class="l">Local</th><th class="l">Ganó</th></tr></thead><tbody>${rows.map(x => { const w = x[3] > x[4] ? x[1] : x[2];
        return `<tr><td class="l">${esc(fmtDay(x[0], {day: "numeric", month: "short", year: "numeric"}))}</td><td class="l">${badge(x[2])}</td><td class="c"><b>${x[4]} – ${x[3]}</b></td><td class="l">${badge(x[1])}</td><td class="l">${esc(w)} por ${Math.abs(x[3] - x[4])}</td></tr>`; }).join("")}</tbody></table></div>`
      : `<div class="sub">No hay enfrentamientos anteriores en los datos.</div>`}</div>
    <h2>Forma reciente (esta temporada)</h2><div class="grid">${formCard(g.away)}${formCard(g.home)}</div>
    <div class="info">Datos descriptivos: el resultado de partidos anteriores entre dos equipos dice muy poco sobre el siguiente (plantillas, bajas y descanso cambian).</div>`;
}
function lineupHtml(g) {
  const side = (abbr, s) => {
    const ps = T().players.filter(p => p.game_id === g.game_id && p.team === abbr).sort((a, b) => (b.start_rate - a.start_rate) || (b.min - a.min));
    const li = p => `<li><span><span class="pname" data-pid="${p.pid}">${esc(p.name)}</span> <span class="posb">${esc(p.pos)}</span> ${A.statusChip(p)}</span><span class="sub num">${num(p.min)} min · titular ${pct(p.start_rate)}</span></li>`;
    const start = ps.slice(0, 5), bench = ps.slice(5).sort((a, b) => b.min - a.min), inj = g.injuries[s];
    return `<div class="card"><h3>${badge(abbr)} ${esc(team(abbr).name)}</h3><div class="lbls" style="margin-top:10px">QUINTETO PROBABLE</div><ul class="lineup">${start.map(li).join("") || `<li class="mute">sin jugadores proyectados</li>`}</ul>
      <div class="lbls" style="margin-top:12px">BANQUILLO (${bench.length})</div><ul class="lineup">${bench.map(li).join("") || `<li class="mute">–</li>`}</ul>
      <div class="lbls" style="margin-top:12px">BAJAS Y DUDAS (${inj.length})</div><ul class="inj">${inj.map(i => `<li><b>${esc(i.player)}</b> <span class="chip ${i.status === "out" ? "bad" : "warn"}">${STATUS[i.status] || esc(i.status)}</span> <span class="mute">${esc(i.detail)}</span>${i.comment ? `<div class="sub">${esc(i.comment)}</div>` : ""}</li>`).join("") || `<li class="mute">sin bajas en el parte</li>`}</ul></div>`;
  };
  return `<div class="note">No son alineaciones confirmadas. El quinteto probable son los cinco jugadores disponibles que más veces han salido de titular; los minutos son los que proyecta el modelo. Un jugador en «duda» se proyecta como si jugara.</div>
    <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(380px,1fr))">${side(g.away, "away")}${side(g.home, "home")}</div>`;
}
function modelHtml(g) {
  const m = g.model, k = g.market;
  const fav = k.spread_home == null ? "sin hándicap" : (k.spread_home === 0 ? "igualado" : (k.spread_home < 0 ? g.home : g.away) + " " + (-Math.abs(k.spread_home)).toFixed(1));
  return `<div class="grid"><div class="card"><h3>De dónde sale el margen del modelo</h3><dl class="kv">
      <dt>Nivel de ${esc(g.home)} − ${esc(g.away)}</dt><dd>${sgn(m.rating_home - m.rating_away)}</dd><dt>Factor cancha</dt><dd>${sgn(m.hca)}</dd>
      <dt>Bajas y regresos</dt><dd>${sgn(m.avail_pts)}</dd><dt>Descanso</dt><dd>${sgn(m.margin - (m.rating_home - m.rating_away) - m.hca - m.avail_pts)}</dd>
      <dt>Margen esperado (local)</dt><dd><b>${sgn(m.margin)}</b> ± ${num(m.sigma)}</dd><dt>Gana ${esc(g.home)}</dt><dd>${pct(m.prob_home)}</dd>
      <dt>P(${esc(g.home)} cubre el hándicap)</dt><dd>${m.p_cover_home == null ? "–" : pct(m.p_cover_home)}</dd></dl></div>
    <div class="card"><h3>Mercado (${esc(k.provider || "sin cuotas")})</h3><dl class="kv">
      <dt>Favorito</dt><dd>${esc(fav)}${k.prob_home != null ? " · gana " + esc(g.home) + " " + pct(k.prob_home) : ""}</dd>
      <dt>Hándicap de apertura</dt><dd>${k.spread_home_open == null ? "–" : esc(g.home) + " " + sgn(k.spread_home_open)}</dd>
      <dt>Total de puntos</dt><dd>${k.total == null ? "–" : num(k.total) + (k.over_odds ? ` · más ${num(k.over_odds, 2)} / menos ${num(k.under_odds, 2)}` : "")}</dd>
      <dt>Ganador (cuota)</dt><dd>${k.ml_home ? esc(g.away) + " " + num(k.ml_away, 2) + " · " + esc(g.home) + " " + num(k.ml_home, 2) : "–"}</dd>
      <dt>Hándicap (cuota)</dt><dd>${k.spread_odds_home ? esc(g.away) + " " + sgn(-k.spread_home) + " a " + num(k.spread_odds_away, 2) + " · " + esc(g.home) + " " + sgn(k.spread_home) + " a " + num(k.spread_odds_home, 2) : "–"}</dd>
      <dt>Diferencia modelo − mercado</dt><dd>${g.gap_pts == null ? "–" : "el modelo ve a " + esc(g.gap_pts >= 0 ? g.home : g.away) + " " + num(Math.abs(g.gap_pts)) + " pts mejor"}</dd>
      ${g.rest ? `<dt>Días de descanso</dt><dd>${esc(g.away)} ${g.rest.away} · ${esc(g.home)} ${g.rest.home}</dd>` : ""}</dl></div></div>`;
}
function resultHtml(D, g) {
  const minEdge = parseFloat(ui.pb.minEdge), lines = dayLines(D, g.game_id, minEdge).sort((a, b) => b.mk.eval.edge - a.mk.eval.edge), t = tally(lines);
  const chip = {acierto: "good", fallo: "bad", anulada: "", empate: ""};
  return `<div class="rtools left"><span class="sub">Ventaja mínima</span><div style="min-width:260px">${seg("pb.minEdge", IDX.thresholds.map(x => [x, (100 * parseFloat(x)).toFixed(0) + " pp"]))}</div></div>
    <div class="info" style="margin-top:0">${t.n ? `Con ventaja de al menos ${(100 * minEdge).toFixed(0)} pp, el lado que prefería el modelo salió en <b>${t.a} de ${t.n}</b> líneas (${pct(t.a / t.n)}).` : "Ninguna línea puntuada con este filtro."} Las líneas de jugadores que no jugaron se anulan.</div>
    <div class="tablewrap"><table><thead><tr><th class="l">Jugador</th><th class="l">Línea</th><th>Cuota</th><th>Proyección</th><th>P modelo</th><th>Ventaja</th><th>Real</th><th class="l">Resultado</th></tr></thead><tbody>${lines.map(({p, m, mk, res}) => {
      const e = mk.eval, over = e.side === "over";
      return `<tr><td class="l"><b>${esc(p.name)}</b> <span class="mute">${esc(p.team)}</span></td><td class="l">${over ? "Más" : "Menos"} de ${num(mk.line.value)} ${esc(L[m])}</td><td>${num(over ? mk.line.over : mk.line.under, 2)}</td>
        <td>${num(mk.mu)}</td><td>${pct(over ? e.p_over : e.p_under)}</td><td>${pp(e.edge)}</td><td><b>${mk.y == null ? "–" : mk.y}</b></td><td class="l"><span class="chip ${chip[res]}">${res}</span></td></tr>`;
    }).join("") || `<tr><td colspan="8" class="l mute">Sin líneas guardadas para este partido.</td></tr>`}</tbody></table></div>`;
}
A.pages.partido = (el, r) => {
  const D = NBA.days[r.a], g = D && D.games.find(x => x.game_id === r.b);
  if (!g) { el.innerHTML = `<div class="card">Ese partido no está en los datos. <a class="lnk" href="#/partidos">Volver a los partidos</a></div>`; return; }
  const kind = D.kind, tabs = TABS[kind], m = g.model, k = g.market || {};
  const tab = tabs.some(t => t[0] === ui.fx.tab) ? ui.fx.tab : tabs[0][0];
  const done = kind === "pasado" ? g.state === "post" : (kind === "hoy" && g.state !== "pre");
  const tsub = (abbr, p, s) => kind === "futuro" ? `${record(abbr) || "sin partidos"} · nivel #${team(abbr).rank}` :
    `${kind === "pasado" ? "el modelo le daba" : "gana"} ${pct(p)}${kind === "hoy" ? " según el modelo" : ""}${g.rest && g.rest[s] <= 1 ? " · jugó ayer" : ""}`;
  const tm = (abbr, name, p, s) => `<div class="tm"><span class="crest" style="--tc:${COLORS[abbr] || "var(--bar)"}">${esc(abbr)}</span><div class="big">${esc(name)}</div><div class="sub">${tsub(abbr, p, s)}</div></div>`;
  const ph = m ? m.prob_home : null;
  let foot = "";
  if (m) {
    const [txt, cls] = gapReading(g);
    const fav = k.spread_home == null ? "sin hándicap" : (k.spread_home === 0 ? "igualado" : (k.spread_home < 0 ? g.home : g.away) + " " + (-Math.abs(k.spread_home)).toFixed(1));
    foot = `<div class="foot"><span>Modelo: <b>${esc((m.margin >= 0 ? g.home : g.away) + " por " + Math.abs(m.margin).toFixed(1))}</b></span><span>Mercado: <b>${esc(fav)}</b></span><span>Total: <b>${k.total == null ? "–" : num(k.total)}</b></span><span class="chip ${cls}">${txt}</span></div>`;
  }
  el.innerHTML = `<div class="hero">
      <div class="top"><span><a class="lnk" href="#/partidos/${D.date}">Partidos</a> · NBA</span><span>Jornada del ${esc(fmtDay(D.date))}${g.tip_utc ? " · " + esc(tipHour(g)) + " h (tu hora)" : ""}</span></div>
      <div class="mid">${tm(g.away, g.away_name, ph == null ? null : 1 - ph, "away")}
        <div class="ko"><small>${done ? (g.state === "in" ? esc(g.detail || "").toUpperCase() : "FINAL") : "INICIO"}</small>${done ? g.away_pts + " – " + g.home_pts : esc(tipHour(g))}<small>@</small></div>
        ${tm(g.home, g.home_name, ph, "home")}</div>${foot}</div>
    <div class="pills">${tabs.map(t => `<button data-set="fx.tab" data-v="${t[0]}" class="${tab === t[0] ? "on" : ""}">${t[1]}</button>`).join("")}</div><div id="fxbody"></div>`;
  $("#fxbody").innerHTML = tab === "jugador" ? A.playerBetsHtml(g.game_id) : tab === "equipo" ? A.teamBetsHtml(g.game_id) : tab === "stats" ? A.statsHtml(g.game_id) :
    tab === "h2h" ? h2hHtml(g) + (kind === "futuro" ? `<div class="info">Las apuestas de jugador, las proyecciones y el desglose del modelo de este partido aparecerán el día del partido.</div>` : "") :
    tab === "quintetos" ? lineupHtml(g) : tab === "resultado" ? resultHtml(D, g) : modelHtml(g);
};
})();
