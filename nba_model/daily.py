"""Estado del portal diario: partidos de la jornada, modelo de equipos, proyecciones de jugador y picks.

`build_state` lo calcula todo en Python (la página solo lo muestra y recalcula probabilidades cuando se escribe
una línea a mano, con las tablas que salen de aquí). `grade_history` puntúa las predicciones guardadas de días
anteriores contra lo que pasó de verdad: ese historial, y no el backtest, es la prueba real del portal.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from . import espn, live, props, props_eval
from .baselines import SIGMA_MARKET
from .data import fetch_history, rest_days_before
from .elo import AVAIL_CLIP, predict_game, run_elo
from .evaluate import load_params
from .injuries import PLAY_PROB
from .odds import american_to_decimal, american_to_implied, normal_cdf, remove_vig
from .webstate import TEAM_NAMES

BIG_EDGE = 0.25            # ventaja tan grande que casi siempre es una noticia que el modelo no conoce
SURVIVAL_CUT = 0.0005      # las tablas P(X >= k) se cortan cuando la probabilidad baja de aquí
MARKET_ORDER = list(props.ALL_MARKETS)


def today_et() -> dt.date:
    """Fecha actual en la costa este de EE. UU. (la que usa la NBA para fechar la jornada)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:                                            # sin base de datos de zonas (Windows sin tzdata)
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date()


def _dec(american) -> float | None:
    if american is None or (isinstance(american, float) and math.isnan(american)):
        return None
    return round(american_to_decimal(float(american)), 3)


def fair_over(over, under) -> float | None:
    """Probabilidad del over según la casa, quitando su margen."""
    if over is None or under is None:
        return None
    a, b, _ = remove_vig(american_to_implied(over), american_to_implied(under))
    return a


def side_eval(sv: list[float], line: float, dec_over: float | None, dec_under: float | None) -> dict:
    """P(más), P(menos), P(empate) con la tabla P(X >= k) y, si hay precios (decimales), ventaja y valor esperado.
    Esta función está replicada en JS en web/portal_template.html (bloque CALC) y se comprueba con
    web/tests/portal_parity.js."""
    k = int(math.floor(line)) + 1
    at = lambda i: (sv[i] if i < len(sv) else 0.0) if i > 0 else 1.0      # noqa: E731
    p_over = at(k)
    p_push = (at(k - 1) - p_over) if line == math.floor(line) else 0.0
    p_under = 1.0 - p_over - p_push
    out = {"p_over": p_over, "p_under": p_under, "p_push": p_push}
    if dec_over and dec_under and dec_over > 1 and dec_under > 1:
        io, iu = 1 / dec_over, 1 / dec_under
        fo = io / (io + iu)
        den = max(1e-9, 1.0 - p_push)                                     # el empate devuelve la apuesta
        e_over, e_under = p_over / den - fo, p_under / den - (1 - fo)
        side = "over" if e_over >= e_under else "under"
        p, dec = (p_over, dec_over) if side == "over" else (p_under, dec_under)
        out.update({"fair_over": fo, "side": side, "edge": max(e_over, e_under), "ev": p * (dec - 1) - (1 - p - p_push)})
    return out


def _survival(model: dict, market: str, mu: float) -> list[float]:
    sv = props.survival(model, market, mu)
    n = len(sv)
    while n > 2 and sv[n - 1] < SURVIVAL_CUT:
        n -= 1
    return [round(x, 4) for x in sv[:n]]


def _team_inputs(tr: props.PropsTracker, team: str, season: int, status: dict[int, str]) -> tuple[list[int], dict, dict]:
    """Candidatos del equipo, P(jugar) de cada uno y el bloque `miss` del modelo de jugadores."""
    cand = tr.candidates(team, season)
    q = {pid: PLAY_PROB.get(status.get(pid, "available"), 0.5) for pid in cand}
    miss = tr.missing(team, {pid: q.get(pid, 1.0) for pid in tr.roster(team)})
    miss["lineup"] = tr.lineup_minutes({pid: q[pid] * tr.play_weight(team, pid) for pid in cand})
    return cand, q, miss


