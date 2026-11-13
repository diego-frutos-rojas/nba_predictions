/* Página «Liga»: clasificación por conferencia, calendario de los próximos días, líderes y tablas de la temporada. */
(function () {
"use strict";
const A = window.App, {NBA, IDX, LG, esc, pct, num, sgn, ic, ui, team, fmtDay, tipHour, record, badge, pageHead, seg, sel} = A;
const STATS = [["pts", "Puntos"], ["reb", "Rebotes"], ["ast", "Asistencias"], ["fg3m", "Triples"], ["min", "Minutos"]];
const pctWin = t => t.w + t.l ? t.w / (t.w + t.l) : 0;
const streak = t => { const f = t.form; if (!f.length) return "–"; const w = f[f.length - 1][3] > f[f.length - 1][4]; let n = 0; for (let i = f.length - 1; i >= 0 && (f[i][3] > f[i][4]) === w; i--) n++; return (w ? "V" : "D") + n; };

function standings() {
  const conf = name => {
    const ts = Object.entries(LG.teams).filter(([, t]) => t.conf === name).map(([abbr, t]) => ({abbr, ...t}));
    ts.sort(ui.lg.order === "nivel" ? (a, b) => b.rating - a.rating : (a, b) => (pctWin(b) - pctWin(a)) || ((b.pf - b.pa) - (a.pf - a.pa)));
    return `<h2>Conferencia ${name}</h2><div class="tablewrap"><table><thead><tr><th class="c">#</th><th class="l">Equipo</th><th>V</th><th>D</th><th>%</th><th>Casa</th><th>Fuera</th><th title="Puntos a favor por partido">PF</th><th title="Puntos en contra por partido">PC</th><th>Dif.</th><th class="l">Últimos 10</th><th>Racha</th><th title="Nivel que le da el modelo, en puntos frente a un equipo medio, y su puesto entre los 30">Nivel del modelo</th></tr></thead><tbody>${ts.map((t, i) => {
      const l10 = t.form.slice(-10), w10 = l10.filter(x => x[3] > x[4]).length, st = streak(t);
      return `<tr><td class="c">${i + 1}</td><td class="l">${badge(t.abbr)} <b>${esc(t.name)}</b></td><td>${t.w}</td><td>${t.l}</td><td>${t.w + t.l ? pctWin(t).toFixed(3).replace(/^0/, "") : "–"}</td><td>${t.home[0]}-${t.home[1]}</td><td>${t.away[0]}-${t.away[1]}</td>
        <td>${num(t.pf)}</td><td>${num(t.pa)}</td><td class="${t.pf - t.pa > 0 ? "pos" : t.pf - t.pa < 0 ? "neg" : ""}">${t.pf == null ? "–" : sgn(t.pf - t.pa)}</td>
        <td class="l"><span class="dots" title="${w10}-${l10.length - w10}">${l10.map(x => `<i class="${x[3] > x[4] ? "h" : "x"}"></i>`).join("")}</span> <span class="mute">${w10}-${l10.length - w10}</span></td>
        <td class="${st[0] === "V" ? "pos" : st[0] === "D" ? "neg" : ""}">${st}</td><td><b>${sgn(t.rating)}</b> <span class="mute">#${t.rank}</span></td></tr>`; }).join("")}</tbody></table></div>`;
  };
  return `<div class="rtools left"><span class="sub">Ordenar por</span><div style="min-width:280px">${seg("lg.order", [["balance", "Balance"], ["nivel", "Nivel del modelo"]])}</div></div>${conf("Este")}${conf("Oeste")}
    <div class="info">El «nivel del modelo» es la valoración que usa el modelo de partidos (puntos frente a un equipo medio en pista neutral, sin contar bajas). Con pocos partidos jugados, el balance dice poco y el nivel arrastra todavía información de la temporada anterior.</div>`;
}
function fixtures() {
  const days = IDX.days.filter(d => d.kind !== "pasado").map(d => NBA.days[d.date]).filter(Boolean);
  return days.length ? `<div class="league">${days.map(D => `<div class="daygrp">${esc(fmtDay(D.date))}${D.kind === "hoy" ? " · hoy" : ""}</div>` + D.games.map(g =>
    `<a class="fx" href="#/partido/${D.date}/${esc(g.game_id)}"><div class="t"><div>${esc(tipHour(g))}</div></div>
      <div class="teams"><div>${badge(g.away)}<span class="tn">${esc(g.away_name)} <span class="sub">${record(g.away)}</span></span></div><div>${badge(g.home)}<span class="tn">${esc(g.home_name)} <span class="sub">${record(g.home)}</span></span></div></div>
      <div class="nums sub"><div>${g.model ? pct(1 - g.model.prob_home) : "nivel #" + team(g.away).rank}</div><div>${g.model ? pct(g.model.prob_home) : "nivel #" + team(g.home).rank}</div></div>
      <div class="x"><span class="btn small">${D.kind === "hoy" ? "Ver partido" : "Vista previa"} ${ic("arrow")}</span></div></a>`).join("")).join("")}</div>
    <div class="info">Solo los partidos de hoy tienen probabilidad del modelo: las de los días siguientes se calculan el día del partido, con las bajas y el descanso de ese momento.</div>`
    : `<div class="card">No hay calendario de los próximos días en los datos.</div>`;
}
function leaders() {
  const total = ui.lg.per === "total", maxGp = Math.max(1, ...LG.players.map(p => p.gp)), minGp = total ? 1 : Math.max(1, Math.ceil(maxGp / 2));
  const val = (p, k) => total ? Math.round(p[k] * p.gp) : p[k];
  return `<div class="rtools left"><span class="sub">Ver</span><div style="min-width:240px">${seg("lg.per", [["partido", "Por partido"], ["total", "Total"]])}</div></div>
    <div class="grid" style="grid-template-columns:repeat(auto-fill,minmax(270px,1fr))">${STATS.map(([k, lab]) => {
      const top = LG.players.filter(p => p.gp >= minGp).sort((a, b) => val(b, k) - val(a, k)).slice(0, 8);
      return `<div class="card lead"><h3>${lab}</h3><ol>${top.map((p, i) => `<li><span class="n">${i + 1}</span><span><b>${esc(p.name)}</b> <span class="mute">${esc(p.team)}</span></span><span class="v">${total ? val(p, k) : num(p[k])}</span></li>`).join("")}</ol></div>`; }).join("")}</div>
    <div class="info">${total ? "Totales de la temporada." : `Medias por partido de jugadores con al menos ${minGp} partido${minGp === 1 ? "" : "s"} jugado${minGp === 1 ? "" : "s"} (la mitad del máximo).`} Datos de las cajas de cada partido.</div>`;
}
function tables() {
  const f = ui.lg, q = f.q.trim().toLowerCase();
  const rows = LG.players.filter(p => (!f.team || p.team === f.team) && (!q || p.name.toLowerCase().includes(q))).map(p => ({...p, pra: Math.round(10 * (p.pts + p.reb + p.ast)) / 10}));
  rows.sort((a, b) => { const x = a[f.sort], y = b[f.sort]; return (x > y ? 1 : x < y ? -1 : 0) * f.dir; });
  const th = (k, t, tip, cls) => `<th data-sort="lg.${k}" class="${cls || ""}" title="${esc(tip || "")}">${t}${f.sort === k ? (f.dir < 0 ? " ▾" : " ▴") : ""}</th>`;
  const teams = Object.keys(LG.teams).sort();
  return `<div class="rtools left"><input type="search" id="lgq" data-live="lg.q" placeholder="Buscar jugador" value="${esc(f.q)}">${sel("lg.team", [["", "Todos los equipos"]].concat(teams.map(t => [t, LG.teams[t].name])))}<span class="sub">${rows.length} jugadores${rows.length > 100 ? " · se muestran los 100 primeros" : ""}</span></div>
    <div class="tablewrap"><table><thead><tr><th class="c">#</th>${th("name", "Jugador", "", "l")}${th("team", "Equipo", "", "l")}${th("pos", "Pos.", "", "c")}${th("gp", "PJ", "Partidos jugados")}${th("gs", "Tit.", "Partidos de titular")}${th("min", "Min")}${th("pts", "Pts")}${th("reb", "Reb")}${th("ast", "Ast")}${th("fg3m", "3P")}${th("pra", "P+R+A")}</tr></thead>
    <tbody>${rows.slice(0, 100).map((p, i) => `<tr><td class="c mute">${i + 1}</td><td class="l"><b>${esc(p.name)}</b></td><td class="l">${badge(p.team)}</td><td class="c">${esc(p.pos)}</td><td>${p.gp}</td><td>${p.gs}</td><td>${num(p.min)}</td><td>${num(p.pts)}</td><td>${num(p.reb)}</td><td>${num(p.ast)}</td><td>${num(p.fg3m)}</td><td>${num(p.pra)}</td></tr>`).join("") || `<tr><td colspan="12" class="l mute">Sin jugadores para este filtro.</td></tr>`}</tbody></table></div>
    <div class="info">Medias por partido de la temporada ${IDX.season - 1}-${String(IDX.season).slice(2)}, con resultados hasta el ${esc(IDX.data_through)}. Pulsa una columna para ordenar.</div>`;
}
A.needs.liga = () => ui.lg.tab === "partidos" ? IDX.days.filter(d => d.kind !== "pasado").map(d => d.date) : [];
A.pages.liga = el => {
  const tabs = [["clasificacion", "Clasificación"], ["partidos", "Partidos"], ["lideres", "Líderes"], ["tablas", "Tablas de la temporada"]];
  el.innerHTML = pageHead("trophy", "Liga · NBA", `Temporada ${IDX.season - 1}-${String(IDX.season).slice(2)}: clasificación, calendario y estadísticas de jugadores.`, "Resultados hasta el " + esc(IDX.data_through)) +
    `<div class="pills">${tabs.map(t => `<button data-set="lg.tab" data-v="${t[0]}" class="${ui.lg.tab === t[0] ? "on" : ""}">${t[1]}</button>`).join("")}</div>` +
    ({clasificacion: standings, partidos: fixtures, lideres: leaders, tablas: tables}[ui.lg.tab] || standings)();
};
})();
