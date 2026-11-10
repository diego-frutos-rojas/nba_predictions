"""Utilidades de cuotas y probabilidad. Solo biblioteca estándar."""
from statistics import NormalDist

_N = NormalDist()


def normal_cdf(x: float) -> float:
    return _N.cdf(x)


def normal_ppf(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return _N.inv_cdf(p)


def american_to_implied(odds: float) -> float:
    """Probabilidad implícita (con margen de la casa) de una cuota americana."""
    if abs(odds) < 100:
        raise ValueError(f"Cuota americana no válida: {odds}")
    return -odds / (-odds + 100) if odds < 0 else 100 / (odds + 100)


def american_to_decimal(odds: float) -> float:
    return 1 + odds / 100 if odds > 0 else 1 + 100 / -odds


def remove_vig(p_home: float, p_away: float) -> tuple[float, float, float]:
    """Devuelve (p_home_sin_margen, p_away_sin_margen, margen_de_la_casa)."""
    total = p_home + p_away
    return p_home / total, p_away / total, total - 1


def expected_value(p_model: float, odds: float) -> float:
    """Valor esperado por 1 unidad apostada."""
    d = american_to_decimal(odds)
    return p_model * (d - 1) - (1 - p_model)


def kelly_fraction(p_model: float, odds: float, fraction: float = 0.25) -> float:
    """Kelly fraccionado. 0 si no hay valor esperado positivo."""
    d = american_to_decimal(odds)
    full = (p_model * d - 1) / (d - 1)
    return max(0.0, full) * fraction
