// Verifica que la página (JS) calcula lo mismo que el modelo Python para cada partido de la jornada.
// Uso: npm install jsdom && node web/tests/web_parity.js     (tras python scripts/export_web.py)
const { JSDOM, VirtualConsole } = require("jsdom");
const fs = require("fs"), path = require("path");
const root = path.resolve(__dirname, "../..");
const html = fs.readFileSync(path.join(root, "viz/analizador-nba.html"), "utf8").replace(/<link[^>]*fonts.googleapis[^>]*>/, "");
const parity = JSON.parse(fs.readFileSync(path.join(root, "web/parity.json"), "utf8"));
const errs = []; const vc = new VirtualConsole(); vc.on("jsdomError", e => errs.push(String(e.message || e)));
const w = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, virtualConsole: vc }).window, d = w.document;
let bad = 0;
for (const chip of d.querySelectorAll("#chips button")) {
  chip.dispatchEvent(new w.Event("click"));
  const home = d.getElementById("home").value, away = d.getElementById("away").value;
  const exp = parity.find(p => p.home === home && p.away === away);
  const mod = [...d.querySelectorAll("#result .stat")].find(s => s.className.includes("mod"));
  const margin = parseFloat(mod.querySelector(".v").textContent.replace("−", "-").replace(",", ".").replace("+", ""));
  const prob = parseFloat(mod.querySelector(".s").textContent.match(/(\d+(?:,\d+)?) %/)[1].replace(",", ".")) / 100;
  const ok = Math.abs(margin - exp.margin) < 0.06 && Math.abs(prob - exp.prob_home) < 0.006;
  if (!ok) bad++;
  console.log(`${away}@${home}`.padEnd(9), "web", margin.toFixed(1).padStart(6), (prob * 100).toFixed(0) + "%", "| python", exp.margin.toFixed(1).padStart(6), (exp.prob_home * 100).toFixed(0) + "%", ok ? "OK" : "DIFERENCIA");
}
if (errs.length) { console.log("errores de la página:", errs); process.exit(1); }
process.exit(bad ? 1 : 0);
