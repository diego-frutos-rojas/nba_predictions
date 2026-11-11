"""Comparación del modelo con el mercado."""
from __future__ import annotations

import json
from pathlib import Path

from .baselines import SIGMA_MARKET
from .odds import american_to_implied, normal_cdf, normal_ppf, remove_vig


def load_market(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def reference_prob(game: dict, sigma: float = SIGMA_MARKET) -> dict:
    """Probabilidad de victoria del local según la mejor referencia disponible.

    Prioridad: cuotas de ambos lados sin margen > cuota de un lado (con margen)
    > spread convertido con la normal > proveedor de datos.
    """
    o = game.get("odds") or {}
    h, a = o.get("home"), o.get("away")
    if h is not None and a is not None:
        ph, _, vig = remove_vig(american_to_implied(h), american_to_implied(a))
        return {"p": ph, "kind": "ml_no_vig", "is_market": True, "vig": vig}
    if h is not None:
        return {"p": american_to_implied(h), "kind": "ml_one_side_with_vig", "is_market": True}
    if a is not None:
        return {"p": 1 - american_to_implied(a), "kind": "ml_one_side_with_vig", "is_market": True}
    if game.get("spread_home_margin") is not None:
        return {"p": normal_cdf(game["spread_home_margin"] / sigma), "kind": "spread_converted", "is_market": True}
    return {"p": game["provider_home_prob"], "kind": "provider", "is_market": False}


def needed_adjustment_pts(base_margin: float, target_p: float, sigma: float) -> float:
    """Puntos de margen que habría que añadir al modelo para igualar `target_p`. `sigma` = la del modelo (sin valor por defecto a propósito)."""
    return sigma * normal_ppf(target_p) - base_margin


def cover_prob_home(model_margin: float, spread_home_margin: float, sigma: float) -> float:
    """P(el local cubre) si el mercado espera `spread_home_margin` para el local. `sigma` = la del modelo."""
    return normal_cdf((model_margin - spread_home_margin) / sigma)
