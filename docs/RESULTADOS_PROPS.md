# Resultados del modelo de jugadores (props v1)

Generado por `python scripts/run_props.py`. Coeficientes ajustados solo con DEV (2014-2019).

## 1. Error de proyección (RMSE; menor es mejor)

| Bloque | Mercado | n | Modelo | Últimos 10 | Media temporada | Dif. MSE vs temporada (IC95 %) |
|---|---|---|---|---|---|---|
| DEV | Puntos | 144566 | **5.647** | 5.877 | 5.867 | -2.538 [-2.662; -2.414] |
| DEV | Rebotes | 144566 | **2.513** | 2.622 | 2.614 | -0.520 [-0.547; -0.490] |
| DEV | Asistencias | 144566 | **1.697** | 1.767 | 1.765 | -0.235 [-0.249; -0.223] |
| DEV | Triples | 144566 | **1.044** | 1.082 | 1.067 | -0.048 [-0.051; -0.045] |
| DEV | Pts+Reb+Ast | 144566 | **7.324** | 7.678 | 7.740 | -6.273 [-6.544; -6.024] |
| DEV | Pts+Reb | 144566 | **6.819** | 7.128 | 7.153 | -4.655 [-4.879; -4.477] |
| DEV | Pts+Ast | 144566 | **6.130** | 6.402 | 6.431 | -3.791 [-3.962; -3.618] |
| DEV | Reb+Ast | 144566 | **3.262** | 3.417 | 3.430 | -1.120 [-1.174; -1.075] |
| VAL | Puntos | 41688 | **5.945** | 6.232 | 6.206 | -3.173 [-3.430; -2.917] |
| VAL | Rebotes | 41688 | **2.500** | 2.621 | 2.603 | -0.528 [-0.579; -0.479] |
| VAL | Asistencias | 41688 | **1.765** | 1.842 | 1.829 | -0.230 [-0.257; -0.202] |
| VAL | Triples | 41688 | **1.219** | 1.265 | 1.248 | -0.072 [-0.080; -0.064] |
| VAL | Pts+Reb+Ast | 41688 | **7.594** | 8.036 | 8.050 | -7.139 [-7.680; -6.581] |
| VAL | Pts+Reb | 41688 | **7.051** | 7.436 | 7.426 | -5.429 [-5.843; -4.980] |
| VAL | Pts+Ast | 41688 | **6.461** | 6.803 | 6.801 | -4.507 [-4.897; -4.102] |
| VAL | Reb+Ast | 41688 | **3.303** | 3.480 | 3.470 | -1.134 [-1.224; -1.045] |
| TEST | Puntos | 119632 | **6.007** | 6.317 | 6.318 | -3.828 [-4.021; -3.645] |
| TEST | Rebotes | 119632 | **2.508** | 2.628 | 2.619 | -0.567 [-0.601; -0.537] |
| TEST | Asistencias | 119632 | **1.817** | 1.903 | 1.900 | -0.308 [-0.327; -0.290] |
| TEST | Triples | 119632 | **1.245** | 1.296 | 1.279 | -0.085 [-0.091; -0.080] |
| TEST | Pts+Reb+Ast | 119632 | **7.715** | 8.189 | 8.263 | -8.755 [-9.148; -8.362] |
| TEST | Pts+Reb | 119632 | **7.143** | 7.549 | 7.581 | -6.456 [-6.772; -6.192] |
| TEST | Pts+Ast | 119632 | **6.542** | 6.920 | 6.961 | -5.658 [-5.928; -5.382] |
| TEST | Reb+Ast | 119632 | **3.372** | 3.555 | 3.566 | -1.344 [-1.404; -1.272] |
| ACTUAL | Puntos | 3090 | **6.019** | 6.441 | 6.434 | -5.170 [-6.419; -3.800] |
| ACTUAL | Rebotes | 3090 | **2.460** | 2.660 | 2.664 | -1.046 [-1.243; -0.855] |
| ACTUAL | Asistencias | 3090 | **1.846** | 1.964 | 1.967 | -0.464 [-0.603; -0.350] |
| ACTUAL | Triples | 3090 | **1.241** | 1.292 | 1.295 | -0.138 [-0.179; -0.099] |
| ACTUAL | Pts+Reb+Ast | 3090 | **7.764** | 8.500 | 8.477 | -11.566 [-14.167; -9.171] |
| ACTUAL | Pts+Reb | 3090 | **7.112** | 7.711 | 7.700 | -8.708 [-10.584; -6.818] |
| ACTUAL | Pts+Ast | 3090 | **6.627** | 7.178 | 7.162 | -7.373 [-9.133; -5.495] |
| ACTUAL | Reb+Ast | 3090 | **3.389** | 3.698 | 3.694 | -2.164 [-2.597; -1.785] |

