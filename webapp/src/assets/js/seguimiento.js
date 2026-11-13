/* Páginas «Historial» (lo que acertaron de verdad las predicciones guardadas) y «Metodología». */
(function () {
"use strict";
const A = window.App, {IDX, esc, pct, num, sgn, L, fmtDay, pageHead} = A;
const thrLabel = t => (100 * parseFloat(t)).toFixed(0) + " pp";

A.pages.historial = el => {
  const t = IDX.track || {days: 0}, head = pageHead("chart", "Historial", "Lo que acertaron de verdad las predicciones de los días anteriores, sin borrar nada.");
  if (!t.days) { el.innerHTML = head + `<div class="card"><h3>Todavía no hay historial</h3><div class="sub">Cada vez que generas el sitio se guardan las predicciones del día en <code>data/predictions/</code>. A partir de mañana, aquí verás cuánto acertaron de verdad (líneas y precios tal como estaban cuando lo generaste).</div></div>`; return; }
  const pk = t.picks || {}, er = t.error || {}, gm = t.games, past = IDX.days.filter(d => d.kind === "pasado").reverse(), nl = {};
  (t.by_day || []).forEach(d => { nl[d.date] = d.n; });
  el.innerHTML = head + `<div class="sub">Predicciones guardadas de ${t.days} día(s), del ${esc(t.from)} al ${esc(t.to)} · ${t.n_lines || 0} líneas de jugador puntuadas (las de jugadores que no jugaron se anulan).</div>
    <h2>Apuestas de jugador siguiendo al modelo</h2>
    <div class="tablewrap"><table><thead><tr><th>Ventaja mínima</th><th>Apuestas</th><th>Acierto</th><th>Rentabilidad</th><th>Unidades</th></tr></thead><tbody>
    ${IDX.thresholds.map(k => { const x = pk[k]; return !x || !x.n ? `<tr><td>≥ ${thrLabel(k)}</td><td colspan="4" class="mute">sin apuestas</td></tr>` : `<tr><td>≥ ${thrLabel(k)}</td><td>${x.n}</td><td>${pct(x.acierto, 1)}</td><td class="${x.roi >= 0 ? "pos" : "neg"}">${sgn(100 * x.roi)} %</td><td class="${x.unidades >= 0 ? "pos" : "neg"}">${sgn(x.unidades, 2)}</td></tr>`; }).join("")}
    </tbody></table></div>
    <h2>Error de la proyección frente a la línea de la casa</h2>
    <div class="tablewrap"><table><thead><tr><th>Mercado</th><th>Líneas</th><th>Error medio del modelo</th><th>Error medio de la línea</th></tr></thead><tbody>
    ${IDX.markets.filter(m => er[m]).map(m => `<tr><td>${esc(L[m])}</td><td>${er[m].n}</td><td>${num(er[m].mae_modelo, 2)}</td><td>${num(er[m].mae_linea, 2)}</td></tr>`).join("")}
    </tbody></table></div>
    ${gm ? `<h2>Partidos</h2><div class="card">En ${gm.n} partidos: el modelo acertó el ganador el ${pct(gm.acierto_modelo, 1)} y el mercado el ${pct(gm.acierto_mercado, 1)}. Log loss (menor es mejor): modelo ${num(gm.log_loss_modelo, 4)}, mercado ${num(gm.log_loss_mercado, 4)}.</div>` : ""}
    <h2>Día a día</h2><div class="tablewrap"><table><thead><tr><th class="l">Jornada</th><th>Partidos</th><th>Líneas puntuadas</th><th></th></tr></thead><tbody>
    ${past.map(d => `<tr><td class="l" style="text-transform:capitalize">${esc(fmtDay(d.date, {weekday: "long", day: "numeric", month: "long", year: "numeric"}))}</td><td>${d.n}</td><td>${nl[d.date] == null ? "–" : nl[d.date]}</td><td><a class="lnk" href="#/partidos/${d.date}">Ver la jornada</a></td></tr>`).join("") || `<tr><td colspan="4" class="l mute">Sin jornadas anteriores.</td></tr>`}
    </tbody></table></div>
    <div class="info">Con pocas semanas de datos estas cifras se mueven mucho por pura suerte: hacen falta varios cientos de apuestas para sacar conclusiones.</div>`;
};

A.pages.metodologia = el => {
  const ev = IDX.evidence.props || {}, r = ev.test_rmse || {}, b = ev.blend || {};
  el.innerHTML = pageHead("book", "Metodología", "Qué hace cada página, cómo se calcula y qué límites tiene.") + `<div class="card"><h3>Qué hace cada página</h3><ul class="plain">
    <li><b>Partidos</b>: la jornada de hoy con la probabilidad del modelo y la lectura frente al mercado (DraftKings, vía ESPN). Con las flechas ves los días anteriores (lo que se predijo y lo que pasó) y el calendario de los siguientes. Cada partido tiene su ficha: apuestas de jugador y de equipo, estadísticas, cara a cara, quintetos probables y el desglose del modelo.</li>
    <li><b>Liga</b>: clasificación, calendario, líderes y tablas de la temporada.</li>
    <li><b>Buscador de props</b>: jugadores que han llegado a una cifra en sus últimos partidos, con la probabilidad del modelo para esta noche.</li>
    <li><b>Apuestas de jugador</b>: las líneas con precio, con la probabilidad del modelo, la de la casa y el historial real de ese nivel de ventaja.</li>
    <li><b>Apuestas de equipo</b>: ganador, hándicap y total de cada partido con la forma reciente de los dos equipos. No son recomendaciones.</li>
    <li><b>Proyecciones</b>: la tabla completa, donde puedes escribir la línea y las cuotas de tu casa.</li>
    <li><b>Favoritos</b>: lo que marcas con la estrella. <b>Historial</b>: lo que acertaron de verdad las predicciones de los días anteriores.</li></ul></div>
  <div class="card" style="margin-top:12px"><h3>Cómo se calcula la probabilidad de un partido</h3><ul class="plain">
    <li>Cada equipo tiene un <b>nivel</b> (puntos frente a un equipo medio) que se actualiza con cada resultado. Al nivel se le suman el factor cancha, el descanso y las bajas del parte de lesiones.</li>
    <li>El margen esperado se convierte en probabilidad con la variabilidad real de los marcadores. Los parámetros se afinaron solo con 2014-2019 y están congelados.</li></ul></div>
  <div class="card" style="margin-top:12px"><h3>Cómo se calcula la proyección de un jugador</h3><ul class="plain">
    <li><b>Minutos</b>: mezcla de sus minutos recientes y habituales, corregida por bajas de compañeros, plantilla disponible, descanso y riesgo de paliza.</li>
    <li><b>Ritmo por minuto</b>: forma reciente y de temporada, encogida hacia su media de carrera para no creerse una racha de tres partidos.</li>
    <li><b>Contexto</b>: lo que concede el rival, bajas de compañeros (más balón para los que quedan), casa/fuera y el total de puntos que espera el mercado.</li>
    <li><b>Probabilidad</b>: alrededor de esa media se usa una distribución ajustada a la variabilidad real de cada estadística. Los coeficientes se ajustaron solo con 2014-2019 y se comprobaron en 2020-2026.</li></ul>
    ${r.pts ? `<div class="sub">Error (RMSE) en 2022-26: puntos ${num(r.pts.modelo, 2)} (media de temporada ${num(r.pts.temporada, 2)}), rebotes ${num(r.reb.modelo, 2)} (${num(r.reb.temporada, 2)}), asistencias ${num(r.ast.modelo, 2)} (${num(r.ast.temporada, 2)}), triples ${num(r.fg3m.modelo, 2)} (${num(r.fg3m.temporada, 2)}).</div>` : ""}</div>
  <div class="card" style="margin-top:12px"><h3>Límites que conviene tener presentes</h3><ul class="plain">
    <li>La casa sabe más que el modelo: sus líneas fallan algo menos que nuestras proyecciones${IDX.evidence.games ? ` y el modelo de partidos no bate al mercado (log loss ${num(IDX.evidence.games.log_loss.v2_elo, 4)} frente a ${num(IDX.evidence.games.log_loss.mercado, 4)} en 2022-26)` : ""}. ${b.n ? `Aun así el modelo de jugadores aporta algo propio (peso ${num(b.coef_modelo, 2)} ± ${num(b.se_modelo, 2)} frente a ${num(b.coef_casa, 2)} de la casa en ${b.n} líneas).` : ""}</li>
    <li>El «acierto», la «racha» y la «forma» de los últimos partidos son descriptivos: con 5 o 10 partidos, una racha perfecta es casi siempre suerte. La ventana es la misma para todos a propósito; no se elige la que mejor queda para cada jugador.</li>
    <li>El modelo no lee noticias: límites de minutos, cambios de quinteto o molestias que no estén en el parte de ESPN no los ve. Por eso las diferencias enormes se marcan como «revisar» y los quintetos son solo probables.</li>
    <li>Las líneas y cuotas son de DraftKings (EE. UU.). Tu casa tendrá otras: escríbelas en la página Proyecciones.</li>
    <li>Si un jugador no juega, la apuesta se anula; si está en «duda», la proyección supone que juega.</li>
    <li>Genera el sitio cerca de la hora de los partidos: el parte de lesiones y las líneas cambian durante el día.</li>
    <li>Herramienta de análisis, no asesoramiento. Solo mayores de 18 años. Juego responsable: 900 200 225 (España).</li></ul></div>`;
};
})();