def _player_block(tr, model, pid, team, opp, season, ctx, miss, status, lines) -> dict:
    p = tr.players[pid]
    f = tr.features(pid, team, opp, season, ctx, miss)
    mu = props.predict(model, {k: np.array([v]) for k, v in f.items()})
    rec = list(p.recent)                                                    # (min, pts, reb, ast, fg3m), antiguo -> reciente
    series = {"min": [r[0] for r in rec], "pts": [r[1] for r in rec], "reb": [r[2] for r in rec],
              "ast": [r[3] for r in rec], "fg3m": [r[4] for r in rec]}
    for c, parts in props.COMBOS.items():
        series[c] = [sum(x) for x in zip(*[series[s] for s in parts])]
    same = p.season == season and p.g_season > 0
    out = {"pid": pid, "name": p.name, "pos": p.pos, "team": team, "opp": opp,
           "status": status.get(pid, "available"), "min": round(float(mu["min"][0]), 1),
           "gp": p.g_season if p.season == season else 0, "start_rate": round(p.start_rate, 2), "markets": {}}
    for m in MARKET_ORDER:
        x = float(mu[m][0])
        parts = props.COMBOS.get(m, (m,))
        s = series[m]
        mk = {"mu": round(x, 2), "sv": _survival(model, m, x),
              "l5": round(float(np.mean(s[-5:])), 1) if s else None,
              "l10": round(float(np.mean(s)), 1) if s else None,
              "season": round(sum(p.sum_season[q] for q in parts) / p.g_season, 1) if same else None,
              "last": [int(v) for v in s],
              "def": round(float(np.mean([f[f"def_{q}"] for q in parts])), 3)}
        ln = lines.get((pid, m))
        if ln is not None:
            do, du = _dec(ln["over"]), _dec(ln["under"])
            mk["line"] = {"value": ln["line"], "over": do, "under": du, "side_ok": bool(ln["side_ok"]), "src": "DraftKings"}
            ev = side_eval(mk["sv"], ln["line"], do if ln["side_ok"] else None, du if ln["side_ok"] else None)
            mk["eval"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in ev.items()}
            mk["hit10"] = [int(sum(v > ln["line"] for v in s)), len(s)]
        out["markets"][m] = mk
    out["min_l10"] = round(float(np.mean(series["min"])), 1) if rec else None
    return out


def _evidence(root: Path) -> dict:
    ev = {}
    f = root / "docs/RESULTADOS_PROPS.json"
    if f.exists():
        r = json.load(open(f))
        mk = r.get("mercado") or {}
        ev["props"] = {"apuestas": mk.get("apuestas"), "blend": mk.get("blend"), "error": mk.get("error"),
                       "desde": mk.get("desde"), "hasta": mk.get("hasta"), "partidos": mk.get("partidos"),
                       "test_rmse": {m: {k: r["bloques"]["TEST"][m][k]["rmse"] for k in ("modelo", "ult10", "temporada")}
                                     for m in props.ALL_MARKETS}}
    f = root / "docs/RESULTADOS.json"
    if f.exists():
        r = json.load(open(f))
        t = r["blocks"]["TEST"]
        ev["games"] = {"log_loss": {k: t[k]["log_loss"] for k in ("v2_elo", "mercado")},
                       "accuracy": {k: t[k]["accuracy"] for k in ("v2_elo", "mercado")},
                       "gap_sd": r["gap_info"]["TEST"]["sd_gap_pts"], "blend": r["blend"]["coef_dev"],     # ajustado solo con DEV
                       "roi": {k: {"roi": v["TEST"]["roi"], "n": v["TEST"]["n"]} for k, v in r["roi_spread_-110"].items()}}
    return ev


def edge_bucket(edge: float) -> str:
    """Tramo de ventaja (los mismos umbrales pre-fijados de la evaluación) para enseñar su historial."""
    best = props_eval.EDGE_THRESHOLDS[0]
    for t in props_eval.EDGE_THRESHOLDS:
        if edge >= t:
            best = t
    return f"{best:.2f}"


