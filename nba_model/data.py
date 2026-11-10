"""Carga y limpieza de datos históricos NBA (resultados + líneas de cierre).

Fuentes (todas en GitHub, descargables con scripts/fetch_history.py):
  - SBR (flancast90/sportsbookreview-scraper, MIT): 2011-12 a 2021-22, con spread y ML de cierre.
  - ESPN vía sportsdataverse: calendarios con marcadores 2019-20 a 2026-27.
  - hoopR (sportsdataverse): spread de cierre de consenso 2020 (burbuja) a 2026.

Convención: `season` = año en que termina la temporada (2012 = 2011-12).
`close_spread_home` < 0 significa que el local es favorito (convención habitual).
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

URLS = {
    "sbr.json": "https://raw.githubusercontent.com/flancast90/sportsbookreview-scraper/master/data/nba_archive_10Y.json",
    "hoopr_lines.parquet": "https://raw.githubusercontent.com/sportsdataverse/hoopR-nba-data/main/nba/betting_lines/closing_lines_odds_api.parquet",
    **{f"sched_{y}.parquet": f"https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_schedules/nba_schedule_{y}.parquet"
       for y in range(2012, 2028)},
    **{f"pbox_{y}.parquet": f"https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_{y}.parquet"
       for y in range(2012, 2028)},
}

NICK = {
    "Hawks": "ATL", "Celtics": "BOS", "Nets": "BKN", "NewJersey": "BKN", "Hornets": "CHA", "Bulls": "CHI",
    "Cavaliers": "CLE", "Mavericks": "DAL", "Nuggets": "DEN", "Pistons": "DET", "Warriors": "GSW",
    "Golden State": "GSW", "Rockets": "HOU", "Pacers": "IND", "Clippers": "LAC", "LA Clippers": "LAC",
    "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA", "Bucks": "MIL", "Timberwolves": "MIN",
    "Pelicans": "NOP", "Knicks": "NYK", "Thunder": "OKC", "Oklahoma City": "OKC", "Magic": "ORL",
    "Seventysixers": "PHI", "76ers": "PHI", "Suns": "PHX", "Trailblazers": "POR", "Trail Blazers": "POR",
    "Kings": "SAC", "Spurs": "SAS", "Raptors": "TOR", "Jazz": "UTA", "Wizards": "WAS",
}
TEAMS = sorted(set(NICK.values()))
# Abreviaturas de ESPN -> código canónico (cubre los cambios Bobcats/Hornets, Hornets/Pelicans, NJ/BKN)
ABBR = {"ATL": "ATL", "BKN": "BKN", "NJ": "BKN", "BOS": "BOS", "CHA": "CHA", "CHI": "CHI", "CLE": "CLE",
        "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW", "GSW": "GSW", "HOU": "HOU", "IND": "IND",
        "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NO": "NOP",
        "NOP": "NOP", "NY": "NYK", "NYK": "NYK", "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHX": "PHX",
        "POR": "POR", "SA": "SAS", "SAS": "SAS", "SAC": "SAC", "TOR": "TOR", "UTAH": "UTA", "UTA": "UTA",
        "WSH": "WAS", "WAS": "WAS"}
# Partidos de temporada regular por campaña (para separar playoffs en SBR, que no los marca)
SBR_REG_GAMES = {2011: 990}  # temporada del cierre patronal: 66 partidos por equipo
SBR_DEFAULT_REG_GAMES = 1230

COLS = ["game_id", "date", "season", "home", "away", "home_pts", "away_pts", "neutral",
        "close_spread_home", "close_ml_home", "close_ml_away", "close_total", "source"]


def fetch_history(dest: str | Path, force: bool = False, current_season: int = 2027) -> None:
    """Descarga los ficheros crudos a `dest` (≈ 20 MB la primera vez).

    Los ficheros históricos solo se bajan si faltan. Los de la temporada en curso (calendario, cajas de jugadores)
    y las líneas de hoopR se vuelven a descargar SIEMPRE, para tener los últimos resultados.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    always = {f"sched_{current_season}.parquet", f"pbox_{current_season}.parquet", "hoopr_lines.parquet"}
    for name, url in URLS.items():
        f = dest / name
        if f.exists() and not force and name not in always:
            continue
        print("descargando", name)
        req = urllib.request.Request(url, headers={"User-Agent": "nba-model/0.2"})
        with urllib.request.urlopen(req, timeout=120) as r:
            f.write_bytes(r.read())


