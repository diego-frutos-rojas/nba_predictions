# Resultados (generado por scripts/run_pipeline.py)

Bloques: DEV 2014-2019 (afinado), VAL 2020-2021 (no usado), TEST 2022-2026 (no usado).

| Bloque | Modelo | Log loss | Brier | Acierto | ECE | n |
|---|---|---|---|---|---|---|
| DEV | Siempre local | 0.6793 | 0.2431 | 58.3 % | 0.0039 | 7380 |
| DEV | v0 (ridge, walk-forward) | 0.6180 | 0.2144 | 65.6 % | 0.0145 | 7380 |
| DEV | v2 (Elo + contexto) | 0.6029 | 0.2083 | 67.0 % | 0.0134 | 7380 |
| DEV | Mercado (spread de cierre) | 0.5888 | 0.2023 | 68.5 % | 0.0157 | 7380 |
| VAL | Siempre local | 0.6919 | 0.2493 | 54.7 % | 0.0397 | 2139 |
| VAL | v0 (ridge, walk-forward) | 0.6451 | 0.2265 | 63.3 % | 0.0520 | 2139 |
| VAL | v2 (Elo + contexto) | 0.6327 | 0.2215 | 64.4 % | 0.0267 | 2139 |
| VAL | Mercado (spread de cierre) | 0.6240 | 0.2175 | 65.3 % | 0.0335 | 1158 |
| TEST | Siempre local | 0.6898 | 0.2483 | 55.3 % | 0.0339 | 6153 |
| TEST | v0 (ridge, walk-forward) | 0.6329 | 0.2207 | 65.0 % | 0.0371 | 6153 |
| TEST | v2 (Elo + contexto) | 0.6117 | 0.2120 | 66.2 % | 0.0204 | 6153 |
| TEST | Mercado (spread de cierre) | 0.5922 | 0.2035 | 68.6 % | 0.0233 | 6151 |

## TEST: diferencias de log loss (IC95 % bootstrap por partido; negativo = el primero es mejor)

- v2_menos_v0: -0.0211 [-0.0266, -0.0154]
- v2_menos_mercado: +0.0194 [+0.0141, +0.0246]

## ¿Aporta el modelo algo además del mercado?

- Blend logístico ajustado en DEV: peso del mercado 0.954, peso del modelo 0.024.
- TEST log loss: mercado 0.5922, blend 0.5918 (dif -0.0003).

- DEV: fracción real de la discrepancia modelo-mercado c2 = -0.028 ± 0.117 (t = -0.5); sd de la discrepancia 2.61 pts.
- TEST: fracción real de la discrepancia modelo-mercado c2 = -0.067 ± 0.124 (t = -1.0); sd de la discrepancia 3.06 pts.

## Apuestas simuladas al spread a -110 siguiendo al modelo (umbral en puntos de discrepancia)

| Umbral | DEV n | DEV ROI | TEST n | TEST ROI | TEST IC95 |
|---|---|---|---|---|---|
| 1 | 5006 | -4.2 % | 4477 | -6.3 % | [-9.0, -3.5] |
| 2 | 3052 | -4.7 % | 3051 | -6.4 % | [-9.8, -3.1] |
| 3 | 1682 | -5.5 % | 1858 | -7.0 % | [-11.3, -2.7] |
| 4 | 858 | -7.6 % | 1091 | -9.3 % | [-14.9, -3.7] |
| 5 | 430 | -4.2 % | 592 | -9.9 % | [-17.5, -2.3] |

Referencia: apostar sin información a -110 pierde ≈ 4,5 % (comisión).