def build_state(root: str | Path, date=None, fetch: bool = True, log=print) -> dict:
    """Calcula todo lo que enseña el portal para la jornada `date` (fecha de la costa este; por defecto hoy)."""
    root = Path(root)
    raw, lv = root / "data/raw", root / "data/live"
    date = pd.Timestamp(date or today_et()).normalize()
    warnings = []
    if fetch:
        log("1/5 actualizando resultados históricos (GitHub)...")
        try:
            fetch_history(raw)
        except Exception as e:
            warnings.append(f"No se pudieron actualizar los ficheros históricos de GitHub ({e}); se usan los que había.")
        log("2/5 completando con ESPN los partidos más recientes...")
        live.sync_results(raw, lv, date - pd.Timedelta(days=1), log=log)
    log("3/5 recalculando modelos hasta ayer...")
    ds = live.build_dataset(raw, lv, until=date)
    g = ds["games"]
    params = load_params(root / "models/params_v2.json")
    elo = run_elo(g, params)
    g["margin_model"] = elo["margin_pred"]
    st = elo["state"]
    av = ds["av_tracker"]
    _, tr = props.build_features(g, ds["boxes"], return_tracker=True)
    model = props.load_model(root / "models/props_v1.json")
    sigma = math.sqrt(st.var) * params.sig_scale

    log("4/5 descargando jornada, cuotas, lesiones y props (ESPN)...")
    slate = [x for x in espn.fetch_scoreboard(date.date()) if x["season_type"] in (2, 3)]
    inj = espn.fetch_injuries()
    status = {i["pid"]: i["status"] for i in inj if i["pid"] is not None}
    inj_by_team: dict[str, list] = {}
    for i in inj:
        inj_by_team.setdefault(i["team"], []).append(i)
    season = int(slate[0]["season"]) if slate else int(g.season.max())
    last_data = g.date.max()
    if (date - last_data).days > 3 and slate:
        warnings.append(f"Los datos de resultados llegan hasta el {last_data.date()}: las proyecciones pueden estar desfasadas.")

    games_out, players_out = [], []
    for ev in slate:
        h, a, gid = ev["home"], ev["away"], ev["game_id"]
        odds = ev["odds"] or {}
        try:
            lines_list = espn.fetch_props(gid)
        except Exception as e:
            lines_list = []
            warnings.append(f"No se pudieron leer las props de {a}@{h} ({e}).")
        if ev["state"] == "pre":                                 # solo se guardan cuotas previas al partido
            live.save_market(lv, gid, ev["odds"], lines_list)
        lines = {(x["pid"], x["market"]): x for x in lines_list}
        # --- modelo de equipos (v2) ---
        deltas = {}
        for side, team in (("home", h), ("away", a)):
            by_pid = {int(p): PLAY_PROB.get(status[int(p)], 0.5) for p in av.roster(team) if int(p) in status}
            deltas[side] = av.expected_delta(team, season, by_pid)
        clip = lambda x: max(-AVAIL_CLIP, min(AVAIL_CLIP, x))     # noqa: E731
        rh, ra = rest_days_before(g[g.season == season], h, date), rest_days_before(g[g.season == season], a, date)
        adj = params.avail * (clip(deltas["home"]) - clip(deltas["away"]))
        pg = predict_game(st, h, a, rh, ra, params, neutral=ev["neutral"], adj=adj)
        spread = odds.get("spread_home")
        mkt = {"provider": odds.get("provider"), "spread_home": spread, "total": odds.get("total"),
               "spread_home_open": odds.get("spread_home_open"), "total_open": odds.get("total_open"),
               "ml_home": _dec(odds.get("ml_home")), "ml_away": _dec(odds.get("ml_away")),
               "spread_odds_home": _dec(odds.get("spread_odds_home")), "spread_odds_away": _dec(odds.get("spread_odds_away")),
               "over_odds": _dec(odds.get("over_odds")), "under_odds": _dec(odds.get("under_odds"))}
        p_mkt, kind = None, None
        if odds.get("ml_home") is not None and odds.get("ml_away") is not None:
            p_mkt, kind = remove_vig(american_to_implied(odds["ml_home"]), american_to_implied(odds["ml_away"]))[0], "moneyline sin margen"
        elif spread is not None:
            p_mkt, kind = normal_cdf(-spread / SIGMA_MARKET), "spread convertido"
        gap = None if spread is None else pg["margin"] - (-spread)
        game = {
            "game_id": gid, "home": h, "away": a, "home_name": TEAM_NAMES[h], "away_name": TEAM_NAMES[a],
            "tip_utc": ev["tip_utc"], "state": ev["state"], "detail": ev["detail"],
            "home_pts": ev["home_pts"], "away_pts": ev["away_pts"],
            "model": {"margin": round(pg["margin"], 2), "prob_home": round(pg["prob_home"], 4), "sigma": round(sigma, 2),
                      "rating_home": round(st.ratings.get(h, 0.0), 2), "rating_away": round(st.ratings.get(a, 0.0), 2),
                      "hca": 0.0 if ev["neutral"] else round(st.hca, 2), "avail_pts": round(adj, 2),
                      "p_cover_home": None if spread is None else round(normal_cdf((pg["margin"] + spread) / sigma), 4)},
            "market": {**mkt, "prob_home": None if p_mkt is None else round(p_mkt, 4), "prob_kind": kind},
            "gap_pts": None if gap is None else round(gap, 2),
            "rest": {"home": rh, "away": ra},
            "injuries": {side: [{"player": i["player"], "status": i["status"], "detail": i["detail"], "comment": i["comment"]}
                                for i in inj_by_team.get(team, [])] for side, team in (("home", h), ("away", a))},
            "n_lines": len(lines_list),
        }
        games_out.append(game)
        # --- modelo de jugadores ---
        grow = {"close_spread_home": spread if spread is not None else float("nan"),
                "close_total": odds.get("total") if odds.get("total") is not None else float("nan"),
                "rest_home": rh, "rest_away": ra, "margin_model": pg["margin"]}
        for team, opp, home in ((h, a, True), (a, h, False)):
            cand, q, miss = _team_inputs(tr, team, season, status)
            ctx = props.game_context(grow, home)
            for pid in cand:
                if q[pid] <= 0 or not tr.eligible(pid):
                    continue
                if tr.appear_frac(team, pid) == 0 and (pid, "pts") not in lines:
                    continue                                     # lleva sin jugar todos los últimos partidos y sin línea
                pl = _player_block(tr, model, pid, team, opp, season, ctx, miss, status, lines)
                pl["game_id"] = gid
                pl["home"] = home
                players_out.append(pl)

    log("5/5 montando picks e historial...")
    evidence = _evidence(root)
    picks = []
    started = {x["game_id"] for x in games_out if x["state"] != "pre"}
    for pl in players_out:
        for m, mk in pl["markets"].items():
            e = mk.get("eval") or {}
            if "edge" not in e or pl["game_id"] in started:
                continue
            flags = []
            if pl["status"] != "available":
                flags.append("duda")
            if e["edge"] >= BIG_EDGE:
                flags.append("revisar")
            picks.append({"pid": pl["pid"], "name": pl["name"], "team": pl["team"], "opp": pl["opp"], "game_id": pl["game_id"],
                          "market": m, "side": e["side"], "line": mk["line"]["value"],
                          "price": mk["line"]["over" if e["side"] == "over" else "under"],
                          "p": e["p_over"] if e["side"] == "over" else e["p_under"], "mu": mk["mu"],
                          "edge": e["edge"], "ev": e["ev"], "bucket": edge_bucket(e["edge"]), "flags": flags})
    picks.sort(key=lambda x: -x["edge"])
    state = {
        "date": str(date.date()), "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season, "data_through": str(last_data.date()), "warnings": warnings,
        "labels": props.LABELS, "markets": MARKET_ORDER, "thresholds": [f"{t:.2f}" for t in props_eval.EDGE_THRESHOLDS],
        "big_edge": BIG_EDGE, "games": games_out, "players": players_out, "picks": picks, "evidence": evidence,
    }
    return state