## 2. Calibración de P(over) frente a una línea ficticia (media de los últimos 10)

| Bloque | Mercado | Log loss modelo | Log loss tasa base | ECE |
|---|---|---|---|---|
| DEV | Puntos | 0.6664 | 0.6897 | 0.024 |
| DEV | Rebotes | 0.6582 | 0.6877 | 0.006 |
| DEV | Asistencias | 0.6483 | 0.6824 | 0.005 |
| DEV | Triples | 0.5223 | 0.6214 | 0.009 |
| DEV | Pts+Reb+Ast | 0.6626 | 0.6911 | 0.019 |
| DEV | Pts+Reb | 0.6638 | 0.6905 | 0.018 |
| DEV | Pts+Ast | 0.6649 | 0.6905 | 0.021 |
| DEV | Reb+Ast | 0.6585 | 0.6893 | 0.007 |
| VAL | Puntos | 0.6596 | 0.6894 | 0.018 |
| VAL | Rebotes | 0.6551 | 0.6881 | 0.007 |
| VAL | Asistencias | 0.6496 | 0.6838 | 0.005 |
| VAL | Triples | 0.5831 | 0.6537 | 0.011 |
| VAL | Pts+Reb+Ast | 0.6550 | 0.6913 | 0.017 |
| VAL | Pts+Reb | 0.6558 | 0.6905 | 0.016 |
| VAL | Pts+Ast | 0.6585 | 0.6902 | 0.015 |
| VAL | Reb+Ast | 0.6546 | 0.6895 | 0.007 |
| TEST | Puntos | 0.6579 | 0.6893 | 0.014 |
| TEST | Rebotes | 0.6527 | 0.6876 | 0.003 |
| TEST | Asistencias | 0.6479 | 0.6845 | 0.005 |
| TEST | Triples | 0.5866 | 0.6560 | 0.011 |
| TEST | Pts+Reb+Ast | 0.6529 | 0.6909 | 0.013 |
| TEST | Pts+Reb | 0.6545 | 0.6903 | 0.011 |
| TEST | Pts+Ast | 0.6559 | 0.6903 | 0.015 |
| TEST | Reb+Ast | 0.6536 | 0.6894 | 0.006 |
| ACTUAL | Puntos | 0.6313 | 0.6659 | 0.029 |
| ACTUAL | Rebotes | 0.6334 | 0.6788 | 0.027 |
| ACTUAL | Asistencias | 0.6314 | 0.6671 | 0.029 |
| ACTUAL | Triples | 0.5914 | 0.6453 | 0.030 |
| ACTUAL | Pts+Reb+Ast | 0.6286 | 0.6686 | 0.032 |
| ACTUAL | Pts+Reb | 0.6322 | 0.6645 | 0.038 |
| ACTUAL | Pts+Ast | 0.6315 | 0.6670 | 0.031 |
| ACTUAL | Reb+Ast | 0.6301 | 0.6758 | 0.023 |

## 3. Contra las líneas de cierre de DraftKings (2026-10-20 a 2026-11-09, 154 partidos)

| Mercado | n | MAE línea | MAE modelo | MAE últimos 10 |
|---|---|---|---|---|
| Puntos | 2148 | 4.911 | 5.126 | 5.337 |
| Rebotes | 1996 | 2.007 | 2.000 | 2.102 |
| Asistencias | 1516 | 1.646 | 1.663 | 1.726 |
| Triples | 1728 | 1.160 | 1.139 | 1.161 |
| Pts+Reb+Ast | 1637 | 6.413 | 6.695 | 7.022 |
| Pts+Reb | 2004 | 5.745 | 5.984 | 6.212 |
| Pts+Ast | 1557 | 5.627 | 5.908 | 6.114 |
| Reb+Ast | 1535 | 2.794 | 2.822 | 2.985 |

Apuestas simuladas a los precios reales siguiendo al modelo (ventaja = P modelo − P de la casa sin margen):

| Ventaja mínima | n | Acierto | ROI | IC95 % |
|---|---|---|---|---|
| 0 pp | 14114 | 52.7 % | -1.5 % | [-4.0; +1.1] |
| 3 pp | 11373 | 53.2 % | -0.6 % | [-3.4; +2.4] |
| 6 pp | 8820 | 54.0 % | +0.8 % | [-2.3; +4.0] |
| 10 pp | 5941 | 54.9 % | +2.4 % | [-2.2; +6.8] |

Regresión logística de «over» sobre casa y modelo (n = 14114): peso de la casa 0.77 ± 0.10, peso del modelo 0.25 ± 0.03. Log loss: casa 0.6889, modelo 0.7063.
