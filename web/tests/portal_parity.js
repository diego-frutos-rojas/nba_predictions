// Ejecuta el bloque CALC de web/portal_template.html (la única matemática que la página repite en JS) sobre los
// casos de un JSON y devuelve los resultados, para compararlos con nba_model/daily.py (tests/test_daily.py).
// Uso: node web/tests/portal_parity.js casos.json   -> imprime JSON con [{...sideEval, bucket}]
const fs = require("fs");
const path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "portal_template.html"), "utf8");
const m = html.match(/\/\*CALC-START\*\/([\s\S]*?)\/\*CALC-END\*\//);
if (!m) { console.error("no se encuentra el bloque CALC en la plantilla"); process.exit(2); }
const { sideEval, edgeBucket } = new Function(m[1] + "; return {sideEval, edgeBucket};")();
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = cases.cases.map(c => {
  const r = sideEval(c.sv, c.line, c.over, c.under);
  if (r.edge != null) r.bucket = edgeBucket(r.edge, cases.thresholds);
  return r;
});
process.stdout.write(JSON.stringify(out));