def _repair_sbr_lines(a: pd.DataFrame) -> pd.DataFrame:
    """En ~6,7 % de las filas de SBR el spread y el total vienen intercambiados
    (spread=178, total=4). Se detectan por magnitud y se corrigen; el signo del spread
    reparado sale del favorito de la moneyline de cierre. Total < 100 => dato ausente."""
    a = a.copy()
    swapped = a.home_close_spread.abs() > 60
    spread_abs = a.close_over_under.where(swapped, a.home_close_spread.abs())
    total = a.home_close_spread.abs().where(swapped, a.close_over_under)
    home_fav = a.home_close_ml < a.away_close_ml
    fixed = np.where(home_fav, -spread_abs, spread_abs)
    a["home_close_spread"] = np.where(swapped, np.where(spread_abs == 0, 0.0, fixed), a.home_close_spread)
    a["close_over_under"] = total.where(total >= 100)
    a.attrs["n_swapped_fixed"] = int(swapped.sum())
    return a


def load_sbr(path: str | Path) -> pd.DataFrame:
    """SBR 2011-12 .. 2018-19 (temporada regular). Se descartan filas basura y playoffs."""
    a = pd.DataFrame(json.load(open(path)))
    a["home_team"], a["away_team"] = a.home_team.astype(str), a.away_team.astype(str)
    a = a[a.home_team.isin(NICK) & a.away_team.isin(NICK)].copy()          # quita filas con equipo "0"
    for c in ("home_final", "away_final"):
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a = a.dropna(subset=["home_final", "away_final"])
    a = a[(a.home_final > 0) & (a.away_final > 0)]
    for c in ("home_close_spread", "close_over_under", "home_close_ml", "away_close_ml"):
        a[c] = pd.to_numeric(a[c], errors="coerce")
    a = _repair_sbr_lines(a)
    a["date"] = pd.to_datetime(a["date"].astype(int).astype(str), format="%Y%m%d")
    a = a.sort_values(["date"], kind="mergesort").reset_index(drop=True)
    out = []
    for s, g in a.groupby("season"):
        n = SBR_REG_GAMES.get(s, SBR_DEFAULT_REG_GAMES)
        out.append(g.head(n))                                                  # primeros N partidos = temporada regular
    a = pd.concat(out)
    a = a[a.season <= 2018]                                                    # 2019+ viene de ESPN
    df = pd.DataFrame({
        "game_id": ["sbr_%d" % i for i in range(len(a))],
        "date": a.date.values, "season": a.season.values + 1,
        "home": a.home_team.map(NICK).values, "away": a.away_team.map(NICK).values,
        "home_pts": a.home_final.astype(int).values, "away_pts": a.away_final.astype(int).values,
        "neutral": False,
        "close_spread_home": a.home_close_spread.values,
        "close_ml_home": a.home_close_ml.values, "close_ml_away": a.away_close_ml.values,
        "close_total": a.close_over_under.values, "source": "sbr",
    })
    return df[COLS]


def load_espn(raw_dir: str | Path, seasons=range(2012, 2028)) -> pd.DataFrame:
    """Temporada regular completada de ESPN (2011-12 en adelante). Fuente única de resultados."""
    parts = []
    for y in seasons:
        f = Path(raw_dir) / f"sched_{y}.parquet"
        if not f.exists():
            continue
        s = pd.read_parquet(f)
        s = s[(s.season_type == 2) & (s.status_type_completed == True)]       # noqa: E712
        s = s[s.home_abbreviation.isin(ABBR) & s.away_abbreviation.isin(ABBR)]      # quita All-Star y otros
        parts.append(pd.DataFrame({
            "game_id": s.game_id.astype("int64").astype(str).values,
            "date": pd.to_datetime(s.game_date).values, "season": y,
            "home": s.home_abbreviation.map(ABBR).values, "away": s.away_abbreviation.map(ABBR).values,
            "home_pts": pd.to_numeric(s.home_score).astype(int).values,
            "away_pts": pd.to_numeric(s.away_score).astype(int).values,
            "neutral": s.neutral_site.fillna(False).astype(bool).values,
        }))
    df = pd.concat(parts).drop_duplicates("game_id")
    for c in ("close_spread_home", "close_ml_home", "close_ml_away", "close_total"):
        df[c] = np.nan
    df["source"] = "espn"
    return df[COLS]