# ---- guardado e historial -------------------------------------------------------------------------
def save_predictions(root: str | Path, state: dict) -> Path:
    """Guarda las predicciones del día. Si se vuelve a ejecutar con partidos ya empezados, se conserva lo que se
    predijo antes del salto inicial (no se puede "predecir" un partido en juego)."""
    d = Path(root) / "data/predictions"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{state['date']}.json"
    keep_games, keep_players = [], []
    started = {x["game_id"] for x in state["games"] if x["state"] != "pre"}
    if path.exists() and started:
        old = json.load(open(path, encoding="utf-8"))
        keep_games = [x for x in old["games"] if x["game_id"] in started]
        keep_players = [x for x in old["players"] if x["game_id"] in started]
    slim = lambda pl: {**{k: pl[k] for k in ("pid", "name", "team", "opp", "game_id", "status", "min")},     # noqa: E731
                       "markets": {m: {k: v for k, v in mk.items() if k in ("mu", "line", "eval")} for m, mk in pl["markets"].items()}}
    out = {"date": state["date"], "generated_utc": state["generated_utc"],
           "games": keep_games + [{k: x[k] for k in ("game_id", "home", "away", "tip_utc", "model", "market", "gap_pts")}
                                  for x in state["games"] if x["game_id"] not in started],
           "players": keep_players + [slim(p) for p in state["players"] if p["game_id"] not in started]}
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return path


