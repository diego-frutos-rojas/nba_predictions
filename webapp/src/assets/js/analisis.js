/* Páginas de análisis sobre la jornada de hoy: apuestas de jugador, apuestas de equipo, proyecciones, buscador de props y favoritos.
   playerBetsHtml / teamBetsHtml / statsHtml se reutilizan en las pestañas de la ficha de partido (con el partido fijado). */
(function () {
"use strict";
const A = window.App, {IDX, esc, pct, pp, num, sgn, L, POS, ic, ui, T, team, gameOf, tipTime, tipHour, gameLabel, badge, lineOf, evalOf, statVal, history,
  hitInfo, sideOk, statusChip, star, seg, tog, chk, sel, gameSelect, numIn, segbar, rate, tiles, pageHead, updated} = A;
const thrLabel = t => (100 * parseFloat(t)).toFixed(0) + " pp";
const vs = p => `${esc(p.team)} ${p.home ? "vs" : "@"} ${esc(p.opp)}`;

// ---------------------------------------------------------------- Apuestas de jugador
const pbHist = () => ({win: parseInt(ui.pb.win, 10), minMin: ui.pb.min20 ? 20 : 0, days: parseFloat(ui.pb.lastDays) || 0});
function betOf(p, m, e, g) {
  const over = e.side === "over", rows = history(p, pbHist()), ok = sideOk(e.line.value, e.side);
  return {p, m, e, g, over, rows, ok, price: over ? e.line.over : e.line.under, prob: over ? e.p_over : e.p_under, fair: over ? e.fair_over : 1 - e.fair_over,
    hi: hitInfo(rows.map(r => statVal(r, m)), ok), key: "p|" + p.pid + "|" + m,
    flags: [].concat(p.status !== "available" ? ["duda"] : [], e.edge >= IDX.big_edge ? ["revisar"] : [])};
}
function betList(fixed) {
  const f = ui.pb, q = f.q.trim().toLowerCase(), out = [];
  for (const p of T().players) {
    const g = gameOf(IDX.today, p.game_id);
    if (!g || g.state !== "pre") continue;                    // no se "predice" un partido en juego o terminado
    if (fixed ? p.game_id !== fixed : (f.game && p.game_id !== f.game)) continue;
    if (q && !p.name.toLowerCase().includes(q) && !p.team.toLowerCase().includes(q)) continue;
    if (f.starters && p.start_rate < 0.5) continue;
    for (const m of IDX.markets) {
      if (f.market !== "all" && m !== f.market) continue;
      const e = evalOf(p, m);
      if (e && e.edge != null) out.push(betOf(p, m, e, g));
    }
  }
  const lo = parseFloat(f.minOdds), hi = parseFloat(f.maxOdds), mh = parseFloat(f.minHit);
  const res = out.filter(x => x.e.edge >= parseFloat(f.minEdge) && (f.side === "all" || x.e.side === f.side) && (!f.hideDoubt || !x.flags.includes("duda")) &&
    (isNaN(lo) || x.price >= lo) && (isNaN(hi) || x.price <= hi) && (isNaN(mh) || (x.hi.n && 100 * x.hi.h / x.hi.n >= mh)));
  const key = {edge: x => x.e.edge, prob: x => x.prob, hit: x => (x.hi.n ? x.hi.h / x.hi.n : 0) + x.hi.st / 1000, odds: x => x.price}[f.sort];
  return res.sort((a, b) => key(b) - key(a));
}
const betName = x => `${x.over ? "Más" : "Menos"} de ${num(x.e.line.value)} ${esc(L[x.m])}`;
function betCard([x, more]) {
  const {p, m, e, g, hi} = x, bt = (IDX.evidence.props || {}).apuestas || {}, b = bt[edgeBucket(e.edge, IDX.thresholds)];
  return `<article class="bet">
    <div class="row"><a href="#/partido/${IDX.today}/${esc(g.game_id)}">${badge(g.away)} @ ${badge(g.home)}</a><span class="row"><span class="mute">${esc(tipTime(g))}</span>${star(x.key)}</span></div>
    <div><div class="row"><div><span class="who pname" data-pid="${p.pid}">${esc(p.name)}</span> <span class="posb" title="${POS[p.pos] || ""}">${esc(p.pos)}</span><div class="sub">${vs(p)} · ${num(p.min)} min proyectados</div></div>
        <div class="odds"><small>Cuota${e.line.manual ? " (tuya)" : ""}</small><b>${num(x.price, 2)}</b></div></div>
      <div class="row" style="margin-top:8px"><span class="mk">${betName(x)}</span><span>${x.flags.map(f => `<span class="chip warn">${f}</span>`).join(" ") || `<span class="sub">${p.start_rate >= 0.5 ? "titular habitual" : "suplente habitual"}</span>`}</span></div></div>
    <div class="row"><div><small>Acierto · últimos ${hi.n}</small><span class="bigp">${hi.n ? pct(hi.h / hi.n) : "–"}</span> <span class="sub">${hi.h} de ${hi.n}</span></div>
      <div style="text-align:right"><small>Racha actual</small><span class="bigp">${hi.st}</span> <span class="sub">seguidos</span></div></div>
    <div><div class="row"><span><small>Probabilidad del modelo</small>${segbar(x.prob)} <b>${pct(x.prob)}</b></span><span style="text-align:right"><small>Casa sin margen ${pct(x.fair)}</small><b class="${e.edge >= 0.06 ? "pos" : ""}">${pp(e.edge)}</b></span></div>
      <div class="sub" style="margin-top:6px">Proyección ${num(p.markets[m].mu)} · valor esperado ${sgn(100 * e.ev)} %${more ? ` · y ${more} mercado${more > 1 ? "s" : ""} más de este jugador` : ""}</div></div>
    <div><div class="row"><small>Últimos partidos · el más reciente primero</small><small><span class="pos">■</span> cumple</small></div>${tiles(x.rows, m, x.ok)}</div>
    <div class="sub">Historial de este nivel de ventaja: ${b && b.n ? `${pct(b.acierto, 1)} de acierto, rentabilidad ${sgn(100 * b.roi)} % [${sgn(100 * b.lo)}; ${sgn(100 * b.hi)}] en ${b.n} apuestas simuladas` : "sin datos"}</div>
  </article>`;
}
function betTable(list) {
  return `<div class="tablewrap"><table><thead><tr><th></th><th class="l">Jugador</th><th class="l">Apuesta</th><th>Cuota</th><th>P modelo</th><th>P casa</th><th>Ventaja</th><th>Acierto</th><th>Racha</th><th class="l">Últimos</th></tr></thead><tbody>${list.map(([x]) =>
    `<tr><td>${star(x.key)}</td><td class="l"><span class="pname" data-pid="${x.p.pid}">${esc(x.p.name)}</span> <span class="mute">${vs(x.p)}</span> ${x.flags.map(f => `<span class="chip warn">${f}</span>`).join(" ")}</td>
      <td class="l">${betName(x)}</td><td>${num(x.price, 2)}</td><td>${pct(x.prob)}</td><td>${pct(x.fair)}</td><td class="${x.e.edge >= 0.06 ? "pos" : ""}">${pp(x.e.edge)}</td><td>${rate(x.hi.h, x.hi.n)}</td><td>${x.hi.st}</td>
      <td class="l"><span class="dots">${x.rows.slice().reverse().map(r => `<i class="${x.ok(statVal(r, x.m)) ? "h" : ""}"></i>`).join("")}</span></td></tr>`).join("")}</tbody></table></div>`;
}
function evidenceRow(x, label) {
  if (!x || !x.n) return `<tr><td>${label}</td><td colspan="3" class="mute">sin datos</td></tr>`;
  return `<tr><td>${label}</td><td>${x.n}</td><td>${pct(x.acierto, 1)}</td><td class="${x.roi >= 0 ? "pos" : "neg"}">${sgn(100 * x.roi)} %${x.lo != null ? ` <span class="mute">[${sgn(100 * x.lo)}; ${sgn(100 * x.hi)}]</span>` : ""}</td></tr>`;
}
function playerBetsHtml(fixed) {
  const f = ui.pb, ev = IDX.evidence.props || {}, bt = ev.apuestas || {}, tr = (IDX.track && IDX.track.picks) || {}, thr = IDX.thresholds;
  if (fixed && gameOf(IDX.today, fixed).state !== "pre") return `<div class="card">El partido ya ha empezado: no se muestran apuestas de un partido en juego o terminado.</div>`;
  let list = betList(fixed);
  // si un mercado de un jugador es sospechoso, lo son todos los suyos (comparten la misma causa)
  const susPid = new Set(list.filter(x => x.flags.includes("revisar")).map(x => x.p.pid));
  const sus = list.filter(x => susPid.has(x.p.pid)); list = list.filter(x => !susPid.has(x.p.pid));
  const group = l => { if (!f.onePer) return l.map(x => [x, 0]); const seen = {}, out = []; for (const x of l) { if (seen[x.p.pid] == null) { seen[x.p.pid] = out.length; out.push([x, 0]); } else out[seen[x.p.pid]][1]++; } return out; };
  const show = l => f.compact ? betTable(l) : `<div class="bets">${l.map(betCard).join("")}</div>`;
  const gl = group(list), gs = group(sus);
  return `<div class="note"><b>Léelo antes de apostar.</b> «Ventaja» es lo que el modelo cree saber frente a la casa, no un beneficio asegurado. En ${ev.partidos || "–"} partidos de esta temporada (${esc(ev.desde || "")} a ${esc(ev.hasta || "")}) seguir al modelo a los precios de DraftKings dio un resultado cercano a cero, con un margen de error que incluye pérdidas. Solo mayores de 18 años; apuesta solo lo que puedas permitirte perder.
      <details><summary>Ver la evidencia por nivel de ventaja</summary><div class="tablewrap" style="margin-top:8px"><table><thead><tr><th>Ventaja mínima</th><th>Apuestas</th><th>Acierto</th><th>Rentabilidad (IC 95 %)</th></tr></thead><tbody>
      ${thr.map(t => evidenceRow(bt[t], `≥ ${thrLabel(t)} · backtest`)).join("")}${thr.map(t => evidenceRow(tr[t], `≥ ${thrLabel(t)} · sitio en vivo`)).join("")}</tbody></table></div></details></div>
    <div class="tabs">${[["all", "Todas"]].concat(IDX.markets.map(k => [k, L[k]])).map(t => `<button data-set="pb.market" data-v="${t[0]}" class="${f.market === t[0] ? "on" : ""}">${esc(t[1])}</button>`).join("")}</div>
    <div class="split"><div><div class="fhead"><span>Filtros</span><button data-reset="pb">Restablecer</button></div><div class="filters">
        <label class="f">Buscar</label><input type="search" id="pbq" data-live="pb.q" placeholder="Jugador o equipo" value="${esc(f.q)}">
        ${chk("pb.starters", "Solo titulares habituales")}${chk("pb.hideDoubt", "Ocultar jugadores en duda")}
        <hr>${fixed ? "" : `<label class="f">Partido</label>${gameSelect("pb.game", "Todos los partidos")}`}
        <label class="f">Lado</label>${seg("pb.side", [["all", "Todos"], ["over", "Más"], ["under", "Menos"]])}
        <label class="f">Ventaja mínima</label>${seg("pb.minEdge", thr.map(t => [t, thrLabel(t)]))}
        <hr><label class="f">Partidos recientes</label>${seg("pb.win", [["5", "5"], ["10", "10"], ["15", "15"], ["20", "20"]])}
        <div class="sub" style="margin-top:6px">Ventana fija para todos: no se busca la que mejor queda para cada jugador.</div>
        ${chk("pb.min20", "Solo partidos de 20+ minutos")}
        <label class="f">Jugados en los últimos (días)</label>${numIn("pb.lastDays", "Cualquiera")}
        <label class="f">Acierto mínimo (%)</label>${numIn("pb.minHit", "Cualquiera")}
        <hr><div class="two"><div><label class="f">Cuota mín.</label>${numIn("pb.minOdds", "–", 0.05)}</div><div><label class="f">Cuota máx.</label>${numIn("pb.maxOdds", "–", 0.05)}</div></div>
        <hr>${chk("pb.onePer", "Una apuesta por jugador")}</div>
        <details style="margin-top:10px"><summary>¿Cómo se calcula la probabilidad del modelo?</summary><div class="sub" style="margin-top:6px">Minutos proyectados × ritmo por minuto, corregidos por rival, bajas y contexto, con una distribución ajustada a la variabilidad real de cada estadística. El detalle está en <a class="lnk" href="#/metodologia">Metodología</a>.</div></details></div>
      <div><div class="rtools"><span class="sub">Ordenar por</span>${sel("pb.sort", [["edge", "Ventaja"], ["prob", "Probabilidad del modelo"], ["hit", "Acierto reciente"], ["odds", "Cuota"]])}
          <button class="btn ${f.compact ? "on" : ""}" data-toggle="pb.compact">${ic("list")} Vista compacta</button></div>
        <div class="sub" style="margin-bottom:10px">${gl.length} apuesta${gl.length === 1 ? "" : "s"} con este filtro</div>
        ${gl.length ? show(gl) : `<div class="card mute">Ninguna apuesta con este filtro. Puede que aún no haya líneas: vuelve a generar el sitio más cerca de los partidos.</div>`}
        ${gs.length ? `<h2>Discrepancias sospechosas (${gs.length})</h2><div class="sub" style="margin-bottom:10px">Ventaja de más de ${(100 * IDX.big_edge).toFixed(0)} pp: casi siempre hay una noticia que el modelo no conoce (vuelta de lesión, límite de minutos, cambio de papel). Compruébalo antes de fiarte.</div>${show(gs)}` : ""}
      </div></div>`;
}

// ---------------------------------------------------------------- Apuestas de equipo
// Forma reciente de un equipo: filas [fecha, rival, en casa, a favor, en contra, hándicap propio, total] (ver nba_model/site.py).
function formRate(abbr, cond, valid) {
  const rows = team(abbr).form.slice(-parseInt(ui.tb.win, 10)).filter(valid || (() => true));
  return {t: abbr, h: rows.filter(cond).length, n: rows.length};
}
function teamRows(fixed, all) {
  const f = ui.tb, out = [], hasLine = x => x[5] != null;
  T().games.forEach((g, gi) => {
    if (fixed ? g.game_id !== fixed : (!all && f.game && g.game_id !== f.game)) return;
    (g.bets || []).forEach((b, bi) => {
      const tm = b.side === "home" ? g.home : g.away, op = b.side === "home" ? g.away : g.home;
      let name, fa, fb;
      if (b.kind === "ganador") { name = "Gana " + tm; fa = formRate(tm, x => x[3] > x[4]); fb = formRate(op, x => x[3] < x[4]); }
      else if (b.kind === "handicap") { name = tm + " " + sgn(b.line); fa = formRate(tm, x => x[3] - x[4] + x[5] > 0, hasLine); fb = formRate(op, x => x[3] - x[4] + x[5] < 0, hasLine); }
      else { const over = b.side === "over", c = x => over ? x[3] + x[4] > b.line : x[3] + x[4] < b.line;
        name = (over ? "Más de " : "Menos de ") + num(b.line) + " puntos"; fa = formRate(g.home, c); fb = formRate(g.away, c); }
      out.push({g, b, name, fa, fb, ord: gi * 10 + bi, key: "g|" + g.game_id + "|" + b.kind + "|" + b.side});
    });
  });
  if (all) return out;
  const lo = parseFloat(f.minOdds), hi = parseFloat(f.maxOdds), mt = parseFloat(f.minTeam), mo = parseFloat(f.minOpp);
  const r = x => x.n ? 100 * x.h / x.n : -1;
  const res = out.filter(x => (f.market === "all" || x.b.kind === f.market) && (isNaN(lo) || (x.b.price != null && x.b.price >= lo)) && (isNaN(hi) || (x.b.price != null && x.b.price <= hi)) &&
    (isNaN(mt) || r(x.fa) >= mt) && (isNaN(mo) || r(x.fb) >= mo));
  const key = {hora: x => -x.ord, modelo: x => x.b.p_model == null ? -1 : x.b.p_model, forma: x => (x.fa.n + x.fb.n ? (x.fa.h + x.fb.h) / (x.fa.n + x.fb.n) : -1), cuota: x => x.b.price || 0}[f.sort];
  return res.sort((a, b) => key(b) - key(a));
}
function teamTable(rows) {
  const form = x => `<td class="band">${x.n ? `${badge(x.t)} ${rate(x.h, x.n)}` : `<span class="mute">–</span>`}</td>`;
  return `<div class="tablewrap"><table><thead><tr><th></th><th class="l">Partido</th><th class="l">Mercado</th><th>Cuota</th><th>P modelo</th><th title="Probabilidad de la casa sin su margen">P casa</th><th title="Con qué frecuencia le ha salido este resultado al equipo en sus últimos partidos">Forma equipo</th><th title="Con qué frecuencia le ha salido al rival el resultado que conviene a esta apuesta">Forma rival</th></tr></thead><tbody>${rows.map(x => {
    const g = x.g, b = x.b;
    return `<tr><td>${star(x.key)}</td><td class="l"><a href="#/partido/${IDX.today}/${esc(g.game_id)}"><b>${esc(gameLabel(g))}</b></a><div class="sub">${esc(tipTime(g))}</div></td><td class="l"><b>${esc(x.name)}</b><div class="sub">${{ganador: "Ganador", handicap: "Hándicap", total: "Total de puntos"}[b.kind]}</div></td>
      <td><b>${b.price ? num(b.price, 2) : "–"}</b></td><td>${b.p_model == null ? `<span class="mute">sin modelo</span>` : `${segbar(b.p_model, 10)} ${pct(b.p_model)}`}</td><td>${b.p_market == null ? "–" : pct(b.p_market)}</td>${form(x.fa)}${form(x.fb)}</tr>`;
  }).join("") || `<tr><td colspan="8" class="mute l">Sin mercados para este filtro.</td></tr>`}</tbody></table></div>`;
}
function teamBetsHtml(fixed) {
  return `<div class="note"><b>No son recomendaciones.</b> En 2022-26 apostar al hándicap siguiendo al modelo perdió entre un 6 % y un 10 % (peor que apostar al azar), y no hay modelo de totales: ahí se enseña solo el precio y la forma. La «forma» describe los últimos partidos; la casa ya la conoce.</div>
    <div class="tabs">${[["all", "Todos"], ["ganador", "Ganador"], ["handicap", "Hándicap"], ["total", "Total de puntos"]].map(t => `<button data-set="tb.market" data-v="${t[0]}" class="${ui.tb.market === t[0] ? "on" : ""}">${t[1]}</button>`).join("")}</div>
    <div class="split"><div><div class="fhead"><span>Filtros</span><button data-reset="tb">Restablecer</button></div><div class="filters">
      ${fixed ? "" : `<label class="f">Partido</label>${gameSelect("tb.game", "Todos los partidos")}`}
      <label class="f">Partidos recientes</label>${seg("tb.win", [["5", "5"], ["10", "10"], ["15", "15"], ["20", "20"]])}
      <div class="sub" style="margin-top:6px">Solo partidos de esta temporada.</div>
      <label class="f">Forma mínima del equipo (%)</label>${numIn("tb.minTeam", "Cualquiera")}
      <label class="f">Forma mínima del rival (%)</label>${numIn("tb.minOpp", "Cualquiera")}
      <hr><div class="two"><div><label class="f">Cuota mín.</label>${numIn("tb.minOdds", "–", 0.05)}</div><div><label class="f">Cuota máx.</label>${numIn("tb.maxOdds", "–", 0.05)}</div></div></div>
      <details style="margin-top:10px"><summary>¿Qué es la forma?</summary><div class="sub" style="margin-top:6px">Ganador: partidos ganados por el equipo y perdidos por el rival. Hándicap: partidos en los que el equipo cubrió su hándicap de cierre y el rival no cubrió el suyo. Total: partidos de cada equipo por encima (o por debajo) de esta cifra.</div></details></div>
    <div><div class="rtools"><span class="sub">Ordenar por</span>${sel("tb.sort", [["hora", "Partido"], ["modelo", "Probabilidad del modelo"], ["forma", "Forma combinada"], ["cuota", "Cuota"]])}</div>${teamTable(teamRows(fixed))}</div></div>`;
}

// ---------------------------------------------------------------- Proyecciones (tabla con líneas manuales)
function statsHtml(fixed) {
  const f = ui.st, m = f.market, q = f.q.trim().toLowerCase(), game = fixed || f.game;
  const rows = T().players.filter(p => (!game || p.game_id === game) && (!q || p.name.toLowerCase().includes(q) || p.team.toLowerCase().includes(q))).map(p => ({p, mk: p.markets[m], e: evalOf(p, m)}));
  const key = {name: r => r.p.name, min: r => r.p.min, mu: r => r.mk.mu, l5: r => r.mk.l5, l10: r => r.mk.l10, season: r => r.mk.season,
    def: r => r.mk.def, line: r => r.e ? r.e.line.value : null, pover: r => r.e ? r.e.p_over : null, edge: r => r.e && r.e.edge != null ? r.e.edge : null,
    diff: r => r.e ? r.mk.mu - r.e.line.value : null}[f.sort];
  rows.sort((a, b) => { const x = key(a), y = key(b); if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * f.dir; });
  const th = (k, t, tip) => `<th data-sort="st.${k}" title="${esc(tip || "")}">${t}${f.sort === k ? (f.dir < 0 ? " ▾" : " ▴") : ""}</th>`;
  return `<div class="tabs">${IDX.markets.map(k => `<button data-set="st.market" data-v="${k}" class="${k === m ? "on" : ""}">${esc(L[k])}</button>`).join("")}</div>
    <div class="rtools left">${fixed ? "" : gameSelect("st.game", "Todos los partidos")}<input type="search" id="stq" data-live="st.q" placeholder="Buscar jugador o equipo" value="${esc(f.q)}"></div>
    <div class="sub" style="margin-bottom:8px">Escribe tu propia línea y cuotas (decimales) de tu casa en las casillas: la probabilidad y la ventaja se recalculan al momento y se guardan en este navegador. Pulsa el nombre para ver el detalle.</div>
    <div class="tablewrap"><table><thead><tr>
      <th></th>${th("name", "Jugador")}${th("min", "Min", "Minutos proyectados")}${th("mu", "Proy.", "Media proyectada por el modelo")}
      ${th("l5", "Últ. 5")}${th("l10", "Últ. 10")}${th("season", "Temp.")}${th("def", "Rival", "Lo que concede el rival en esta estadística frente a la media de la liga")}
      ${th("line", "Línea")}<th>Más</th><th>Menos</th>${th("diff", "Proy.−línea")}${th("pover", "P(más)")}<th title="Partidos recientes por encima de la línea">Recientes</th>${th("edge", "Ventaja", "P del modelo menos P de la casa sin margen, para el lado que prefiere el modelo")}
    </tr></thead><tbody>${rows.map(({p, mk, e}) => {
      const k = p.pid + "|" + m, ln = e ? e.line : null, man = A.manual[k] || {};
      const inp = (fl, v, step) => `<input type="number" step="${step}" min="0" data-k="${k}" data-f="${fl}" class="${man[fl] != null ? "manual" : ""}" value="${v == null ? "" : v}">`;
      const edge = e && e.edge != null ? `<span class="chip ${e.edge >= 0.06 ? "good" : ""}">${e.side === "over" ? "más" : "menos"} ${pp(e.edge)}</span>` : "–";
      const dots = e ? `<span class="dots" title="${mk.last.filter(v => v > ln.value).length} de ${mk.last.length} por encima">${mk.last.map(v => `<i class="${v > ln.value ? "h" : ""}"></i>`).join("")}</span>` : "–";
      return `<tr><td>${star("p|" + k)}</td><td class="l"><span class="pname" data-pid="${p.pid}">${esc(p.name)}</span> <span class="mute">${vs(p)}</span> ${statusChip(p)}</td>
        <td>${num(p.min)}</td><td><b>${num(mk.mu)}</b></td><td>${num(mk.l5)}</td><td>${num(mk.l10)}</td><td>${num(mk.season)}</td>
        <td class="${mk.def > 0.03 ? "pos" : mk.def < -0.03 ? "neg" : "mute"}">${sgn(100 * mk.def, 0)} %</td>
        <td>${inp("line", ln ? ln.value : null, 0.5)}</td><td>${inp("over", ln ? ln.over : null, 0.01)}</td><td>${inp("under", ln ? ln.under : null, 0.01)}</td>
        <td>${e ? sgn(mk.mu - ln.value) : "–"}</td><td>${e ? pct(e.p_over) : "–"}</td><td>${dots}</td><td>${edge}</td></tr>`;
    }).join("") || `<tr><td colspan="15" class="mute l">Sin jugadores para este filtro.</td></tr>`}</tbody></table></div>
    <div class="rtools left" style="margin-top:10px"><button class="btn small" id="clearman">Borrar mis líneas manuales</button><span class="sub">Cuotas en formato decimal. «Rival» en verde = el rival concede más de lo normal.</span></div>`;
}

// ---------------------------------------------------------------- Buscador de props
function searchRows() {
  const f = ui.ps, n = parseFloat(f.n), minRate = parseFloat(f.minRate), out = [];
  if (isNaN(n)) return null;
  const o = {win: parseInt(f.win, 10), minMin: parseFloat(f.minMin) || 0, venue: f.venue, role: f.role, allTeams: f.allTeams};
  for (const p of T().players) {
    const g = gameOf(IDX.today, p.game_id);
    if (!g || (f.games.length && !f.games.includes(p.game_id)) || (f.hideStarted && g.state !== "pre")) continue;
    if (!f.pos.includes(p.pos) || (f.hideDoubt && p.status !== "available")) continue;
    const rows = history(p, o);
    if (!rows.length) continue;
    const vals = rows.map(r => statVal(r, f.stat)), h = vals.filter(v => v >= n).length, avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (f.mode === "tasa" ? 100 * h / vals.length < minRate : avg < n) continue;
    out.push({p, g, mk: p.markets[f.stat], rows, h, avg, pm: sideEval(p.markets[f.stat].sv, n - 0.5, null, null).p_over});    // P(X >= n) = P(X > n - 0,5)
  }
  return out.sort((a, b) => f.mode === "tasa" ? (b.h / b.rows.length - a.h / a.rows.length) || (b.pm - a.pm) : b.avg - a.avg);
}
A.pages.buscador = el => {
  const f = ui.ps, rows = searchRows(), lab = (L[f.stat] || "").toLowerCase(), n = parseFloat(f.n);
  const res = rows == null ? `<div class="card"><h3>Elige una estadística y una cifra</h3><div class="sub">Por ejemplo: «Puntos», 20 o más, en al menos el 60 % de los últimos 10 partidos. El buscador repasa a todos los jugadores de la jornada (${T().players.length}).</div></div>`
    : `<div class="sub" style="margin-bottom:10px">${rows.length} jugador${rows.length === 1 ? "" : "es"} con ${f.mode === "tasa" ? `${esc(f.n)} o más ${esc(lab)} en al menos el ${esc(f.minRate)} % de sus últimos ${esc(f.win)} partidos` : `una media de ${esc(f.n)} o más ${esc(lab)} en sus últimos ${esc(f.win)} partidos`}</div>
      <div class="tablewrap"><table><thead><tr><th></th><th class="l">Jugador</th><th class="l">Partido</th><th>Min proy.</th><th>Acierto</th><th class="l">Últimos (reciente primero)</th><th>Media</th><th>Proyección</th><th title="Probabilidad del modelo de llegar a esa cifra esta noche">P modelo</th><th>Línea casa</th></tr></thead><tbody>${rows.map(r => {
        const ln = lineOf(r.p, f.stat);
        return `<tr><td>${star("p|" + r.p.pid + "|" + f.stat)}</td><td class="l"><span class="pname" data-pid="${r.p.pid}">${esc(r.p.name)}</span> <span class="mute">${esc(r.p.pos)} · ${esc(r.p.team)}</span> ${statusChip(r.p)}</td>
          <td class="l"><a href="#/partido/${IDX.today}/${esc(r.g.game_id)}">${esc(gameLabel(r.g))}</a></td><td>${num(r.p.min)}</td><td>${rate(r.h, r.rows.length)}</td>
          <td class="l">${tiles(r.rows, f.stat, v => v >= n, true)}</td><td>${num(r.avg)}</td><td><b>${num(r.mk.mu)}</b></td><td>${pct(r.pm)}</td><td>${ln ? num(ln.value) : "–"}</td></tr>`;
      }).join("") || `<tr><td colspan="10" class="mute l">Ningún jugador cumple el criterio. Prueba con una cifra o un porcentaje más bajos.</td></tr>`}</tbody></table></div>
      <div class="info">El acierto reciente describe lo que ya pasó en pocos partidos; no es una probabilidad. Compáralo con «P modelo», que tiene en cuenta minutos, rival y bajas, y recuerda que la casa ya conoce estas rachas.</div>`;
  el.innerHTML = pageHead("search", "Buscador de props", "Encuentra jugadores que cumplen tu criterio en sus últimos partidos: puntos, rebotes, asistencias, triples y combinadas.") + `<div class="split wide"><div class="filters">
      <div class="fhead"><span>Elige partidos</span><button data-reset="ps">Restablecer</button></div><div class="row sub"><span>Hoy · sin marcar ninguno se buscan todos.</span><span>${f.games.length}/${T().games.length}</span></div>
      <div style="margin-top:8px">${T().games.map(g => `<label class="chk"><input type="checkbox" data-arr="ps.games" value="${esc(g.game_id)}" ${f.games.includes(g.game_id) ? "checked" : ""}> ${esc(gameLabel(g))} <span class="mute">${esc(tipHour(g))}</span></label>`).join("")}</div>
      <label class="f">Estadística</label>${sel("ps.stat", IDX.markets.map(k => [k, L[k]]))}
      <hr><div class="fhead"><span>Criterio</span></div><div class="sub" style="margin-bottom:8px">Cómo cuentan sus partidos recientes.</div>${seg("ps.mode", [["tasa", "Acierto"], ["media", "Media"]])}
      <div class="two"><div><label class="f">Cifra (o más)</label>${numIn("ps.n", "p. ej. 20", 1)}</div><div><label class="f">Partidos recientes</label>${sel("ps.win", ["2", "3", "4", "5", "6", "7", "8", "9", "10", "15", "20"].map(w => [w, w + " partidos"]))}</div></div>
      ${f.mode === "tasa" ? `<label class="f">Acierto mínimo: <b>${esc(f.minRate)} %</b></label><input type="range" min="0" max="100" step="10" data-ui="ps.minRate" value="${esc(f.minRate)}">` : ""}
      <hr><div class="fhead"><span>Historial del jugador</span></div><div class="sub" style="margin-bottom:8px">Qué partidos anteriores se tienen en cuenta.</div>
      <label class="f">Posiciones</label>${tog("ps.pos", [["G", "Bases"], ["F", "Aleros"], ["C", "Pívots"]])}
      <label class="f">Minutos jugados mínimos: <b>${esc(f.minMin)}</b></label><input type="range" min="0" max="36" step="2" data-ui="ps.minMin" value="${esc(f.minMin)}">
      <label class="f">Campo de los partidos anteriores</label>${tog("ps.venue", [["casa", "En casa"], ["fuera", "Fuera"]])}
      <hr><div class="fhead"><span>Más filtros</span></div>
      <label class="f">Papel en los partidos anteriores</label>${seg("ps.role", [["todos", "Todos"], ["titular", "Titular"], ["suplente", "Suplente"]])}
      ${chk("ps.allTeams", "Incluir partidos con otros equipos")}${chk("ps.hideDoubt", "Ocultar jugadores en duda")}${chk("ps.hideStarted", "Ocultar partidos empezados")}
    </div><div>${res}</div></div>`;
};

// ---------------------------------------------------------------- páginas completas y favoritos
A.pages.jugadores = el => { el.innerHTML = pageHead("user", "Apuestas de jugador", "Encuentra un jugador, compara la cuota con el modelo y revisa su forma reciente.", updated()) + playerBetsHtml(""); };
A.pages.equipos = el => { el.innerHTML = pageHead("users", "Apuestas de equipo", "Ganador, hándicap y total de cada partido: cuota de la casa, probabilidad del modelo y forma reciente de los dos equipos.", updated()) + teamBetsHtml(""); };
A.pages.proyecciones = el => { el.innerHTML = pageHead("table", "Proyecciones de jugadores", "La tabla completa de proyecciones. Escribe la línea y las cuotas de tu casa para recalcular al momento.", updated()) + statsHtml(""); };
A.pages.favoritos = el => {
  const keys = Object.keys(A.favs), cards = [], plain = [], trows = [], all = teamRows("", true);
  for (const k of keys) {
    const [t, a, b] = k.split("|");
    if (t === "p") {
      const p = T().players.find(x => String(x.pid) === a); if (!p || !p.markets[b]) continue;
      const g = gameOf(IDX.today, p.game_id), e = evalOf(p, b);
      if (e && e.edge != null) cards.push([betOf(p, b, e, g), 0]); else plain.push({p, m: b, k});
    } else { const r = all.find(x => x.key === k); if (r) trows.push(r); }
  }
  const head = `<div class="phead"><div class="l"><div class="pic">${ic("star")}</div><div><h1>Favoritos</h1><div class="sub">Lo que has marcado con la estrella en la jornada de hoy. Se guarda en este navegador.</div></div></div>${keys.length ? `<button class="btn small" id="clearfav">Vaciar favoritos</button>` : ""}</div>`;
  if (!cards.length && !plain.length && !trows.length) { el.innerHTML = head + `<div class="card"><h3>Todavía no hay favoritos</h3><div class="sub">Pulsa la estrella de una apuesta de jugador, de un mercado de equipo o de una fila de las tablas para tenerla aquí a mano.</div></div>`; return; }
  el.innerHTML = head + (cards.length ? `<h2 style="margin-top:0">Apuestas de jugador (${cards.length})</h2><div class="bets">${cards.map(betCard).join("")}</div>` : "") +
    (plain.length ? `<h2>Jugadores sin precio (${plain.length})</h2><div class="tablewrap"><table><thead><tr><th></th><th class="l">Jugador</th><th class="l">Estadística</th><th>Proyección</th><th>Últ. 5</th><th>Últ. 10</th></tr></thead><tbody>${plain.map(x =>
      `<tr><td>${star(x.k)}</td><td class="l"><span class="pname" data-pid="${x.p.pid}">${esc(x.p.name)}</span> <span class="mute">${vs(x.p)}</span></td><td class="l">${esc(L[x.m])}</td><td><b>${num(x.p.markets[x.m].mu)}</b></td><td>${num(x.p.markets[x.m].l5)}</td><td>${num(x.p.markets[x.m].l10)}</td></tr>`).join("")}</tbody></table></div>` : "") +
    (trows.length ? `<h2>Mercados de equipo (${trows.length})</h2>${teamTable(trows)}` : "");
};
Object.assign(A, {playerBetsHtml, teamBetsHtml, statsHtml});
})();
