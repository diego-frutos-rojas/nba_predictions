"""Métricas de evaluación probabilística y utilidades estadísticas."""
from __future__ import annotations

import numpy as np

EPS = 1e-9


def log_loss(p, y):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def brier(p, y):
    return float(((np.asarray(p, float) - np.asarray(y, float)) ** 2).mean())


def accuracy(p, y):
    return float(((np.asarray(p) > 0.5) == (np.asarray(y) == 1)).mean())


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + np.exp(-np.asarray(x, float)))


def paired_bootstrap_diff(loss_a, loss_b, n_boot=2000, seed=0):
    """IC 95 % de mean(loss_a - loss_b) con bootstrap por partido (a<b => A mejor)."""
    d = np.asarray(loss_a, float) - np.asarray(loss_b, float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(axis=1)
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def per_game_logloss(p, y):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calibration_table(p, y, bins=(0, .2, .3, .4, .5, .6, .7, .8, 1.0)):
    p, y = np.asarray(p, float), np.asarray(y, float)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum():
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(m.sum()),
                        "pred": float(p[m].mean()), "real": float(y[m].mean())})
    return out


def calibration_error(p, y, bins=10):
    """ECE: error medio ponderado entre probabilidad predicha y frecuencia real."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.sum():
            tot += m.sum() / len(p) * abs(p[m].mean() - y[m].mean())
    return float(tot)