def attach_hoopr_lines(espn: pd.DataFrame, path: str | Path) -> pd.DataFrame:
    """Añade el spread de cierre de consenso (hoopR). home_point < 0 => local favorito."""
    ln = pd.read_parquet(path)
    ln["game_id"] = ln.game_id.astype("int64").astype(str)
    m = espn.merge(ln[["game_id", "home_point", "over_under", "n_books"]], on="game_id", how="left")
    m["close_spread_home"] = m["home_point"]
    m["close_total"] = m["over_under"]
    return m.drop(columns=["home_point", "over_under", "n_books"])


def attach_sbr_lines(espn: pd.DataFrame, sbr: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cruza líneas de cierre SBR (2012-2019) con partidos ESPN por (temporada, local, visitante)
    y fecha con tolerancia de ±1 día (SBR a veces fecha un día distinto). Valida marcadores."""
    keys = ["season", "home", "away"]
    cand = espn[espn.season <= 2019][keys + ["game_id", "date", "home_pts", "away_pts"]].merge(
        sbr[keys + ["date", "home_pts", "away_pts", "close_spread_home", "close_ml_home", "close_ml_away", "close_total"]],
        on=keys, suffixes=("", "_sbr"))
    cand["dd"] = (cand.date - cand.date_sbr).abs().dt.days
    cand = cand[cand.dd <= 1].sort_values("dd").drop_duplicates("game_id").drop_duplicates(
        keys + ["date_sbr"])
    score_ok = ((cand.home_pts == cand.home_pts_sbr) & (cand.away_pts == cand.away_pts_sbr)).mean()
    out = espn.merge(cand[["game_id", "close_spread_home", "close_ml_home", "close_ml_away", "close_total"]],
                     on="game_id", how="left", suffixes=("", "_l"))
    for c in ("close_spread_home", "close_ml_home", "close_ml_away", "close_total"):
        out[c] = out[c].where(out[c].notna(), out[c + "_l"]) if c + "_l" in out else out[c]
    out = out.drop(columns=[c for c in out.columns if c.endswith("_l")])
    info = {"sbr_rows": len(sbr), "matched": len(cand), "score_agreement": float(score_ok)}
    return out, info


def build_games(raw_dir: str | Path, return_info: bool = False):
    """Dataset unificado 2011-12 .. 2026-27 con resultados ESPN y líneas de cierre (SBR / hoopR)."""
    raw_dir = Path(raw_dir)
    espn = load_espn(raw_dir)
    espn = attach_hoopr_lines(espn[espn.season >= 2020].copy(), raw_dir / "hoopr_lines.parquet").pipe(
        lambda later: pd.concat([espn[espn.season < 2020], later], ignore_index=True))
    sbr = load_sbr(raw_dir / "sbr.json")
    df, info = attach_sbr_lines(espn, sbr)
    df["source"] = np.where(df.season <= 2019, "sbr_lines", "hoopr_lines")
    df = df.sort_values(["date", "game_id"], kind="mergesort").reset_index(drop=True)
    df["home_margin"] = df.home_pts - df.away_pts
    return (df, info) if return_info else df


def add_rest(df: pd.DataFrame) -> pd.DataFrame:
    """Días de descanso de cada equipo (sin fuga: solo mira partidos anteriores).

    rest_*: días naturales desde el partido anterior de ese equipo (se corta en 7;
    el primero de la temporada vale 7). Descanso 1 = jugó ayer (back-to-back).
    """
    df = df.sort_values(["date", "game_id"], kind="mergesort").reset_index(drop=True)
    last: dict[str, tuple[int, pd.Timestamp]] = {}
    rh, ra = [], []
    for h, a, d, s in zip(df.home, df.away, df.date, df.season):
        for t, out in ((h, rh), (a, ra)):
            prev = last.get(t)
            out.append(7 if (prev is None or prev[0] != s) else min(7, (d - prev[1]).days))
        last[h] = (s, d)
        last[a] = (s, d)
    df["rest_home"], df["rest_away"] = rh, ra
    return df


def rest_days_before(df: pd.DataFrame, team: str, date) -> int:
    """Días desde el último partido del equipo hasta `date` (convención del modelo: 1 = jugó ayer;
    7 = 7 o más días o primer partido de la temporada). Solo mira partidos anteriores a `date`."""
    date = pd.Timestamp(date)
    prev = df[((df.home == team) | (df.away == team)) & (df.date < date)].date
    return 7 if prev.empty else int(min(7, (date - prev.max()).days))
