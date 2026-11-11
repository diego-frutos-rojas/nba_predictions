"""Página de «takes»: la jornada resumida en frases claras («Gana Houston · 68 %», «Más de 21,5 puntos · 59 %»).

Parte del mismo estado que el portal (`daily.build_state`) y no añade ningún modelo: solo ordena y resume.

El porcentaje grande de cada take es la **probabilidad combinada** modelo + casa, no la del modelo a secas:
  * Partidos: blend logístico ajustado solo con DEV (`docs/RESULTADOS.json` -> blend.coef_dev).
  * Jugadores: regresión logística de «over» sobre casa y modelo medida con las líneas reales de la temporada
    (`docs/RESULTADOS_PROPS.json` -> mercado.blend).
Motivo: el modelo a secas es demasiado confiado frente a la casa (dice 80 % donde el historial acierta ~55 %), y
enseñar ese 80 % como «porcentaje de acierto» sería engañoso. Las cifras sin combinar van en el detalle de cada take.
Si falta el fichero de evidencia se usa la probabilidad del modelo y el take se marca como `calibrated = False`.

Toda la matemática está aquí (Python). La página solo multiplica probabilidades y cuotas en la combinada manual.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from .daily import BIG_EDGE

# Tramos de color de la página. Fijados a priori para presentar; no se ajustan mirando resultados.
TIER_STRONG = 0.65
TIER_MEDIUM = 0.57
TOP_N = 12                    # takes de la portada
PARLAY_SIZES = (2, 3, 4)      # combinadas automáticas: doble, triple y cuádruple
MODEL_CLIP = (0.01, 0.99)     # el mismo recorte que usa props_eval.market_test al ajustar el blend

MARKET_PHRASE = {"pts": "puntos", "reb": "rebotes", "ast": "asistencias", "fg3m": "triples", "pra": "puntos + rebotes + asistencias",
                 "pr": "puntos + rebotes", "pa": "puntos + asistencias", "ra": "rebotes + asistencias"}
STATUS_ES = {"out": "baja", "doubtful": "muy dudoso", "questionable": "duda", "probable": "probable", "day-to-day": "día a día",
             "listed": "en el parte", "available": "disponible"}


def _logit(p: float) -> float:
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def _clip(p: float, lo: float = 1e-6, hi: float = 1 - 1e-6) -> float:
    return max(lo, min(hi, p))


def tier(p: float) -> str:
    """Tramo de color: 'fuerte' (>= 65 %), 'media' (>= 57 %) o 'ajustada'."""
    return "fuerte" if p >= TIER_STRONG else ("media" if p >= TIER_MEDIUM else "ajustada")


def blend_game(p_model: float, p_market: float | None, coef: dict | None) -> tuple[float, bool]:
    """P(gana el local) combinando modelo y mercado. Devuelve (probabilidad, ¿está combinada?)."""
    if p_market is None or not coef:
        return p_model, False
    z = coef["a"] + coef["b_mercado"] * _logit(_clip(p_market)) + coef["b_modelo"] * _logit(_clip(p_model))
    return _sigmoid(z), True


def blend_prop(p_model: float, p_house: float | None, coef: dict | None) -> tuple[float, bool]:
    """P(el lado elegido) combinando modelo y casa. Sin precio fiable la casa cuenta como 50 % (la línea es su mediana).
    La regresión no tiene término independiente, así que es simétrica: blend(over) + blend(under) = 1."""
    if not coef:
        return p_model, False
    house = 0.5 if p_house is None else p_house
    z = coef["coef_casa"] * _logit(_clip(house)) + coef["coef_modelo"] * _logit(_clip(p_model, *MODEL_CLIP))
    return _sigmoid(z), True


def _fmt_line(x: float) -> str:
    return (f"{x:.1f}" if x != int(x) else f"{int(x)}").replace(".", ",")


def game_take(g: dict, coef: dict | None) -> dict:
    p_home_model, p_home_mkt = g["model"]["prob_home"], g["market"].get("prob_home")
    p_home, calibrated = blend_game(p_home_model, p_home_mkt, coef)
    home_wins = p_home >= 0.5
    side = "home" if home_wins else "away"
    pick, rival = (g["home"], g["away"]) if home_wins else (g["away"], g["home"])
    pick_name, rival_name = (g["home_name"], g["away_name"]) if home_wins else (g["away_name"], g["home_name"])
    flip = (lambda x: x) if home_wins else (lambda x: 1 - x)
    p = flip(p_home)
    p_model, p_market = flip(p_home_model), None if p_home_mkt is None else flip(p_home_mkt)
    margin = g["model"]["margin"] if home_wins else -g["model"]["margin"]
    spread = g["market"].get("spread_home")
    flags = []
    if p_market is not None and (p_model >= 0.5) != (p_market >= 0.5):
        flags.append("discrepan")                                   # modelo y mercado eligen ganadores distintos
    if g["state"] != "pre":
        flags.append("empezado")
    return {
        "id": f"g:{g['game_id']}", "kind": "game", "game_id": g["game_id"], "team": pick, "opp": rival,
        "title": f"Gana {pick_name}", "subtitle": f"{'en casa' if home_wins else 'fuera'} contra {rival_name}",
        "p": round(p, 4), "tier": tier(p), "calibrated": calibrated, "price": g["market"].get("ml_home" if home_wins else "ml_away"),
        "flags": flags, "tip_utc": g["tip_utc"], "state": g["state"],
        "detail": {
            "home": g["home"], "away": g["away"], "home_name": g["home_name"], "away_name": g["away_name"], "pick_side": side,
            "p_model": round(p_model, 4), "p_market": None if p_market is None else round(p_market, 4),
            "market_kind": g["market"].get("prob_kind"), "provider": g["market"].get("provider"),
            "margin_model": round(margin, 1), "spread_pick": None if spread is None else (spread if home_wins else -spread),
            "p_cover_pick": None if g["model"].get("p_cover_home") is None else round(flip(g["model"]["p_cover_home"]), 4),
            "gap_pts": None if g.get("gap_pts") is None else round(g["gap_pts"] if home_wins else -g["gap_pts"], 1),
            "total": g["market"].get("total"), "sigma": g["model"]["sigma"],
            "rating_pick": g["model"]["rating_home" if home_wins else "rating_away"],
            "rating_opp": g["model"]["rating_away" if home_wins else "rating_home"],
            "hca": g["model"]["hca"], "avail_pts": round(g["model"]["avail_pts"] if home_wins else -g["model"]["avail_pts"], 1),
            "rest_pick": g["rest"][side], "rest_opp": g["rest"]["away" if home_wins else "home"],
            "injuries_pick": _injuries(g["injuries"][side]), "injuries_opp": _injuries(g["injuries"]["away" if home_wins else "home"]),
        },
    }


def _injuries(items: list[dict]) -> list[dict]:
    order = {"out": 0, "doubtful": 1, "questionable": 2}
    keep = [i for i in items if i["status"] != "available"]
    keep.sort(key=lambda i: order.get(i["status"], 3))
    return [{"player": i["player"], "status": STATUS_ES.get(i["status"], i["status"]), "detail": i.get("detail") or ""} for i in keep]


def player_takes(pl: dict, coef: dict | None, team_names: dict, started: set) -> list[dict]:
    """Un take por mercado con línea: el lado (más / menos) que prefiere el modelo, con su probabilidad combinada."""
    out = []
    for m, mk in pl["markets"].items():
        ln, ev = mk.get("line"), mk.get("eval")
        if not ln or not ev:
            continue
        den = max(1e-9, 1 - ev["p_push"])                              # el empate devuelve la apuesta
        over = ev["p_over"] >= ev["p_under"]
        p_model = (ev["p_over"] if over else ev["p_under"]) / den
        fair = ev.get("fair_over")                                     # solo existe si el precio es fiable (side_ok)
        p_house = None if fair is None else (fair if over else 1 - fair)
        p, calibrated = blend_prop(p_model, p_house, coef)
        last = mk.get("last") or []
        hits = sum((v > ln["value"]) if over else (v < ln["value"]) for v in last)
        edge = None if p_house is None else p_model - p_house
        flags = []
        if pl["status"] != "available":
            flags.append("duda")
        if edge is not None and edge >= BIG_EDGE:
            flags.append("revisar")                                    # casi siempre es una noticia que el modelo no conoce
        if p_house is None:
            flags.append("sin_precio")
        if pl["game_id"] in started:
            flags.append("empezado")
        price = ln.get("over" if over else "under") if ln.get("side_ok") else None
        out.append({
            "id": f"p:{pl['game_id']}:{pl['pid']}:{m}", "kind": "player", "game_id": pl["game_id"], "pid": pl["pid"],
            "team": pl["team"], "opp": pl["opp"], "market": m, "side": "over" if over else "under",
            "name": pl["name"], "title": f"{'Más' if over else 'Menos'} de {_fmt_line(ln['value'])} {MARKET_PHRASE[m]}",
            "subtitle": f"{team_names.get(pl['team'], pl['team'])} · {'en casa' if pl.get('home') else 'fuera'} contra {team_names.get(pl['opp'], pl['opp'])}",
            "p": round(p, 4), "tier": tier(p), "calibrated": calibrated, "price": price, "flags": flags,
            "detail": {
                "line": ln["value"], "mu": mk["mu"], "p_model": round(p_model, 4), "p_house": None if p_house is None else round(p_house, 4),
                "edge": None if edge is None else round(edge, 4), "src": ln.get("src"),
                "l5": mk.get("l5"), "l10": mk.get("l10"), "season": mk.get("season"), "last": last, "hits": [hits, len(last)],
                "min": pl["min"], "min_l10": pl.get("min_l10"), "gp": pl.get("gp"), "pos": pl.get("pos"),
                "status": STATUS_ES.get(pl["status"], pl["status"]), "def": mk.get("def"),
            },
        })
    return out


def _clean(t: dict) -> bool:
    """Takes aptos para portada y combinadas: sin dudas de lesión, sin discrepancias sospechosas y sin empezar."""
    return not set(t["flags"]) & {"duda", "revisar", "sin_precio", "empezado", "discrepan"} and t["price"] is not None


def auto_parlays(takes: list[dict]) -> list[dict]:
    """Combinadas automáticas: los takes limpios más probables, **uno por partido** para que sean (casi) independientes.
    P(combinada) = producto de probabilidades; cuota = producto de cuotas."""
    best: dict[str, dict] = {}
    for t in sorted((t for t in takes if _clean(t)), key=lambda t: -t["p"]):
        best.setdefault(t["game_id"], t)
    legs = list(best.values())
    out = []
    for n in PARLAY_SIZES:
        if len(legs) < n:
            break
        sel = legs[:n]
        p = math.prod(x["p"] for x in sel)
        price = math.prod(x["price"] for x in sel)
        out.append({"n": n, "legs": [x["id"] for x in sel], "p": round(p, 4), "price": round(price, 2),
                    "fair_price": round(1 / p, 2), "ev": round(p * price - 1, 4)})
    return out


def build(state: dict) -> dict:
    """Estado de la página de takes a partir del estado del portal."""
    ev = state.get("evidence") or {}
    coef_g = (ev.get("games") or {}).get("blend")
    coef_p = (ev.get("props") or {}).get("blend")
    names = {}
    for g in state["games"]:
        names[g["home"]], names[g["away"]] = g["home_name"], g["away_name"]
    started = {g["game_id"] for g in state["games"] if g["state"] != "pre"}
    games = sorted((game_take(g, coef_g) for g in state["games"]), key=lambda t: -t["p"])
    players = sorted((t for pl in state["players"] for t in player_takes(pl, coef_p, names, started)), key=lambda t: -t["p"])
    everything = games + players
    best_by_player: dict = {}
    for t in players:                                                  # ya vienen ordenados: el primero de cada jugador es su mejor take
        if _clean(t):
            best_by_player.setdefault(t["pid"], t)
    top = sorted([t for t in games if _clean(t)] + list(best_by_player.values()), key=lambda t: -t["p"])[:TOP_N]
    order = {g["game_id"]: i for i, g in enumerate(sorted(state["games"], key=lambda g: g["tip_utc"]))}
    acc = (ev.get("games") or {}).get("accuracy") or {}
    bets = (ev.get("props") or {}).get("apuestas") or {}
    return {
        "date": state["date"], "generated_utc": state["generated_utc"], "warnings": state.get("warnings", []),
        "tiers": {"fuerte": TIER_STRONG, "media": TIER_MEDIUM}, "big_edge": BIG_EDGE,
        "labels": {k: v for k, v in state["labels"].items() if k in MARKET_PHRASE}, "team_names": names,
        "slate": [{"game_id": g["game_id"], "home": g["home"], "away": g["away"], "tip_utc": g["tip_utc"], "state": g["state"]}
                  for g in sorted(state["games"], key=lambda g: order[g["game_id"]])],
        "games": games, "players": players, "top": [t["id"] for t in top], "parlays": auto_parlays(everything),
        "evidence": {"games_accuracy_model": acc.get("v2_elo"), "games_accuracy_market": acc.get("mercado"),
                     "props_hit_all": (bets.get("0.00") or {}).get("acierto"), "props_n": (bets.get("0.00") or {}).get("n"),
                     "props_roi_all": (bets.get("0.00") or {}).get("roi"),
                     "props_from": (ev.get("props") or {}).get("desde"), "props_to": (ev.get("props") or {}).get("hasta")},
        "track": state.get("track") or {"days": 0},
    }


def render(root: str | Path, state: dict, out: str | Path | None = None) -> Path:
    """Escribe viz/takes-nba.html (página autocontenida) a partir del estado del portal."""
    root = Path(root)
    out = Path(out) if out else root / "viz/takes-nba.html"
    tpl = (root / "web/takes_template.html").read_text(encoding="utf-8")
    assert "/*__TAKES__*/null" in tpl, "la plantilla de takes no tiene el marcador de estado"
    payload = json.dumps(build(state), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tpl.replace("/*__TAKES__*/null", payload), encoding="utf-8")
    return out
