// Carga una página de takes ya generada, la recorre (pestañas, abrir un take, combinada) y devuelve un resumen en JSON.
// Uso: node web/tests/takes_smoke.js viz/takes-nba.html      (lo ejecuta tests/test_takes.py)
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs");
const errs = []; const vc = new VirtualConsole();
vc.on("jsdomError", e => errs.push(String(e.message || e)));
const dom = new JSDOM(fs.readFileSync(process.argv[2], "utf8"), { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc, url: "https://takes.test/" });
const w = dom.window, d = w.document;
w.scrollTo = () => {};
const click = el => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const count = sel => d.querySelectorAll(sel).length;
const out = { tabs: [...d.querySelectorAll(".tab")].map(b => b.textContent), top: count("#top-grid .take"), games: count("#games-grid .take") };
const first = d.querySelector("#games-grid .take");
if (first) {
  out.first_game = { call: first.querySelector(".call").textContent, pct: first.querySelector(".ring span").textContent };
  click(first.querySelector(".head"));
  out.first_game.detail_tiles = first.querySelectorAll(".more .tile").length;
  out.first_game.expanded = first.querySelector(".head").getAttribute("aria-expanded");
}
click(d.querySelector('[data-tab="jugadores"]'));
out.players_best = count("#players-grid .take");
const fp = d.querySelector("#players-grid .take");
if (fp) {
  out.first_player = { name: fp.querySelector(".name").textContent, call: fp.querySelector(".call").textContent, pct: fp.querySelector(".ring span").textContent };
  click(fp.querySelector(".head"));
  out.first_player.bars = fp.querySelectorAll(".more .bars .b").length;
}
d.getElementById("f-best").checked = false; d.getElementById("f-best").dispatchEvent(new w.Event("change"));
d.getElementById("f-clean").checked = false; d.getElementById("f-clean").dispatchEvent(new w.Event("change"));
out.players_all_count = d.getElementById("f-count").textContent;
// combinada manual: añade los dos primeros partidos que tengan botón
const adds = [...d.querySelectorAll("#games-grid [data-add]")].slice(0, 2);
adds.forEach(click);
click(d.querySelector('[data-tab="combinadas"]'));
const mine = d.querySelector("#tab-combinadas .parlay");
out.slip = mine ? { legs: mine.querySelectorAll(".legs li").length, tiles: [...mine.querySelectorAll(".sum dd")].map(x => x.textContent.trim()) } : null;
out.auto_parlays = count("#tab-combinadas .grid .parlay");
out.badge = (d.querySelector('[data-tab="combinadas"] b') || {}).textContent || null;
out.errors = errs;
console.log(JSON.stringify(out));
process.exit(errs.length ? 1 : 0);
