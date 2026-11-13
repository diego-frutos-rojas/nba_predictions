/* Arranque: barra lateral, enrutado por «#/pagina», carga de días bajo demanda y eventos comunes. */
(function () {
"use strict";
const A = window.App, {NBA, IDX, $, esc, ic, ui, DEFAULTS, setPath, getPath, fmtDay, loadDay, openPlayer, save, load} = A;

// [id, etiqueta, icono, grupo]; `soon` = anunciado pero sin construir.
const NAV = [
  ["partidos", "Partidos", "cal", "Jornada"], ["liga", "Liga", "trophy", "Jornada"],
  ["buscador", "Buscador de props", "search", "Análisis"], ["jugadores", "Apuestas de jugador", "user", "Análisis"],
  ["equipos", "Apuestas de equipo", "users", "Análisis"], ["proyecciones", "Proyecciones", "table", "Análisis"],
  ["", "Probabilidad en directo", "pulse", "Análisis", "soon"], ["", "Combinadas", "slip", "Análisis", "soon"],
  ["historial", "Historial", "chart", "Seguimiento"], ["metodologia", "Metodología", "book", "Seguimiento"],
];
function route() {
  const h = (location.hash || "#/partidos").replace(/^#\/?/, "").split("/");
  return {page: h[0] || "partidos", a: h[1] || "", b: h[2] || ""};
}
// Días que necesita cada página antes de pintarse (hoy siempre; ver A.needs en liga.js).
A.needs.partidos = r => [r.a || IDX.today];
A.needs.partido = r => [r.a];

function renderShell(r) {
  const active = r.page === "partido" ? "partidos" : r.page, nFav = Object.keys(A.favs).length;
  let html = `<div class="brand"><span class="name">Portal <b>NBA</b></span><button class="iconbtn collapse" id="collapse" title="Plegar la navegación" aria-label="Plegar la navegación">${ic("chev")}</button></div><nav class="nav">`, grp = "";
  for (const [id, label, icon, g, soon] of NAV) {
    if (g !== grp) { html += `<div class="grp">${g}</div>`; grp = g; }
    html += soon ? `<span class="soon" title="${esc(label)} (pronto)">${ic(icon)}<span class="lbl">${esc(label)}</span><span class="tag">PRONTO</span></span>`
      : `<a href="#/${id}" class="${active === id ? "on" : ""}" title="${esc(label)}">${ic(icon)}<span class="lbl">${esc(label)}</span></a>`;
  }
  html += `</nav><div class="grow"></div><nav class="nav"><a href="#/favoritos" class="${active === "favoritos" ? "on" : ""}" title="Favoritos">${ic("star")}<span class="lbl">Favoritos</span><span class="cnt">${nFav}</span></a></nav>`;
  $("#side").innerHTML = html;
  $("#menu").innerHTML = ic("menu");
  $("#hdate").textContent = "Jornada del " + fmtDay(IDX.today, {weekday: "long", day: "numeric", month: "long", year: "numeric"});
  const T = NBA.days[IDX.today], gen = new Date(IDX.generated_utc);
  $("#hmeta").textContent = "Generado el " + gen.toLocaleString("es-ES", {day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"}) +
    " · resultados hasta el " + IDX.data_through + (T ? " · " + T.games.length + " partidos · " + T.players.length + " jugadores proyectados" : "");
  $("#warnings").innerHTML = IDX.warnings.map(w => `<div class="note">${esc(w)}</div>`).join("");
}
const failed = {};
function render() {
  const r = route(), el = $("#page"), page = A.pages[r.page] ? r.page : "partidos";
  renderShell(r);
  const need = [IDX.today].concat(A.needs[page] ? A.needs[page](r) : []);
  const bad = need.find(d => !A.dayInfo(d) || failed[d]);
  if (bad) { el.innerHTML = `<div class="card"><h3>Ese día no está disponible</h3><div class="sub">No hay datos del ${esc(bad)} en este sitio. <a class="lnk" href="#/partidos">Volver a la jornada de hoy</a></div></div>`; return; }
  const missing = need.filter(d => !NBA.days[d]);
  if (missing.length) {                                        // se piden los días que faltan y se vuelve a pintar
    el.innerHTML = `<div class="card">Cargando…</div>`;
    Promise.all(missing.map(loadDay)).then(render, () => { missing.forEach(d => { if (!NBA.days[d]) failed[d] = true; }); render(); });
    return;
  }
  A.pages[page](el, r);
  el.insertAdjacentHTML("beforeend", `<div class="pagefoot"><span>Portal NBA · herramienta de análisis, no asesoramiento. Solo mayores de 18 años.</span><span>Juego responsable: 900 200 225</span></div>`);
}
A.render = render;

function bindEvents() {
  window.addEventListener("hashchange", () => { document.body.classList.remove("navopen"); ui.fx.tab = route().page === "partido" ? ui.fx.tab : ""; render(); window.scrollTo(0, 0); });
  document.addEventListener("click", e => {
    const t = e.target;
    if (t.closest("#menu")) { document.body.classList.toggle("navopen"); return; }
    if (document.body.classList.contains("navopen") && !t.closest("#side")) document.body.classList.remove("navopen");
    if (t.closest("#collapse")) { save("portal-nba-mini", {v: $("#app").classList.toggle("mini")}); return; }
    let b;
    if ((b = t.closest("[data-fav]"))) { e.preventDefault(); const k = b.dataset.fav; if (A.favs[k]) delete A.favs[k]; else A.favs[k] = 1; A.saveFavs(); render(); return; }
    if ((b = t.closest("[data-set]"))) { setPath(b.dataset.set, b.dataset.v); render(); return; }
    if ((b = t.closest("[data-toggle]"))) { setPath(b.dataset.toggle, !getPath(b.dataset.toggle)); render(); return; }
    if ((b = t.closest("[data-tog]"))) { const a = getPath(b.dataset.tog), i = a.indexOf(b.dataset.v); if (i < 0) a.push(b.dataset.v); else a.splice(i, 1); render(); return; }
    if ((b = t.closest("[data-reset]"))) { ui[b.dataset.reset] = JSON.parse(JSON.stringify(DEFAULTS[b.dataset.reset])); render(); return; }
    if ((b = t.closest("th[data-sort]"))) { const [a, k] = b.dataset.sort.split("."), f = ui[a]; if (f.sort === k) f.dir = -f.dir; else { f.sort = k; f.dir = ["name", "team", "pos"].includes(k) ? 1 : -1; } render(); return; }
    if ((b = t.closest(".pname[data-pid]"))) { openPlayer(Number(b.dataset.pid)); return; }
    if (t.closest("#clearman")) { for (const k of Object.keys(A.manual)) delete A.manual[k]; A.saveManual(); render(); return; }
    if (t.closest("#clearfav")) { for (const k of Object.keys(A.favs)) delete A.favs[k]; A.saveFavs(); render(); }
  });
  document.addEventListener("change", e => {
    const t = e.target;
    if (t.matches("input[data-k]")) {                          // línea o cuota escrita a mano en la tabla de proyecciones
      const k = t.dataset.k, f = t.dataset.f, v = t.value === "" ? null : parseFloat(t.value), cur = A.manual[k] || {};
      if (f === "line" && v == null) { delete A.manual[k]; }
      else {
        if (cur.line == null && f !== "line") {                // cuota manual sobre la línea de DraftKings
          const [pid, mm] = k.split("|"), pl = A.T().players.find(x => String(x.pid) === pid), base = pl.markets[mm].line;
          if (!base) return;
          cur.line = base.value;
        }
        cur[f] = v; A.manual[k] = cur;
      }
      A.saveManual(); render(); return;
    }
    if (t.matches("[data-arr]")) { const a = getPath(t.dataset.arr), i = a.indexOf(t.value); if (t.checked && i < 0) a.push(t.value); if (!t.checked && i >= 0) a.splice(i, 1); render(); return; }
    if (t.matches("[data-ui]")) { setPath(t.dataset.ui, t.type === "checkbox" ? t.checked : t.value); render(); }
  });
  document.addEventListener("input", e => {
    const t = e.target;
    if (!t.matches("[data-live]")) return;
    setPath(t.dataset.live, t.value);
    const id = t.id, pos = t.selectionStart;
    render();
    const n = document.getElementById(id);
    if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (err) { /* algunos tipos de campo no admiten selección */ } }
  });
}
if (load("portal-nba-mini", {}).v) $("#app").classList.add("mini");
bindEvents();
render();
})();
