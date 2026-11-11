"""Uso: python scripts/exp_dev_verano_platt.py   (resultados en docs/AUDITORIA.md, sección 5)
Experimentos SOLO con DEV (2014-2019). Validación cruzada temporal: afinar en 2014-16 -> evaluar 2017-19 y al revés.
No mira VAL ni TEST.
E1: cambio de plantilla en verano (rating inicial += w * D, D = talento que juega el 1er partido - talento de la rotación final previa).
E2: recalibración de Platt sobre logit(p) del modelo.
"""
import math
import sys
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from statistics import NormalDist

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nba_model.availability import MIN_ROT, AvailabilityTracker, load_boxes
from nba_model.elo import AVAIL_CLIP, SIGMA_INIT, SIGMA_MEMORY, _rest_effect, run_elo
from nba_model.evaluate import _logit_fit, load_params, prepare_dataset
from nba_model.metrics import log_loss, logit, sigmoid

_N = NormalDist()
t0 = time.time()
g = prepare_dataset(ROOT / "data/raw")
g = g[g.season <= 2019].reset_index(drop=True)            # el experimento NUNCA ve VAL ni TEST
print("dataset", len(g), "partidos", round(time.time() - t0), "s")
P = load_params(ROOT / "models/params_v2.json")

# ---- feature D (sin fuga: valores previos al partido + quién juega el 1er partido, como en availability) ----
boxes = load_boxes(ROOT / "data/raw")
by_game = defaultdict(lambda: defaultdict(list))
for gid, team, pid, mins, played, gs in zip(boxes.game_id, boxes.team, boxes.pid, boxes.minutes, boxes.played, boxes.gs):
    by_game[gid][team].append((pid, mins, played, gs))
tr = AvailabilityTracker()
Dh, Da = np.zeros(len(g)), np.zeros(len(g))
for i, (gid, h, a, s) in enumerate(zip(g.game_id, g.home, g.away, g.season)):
    ent = by_game.get(gid, {})
    for t, arr in ((h, Dh), (a, Da)):
        if tr.season.get(t) != s and t in tr.season:           # primer partido de la temporada (y hay temporada previa)
            prev = tr.roster(t)                                 # rotación al final de la temporada anterior
            T_prev = sum(tr.value(p) for p in prev)
            now = {e[0] for e in ent.get(t, []) if e[2] and tr.m.get(e[0], 0.0) >= MIN_ROT}
            T_now = sum(tr.value(p) for p in now)
            arr[i] = T_now - T_prev
    for t in (h, a):
        tr._roll(t, s)
    for t in (h, a):
        tr.update(t, s, ent.get(t, []), 0.0)
g["D_home"], g["D_away"] = Dh, Da
nz = np.r_[Dh[Dh != 0], Da[Da != 0]]
print("D: n=%d media=%.1f sd=%.1f min=%.1f max=%.1f" % (len(nz), nz.mean(), nz.std(), nz.min(), nz.max()))


def run(df, p, w):
    """Copia de elo.run_elo con el ajuste de plantilla al primer partido de cada equipo en la temporada."""
    r = defaultdict(float); gis = defaultdict(int); hca, var, season = p.hca0, SIGMA_INIT ** 2, None
    n = len(df); mp = np.empty(n); sg = np.empty(n)
    H, A, M, S, NEU = df.home.values, df.away.values, df.home_margin.values.astype(float), df.season.values, df.neutral.values
    RH, RA, AH, AA, DH, DA = df.rest_home.values, df.rest_away.values, df.avail_home.values, df.avail_away.values, df.D_home.values, df.D_away.values
    clip = lambda x: max(-AVAIL_CLIP, min(AVAIL_CLIP, x))
    for i in range(n):
        if S[i] != season:
            if season is not None:
                for t in r: r[t] *= p.carry; gis[t] = 0
            season = S[i]
        h, a = H[i], A[i]
        if w:
            r[h] += w * DH[i]; r[a] += w * DA[i]                 # D != 0 solo en el 1er partido del equipo
        pred = r[h] - r[a] + (0 if NEU[i] else hca) + _rest_effect(RH[i], p) - _rest_effect(RA[i], p) + p.avail * (clip(AH[i]) - clip(AA[i]))
        mp[i] = pred; sg[i] = math.sqrt(var) * p.sig_scale
        m = max(-p.cap, min(p.cap, M[i])); err = m - pred
        k = p.k * (1 + p.boost * math.exp(-(gis[h] + gis[a]) / 30))
        r[h] += k * err; r[a] -= k * err
        if not NEU[i]: hca += p.lr_hca * err
        var += (M[i] - pred) ** 2 / SIGMA_MEMORY - var / SIGMA_MEMORY
        gis[h] += 1; gis[a] += 1
    return np.array([_N.cdf(x / y) for x, y in zip(mp, sg)]), mp


y = (g.home_margin.values > 0).astype(int)
S = g.season.values
A_, B_ = (S >= 2014) & (S <= 2016), (S >= 2017) & (S <= 2019)
# primeros 20 partidos de cada temporada (donde debería notarse)
gn = g.groupby("season").cumcount().values
early = gn < 20 * 15

# comprobación: w=0 reproduce elo.run_elo
p0, _ = run(g, P, 0.0)
assert np.allclose(p0, run_elo(g, P)["prob_home"]), "la copia no reproduce elo.run_elo"

print("\n== E1: ajuste de plantilla (rejilla w x carry, el resto congelado) ==")
grid = [(w, c) for w in (0, .01, .02, .03, .04, .05, .06, .08) for c in (.60, .65, P.carry, .80, .90)]
res = {}
for w, c in grid:
    p, _ = run(g, replace(P, carry=c), w)
    res[(w, c)] = p
ll = lambda p, m: log_loss(p[m], y[m])
for lab, tune_m, eval_m in (("afina 14-16 -> evalúa 17-19", A_, B_), ("afina 17-19 -> evalúa 14-16", B_, A_)):
    best = min(grid, key=lambda k: ll(res[k], tune_m))
    base = (0, P.carry)
    print(f"{lab}: elegido w={best[0]} carry={best[1]:.2f} | eval LL base {ll(res[base], eval_m):.5f} -> {ll(res[best], eval_m):.5f} "
          f"(dif {ll(res[best], eval_m) - ll(res[base], eval_m):+.5f}); inicio temporada {ll(res[base], eval_m & early):.5f} -> {ll(res[best], eval_m & early):.5f}")
print("tabla DEV completo (LL): ")
for w in (0, .02, .04, .06, .08):
    print("  w=%.2f " % w + " ".join(f"c={c:.2f}:{ll(res[(w, c)], A_ | B_):.5f}" for c in (.60, .65, P.carry, .80, .90)))

print("\n== E2: Platt (a + b*logit p) ==")
for lab, tune_m, eval_m in (("afina 14-16 -> evalúa 17-19", A_, B_), ("afina 17-19 -> evalúa 14-16", B_, A_)):
    X = lambda m: np.c_[np.ones(m.sum()), logit(p0[m])]
    wv = _logit_fit(X(tune_m), y[tune_m])
    pc = sigmoid(X(eval_m) @ wv)
    print(f"{lab}: a={wv[0]:+.3f} b={wv[1]:.3f} | eval LL {ll(p0, eval_m):.5f} -> {log_loss(pc, y[eval_m]):.5f} (dif {log_loss(pc, y[eval_m]) - ll(p0, eval_m):+.5f})")
print("tiempo total", round(time.time() - t0), "s")