def grade_history(root: str | Path, before: str) -> dict:
    """Puntúa las predicciones guardadas de fechas anteriores a `before` contra los resultados reales."""
    root = Path(root)
    files = sorted(f for f in (root / "data/predictions").glob("*.json") if f.stem < before)
    if not files:
        return {"days": 0}
    ds = live.build_dataset(root / "data/raw", root / "data/live")
    g = ds["games"].set_index("game_id")
    b = ds["boxes"]
    b = b[b.played].set_index(["game_id", "pid"])
    rows, games, by_day = [], [], []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        n0 = len(rows)
        for x in d["games"]:
            if x["game_id"] in g.index and x["market"].get("prob_home") is not None:
                games.append({"y": float(g.loc[x["game_id"], "home_margin"] > 0), "p_model": x["model"]["prob_home"],
                              "p_mkt": x["market"]["prob_home"]})
        for pl in d["players"]:
            key = (pl["game_id"], pl["pid"])
            if key not in b.index:
                continue                                         # no jugó (apuesta anulada) o partido sin caja todavía
            box = b.loc[key]
            for m, mk in pl["markets"].items():
                ln, e = mk.get("line"), mk.get("eval") or {}
                if not ln:
                    continue
                y = float(sum(box[s] for s in props.COMBOS.get(m, (m,))))
                rows.append({"date": d["date"], "game_id": pl["game_id"], "market": m, "y": y, "mu": mk["mu"], "line": ln["value"],
                             "dec_over": ln["over"], "dec_under": ln["under"], "p_over": e.get("p_over"),
                             "fair_over": e.get("fair_over"), "edge": e.get("edge"), "side": e.get("side")})
        by_day.append({"date": d["date"], "n": len(rows) - n0})
    out = {"days": len(files), "from": files[0].stem, "to": files[-1].stem, "n_lines": len(rows), "by_day": by_day}
    if games:
        t = pd.DataFrame(games)
        ll = lambda p: float(-(t.y * np.log(np.clip(p, 1e-9, 1)) + (1 - t.y) * np.log(np.clip(1 - p, 1e-9, 1))).mean())    # noqa: E731
        out["games"] = {"n": len(t), "acierto_modelo": float(((t.p_model > 0.5) == (t.y == 1)).mean()),
                        "acierto_mercado": float(((t.p_mkt > 0.5) == (t.y == 1)).mean()),
                        "log_loss_modelo": ll(t.p_model), "log_loss_mercado": ll(t.p_mkt)}
    if rows:
        t = pd.DataFrame(rows)
        out["error"] = {m: {"n": int(len(s)), "mae_modelo": float((s.y - s.mu).abs().mean()), "mae_linea": float((s.y - s.line).abs().mean())}
                        for m, s in t.groupby("market")}
        bets = t[t.edge.notna()].copy()
        out["picks"] = {}
        for thr in props_eval.EDGE_THRESHOLDS:
            s = bets[bets.edge >= thr]
            if s.empty:
                out["picks"][f"{thr:.2f}"] = {"n": 0}
                continue
            over = (s.side == "over").values
            win = np.where(over, s.y > s.line, s.y < s.line)
            push = (s.y == s.line).values
            dec = np.where(over, s.dec_over, s.dec_under).astype(float)
            pnl = np.where(push, 0.0, np.where(win, dec - 1, -1.0))
            out["picks"][f"{thr:.2f}"] = {"n": int(len(s)), "acierto": float(win[~push].mean()) if (~push).any() else None,
                                          "roi": float(pnl.mean()), "unidades": float(pnl.sum())}
    return out


def render(root: str | Path, state: dict, out: str | Path | None = None) -> Path:
    """Inserta el estado en la plantilla y escribe la página autocontenida."""
    root = Path(root)
    out = Path(out) if out else root / "viz/portal-nba.html"
    tpl = (root / "web/portal_template.html").read_text(encoding="utf-8")
    assert "/*__STATE__*/null" in tpl, "la plantilla no tiene el marcador de estado"
    payload = json.dumps(state, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tpl.replace("/*__STATE__*/null", payload), encoding="utf-8")
    return out
