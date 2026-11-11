# Auditoría y mejora del modelo NBA (v0 → v2)

Fecha de los datos: 10 de noviembre de 2026. Todo es reproducible con `python scripts/run_pipeline.py`.

## 1. Resumen

| | v0 (el que entregué antes) | v2 (nuevo) | Mercado (spread de cierre) |
|---|---|---|---|
| Log loss TEST 2022-26 | 0,6329 | **0,6117** | 0,5922 |
| Acierto TEST | 65,0 % | **66,3 %** | 68,6 % |
| Error de calibración (ECE) TEST | 0,037 | **0,021** | 0,023 |

* v2 mejora a v0 en **−0,0211** de log loss (IC95 % bootstrap [−0,0266; −0,0154]) en 6.153 partidos que **no se usaron para ajustar nada**.
* La mejora es la misma en el bloque de desarrollo y en el de prueba: v2 cierra el **52 % de la distancia entre v0 y el mercado** en DEV y el **52 %** en TEST. Eso es lo que se espera de una mejora real y no de sobreajuste.
* **v2 sigue sin batir al mercado**: +0,0194 de log loss peor (IC95 % [+0,0141; +0,0246]).
* Lo más importante para usarlo: **las discrepancias entre el modelo y el mercado no contienen información real** (sección 6). Seguir al modelo en apuestas simuladas pierde dinero.

## 2. Qué se auditó y cómo

* **Datos nuevos**: 15 temporadas (2011-12 a 2025-26 más lo jugado de 2026-27), 18.037 partidos de temporada regular, con resultados de ESPN (marcadores coinciden en el 99,9 % con SBR), líneas de cierre de SBR (2011-12 a 2018-19) y de hoopR/Odds API (2019-20 a 2025-26), y 467.000 filas de cajas de jugadores.
* **Protocolo anti-sobreajuste** (fijado antes de mirar resultados):
  * DEV = temporadas 2014-2019 (2012-2013 de calentamiento). Es lo único con lo que se afinó.
  * VAL = 2020-2021 (años de pandemia) y TEST = 2022-2026. No se usaron para elegir nada.
  * Todo es *walk-forward*: cada predicción solo usa partidos anteriores (hay tests automáticos que lo comprueban).

## 3. Hallazgos sobre v0

1. **El backtest de v0 no valía** (17/20 aciertos, Brier 0,134). Era *leave-one-out* sin orden temporal y el prior de récord incluía los partidos "predichos". Con el mismo método bien medido (walk-forward) v0 acierta el 65,0 % y su log loss es 0,633.
2. **Ventaja de campo fija en 3,0 puntos.** La real ha bajado: margen medio del local 1,7 (2022), 2,5 (2023), 2,1 (2024), 1,7 (2025), 1,7 (2026) y 1,5 (2026-27 hasta ahora). v0 regalaba ~1 punto al local.
3. **Dispersión fija σ = 12.** El margen de la NBA es más variable cada año (desviación típica 13,4 en 2012 → 16,5 en 2026-27). v0 estaba sobreconfiado: en TEST daba 0,65 a partidos que el local ganó el 59 % de las veces.
4. **No tenía descanso ni bajas.** El back-to-back cuesta ≈1,5 puntos y las bajas de rotación mueven la línea.
5. **Datos con fallos** (afectan a quien use SBR directamente): en el 6,7 % de las filas el spread y el total vienen intercambiados (`spread=178`, `total=4`). Con ese error la correlación spread–resultado era 0,07-0,15 en vez de 0,46. Está reparado y testeado (`_repair_sbr_lines`).
6. **El valor esperado de v0 era un falso positivo.** En Utah–Miami daba EV +0,81 por euro; mercado y proveedor decían 22 %. Ver sección 6.

## 4. Mejoras de v2 (cada una tiene un motivo medido)

| Cambio | Para qué | Parámetro |
|---|---|---|
| Ratings secuenciales tipo Elo con margen recortado | Usar todo el historial en vez de 20 partidos | `k`, `cap` |
| Regresión a la media entre temporadas | Los equipos cambian | `carry` |
| Ventaja de campo adaptativa | Se mueve con los años y con la pandemia | `hca0`, `lr_hca` |
| Dispersión estimada online | El margen es más variable cada año | `sig_scale` |
| Descanso (back-to-back) | −1,5 pts medidos | `rest_b2b`, `rest_long` |
| Más aprendizaje al inicio de temporada | Ratings menos fiables | `boost` |
| **Disponibilidad de plantilla** (talento que juega hoy frente al habitual, ponderado por calidad) | Convierte bajas y regresos en puntos de margen | `avail` |

Son 10 parámetros para 7.380 partidos de desarrollo.

## 5. Controles contra el sobreajuste y lo que se descartó

* **Validación cruzada temporal**: afinar en 2014-16 y evaluar en 2017-19 (y al revés). Los parámetros salen casi iguales en ambos sentidos (`k` ≈ 0,031 en las dos búsquedas, `avail` ≈ 0,045 en las dos) y la ganancia fuera de muestra es la misma que dentro.
* **Promediar el 5 % mejor de 700 configuraciones** en vez de quedarse con la mejor. Quedarse con la mejor empeoraba fuera de muestra (0,5966 frente a 0,5939); promediar generaliza.
* **Contrastes pre-especificados** (2 sobre el residuo del mercado, 3 segmentos) con umbral corregido por comparaciones múltiples.
* **Descartado: modelo de impacto de jugador** (tipo plus-minus ajustado con solo marcadores de partido). Mejoraba dentro de muestra (0,5932 → 0,5884) y no fuera (0,6178 → 0,6172): sobreajuste clásico. Queda en `nba_model/player_model.py` como experimento documentado; con datos de quintetos (stints) podría funcionar.
* **Corregido: primera versión de la disponibilidad.** El "talento habitual" se calculaba con una plantilla que crecía durante las primeras jornadas, así que salía sesgado (+41 minutos en NYK, +63 en PHX). Se detectó al revisar el informe de esta noche, se arregló (misma plantilla en el numerador y el denominador) y se validó **solo con DEV** antes de reevaluar. El efecto pasó de −0,0009 a −0,0026 de log loss y se volvió más estable.
* **Corregido (11-nov-2026): recorte de la disponibilidad en `elo.run_elo`.** El recorte a ±60 estaba escrito con un condicional en línea
  que, si `avail_home` > 60, devolvía 60 y **descartaba el término del visitante** (precedencia de `a if c else b - x`). Afectaba a 81
  partidos (6 DEV, 12 VAL, 63 TEST); el portal, el analizador web y `run_report` ya recortaban bien. Con los parámetros congelados el
  efecto es despreciable (TEST 0,61168 → 0,61168; DEV 0,60294 → 0,60292). Test de regresión: `test_elo_avail_clips_each_side_independently`.
* **Descartado (11-nov-2026): ajuste de plantilla en verano.** Al primer partido de cada equipo, rating += w·D, con D = valor
  (`AvailabilityTracker.value`) de quienes juegan ese partido − valor de la rotación final de la temporada anterior. Rejilla w ∈ {0…0,08} ×
  carry ∈ {0,60…0,90}, resto congelado. Validación cruzada en DEV: afinando en 2014-16 elige w=0,04/carry=0,90 y **empeora** 2017-19
  (+0,0015; en los 20 primeros partidos +0,0078); afinando en 2017-19 elige w=0. Inestable: no se adopta. El *prior* con proyecciones de
  victorias de las casas (hoja de ruta, punto 3) sigue pendiente porque necesita datos externos.
* **Descartado (11-nov-2026): recalibración de Platt** (a + b·logit p) ajustada en una mitad de DEV: empeora la otra en los dos sentidos
  (+0,0010 y +0,0003; b = 1,13 y 0,98). La pendiente de calibración no es estable entre periodos; se mantiene sin recalibrar.

## 6. ¿Bate al mercado? No

Todas las pruebas, en TEST salvo donde se indica, con el modelo congelado:

* **Blend** logístico modelo+mercado (ajustado en DEV): peso del modelo 0,023 (≈ 0). Mejora el log loss del mercado en 0,0003: despreciable.
* **Parte real de la discrepancia** (regresión del margen real sobre margen del mercado y discrepancia): c2 = −0,07 ± 0,12 (DEV: −0,03 ± 0,12). Es decir, **0 % de la discrepancia es información**.
* **Apuestas simuladas al spread a −110 siguiendo al modelo** (umbral de 1 a 5 puntos de discrepancia): ROI de −6 % a −10 % en TEST (n entre 595 y 4.484), peor que el −4,5 % que cuesta apostar al azar por la comisión.
* **Descanso y bajas**: el mercado ya los incorpora (back-to-back t = −1,5; disponibilidad t = −0,5, no significativos).
* **Segmentos** (inicio de temporada, final, back-to-back): ninguno aporta.

Implicación: las "apuestas con valor" de un modelo basado en resultados y minutos son casi siempre un error del modelo. Un edge real necesitaría información que el mercado no tenga todavía (por ejemplo noticias de lesión antes de que se muevan las líneas), medida contra cuotas de apertura y cierre con marca de tiempo. Aun así, a −110 el valor esperado por defecto es negativo.

## 7. Efecto en los partidos de esta noche (10-nov-2026)

| Partido | P(local) v0 | P(local) v2 | Mercado | Diferencia v0 → v2 |
|---|---|---|---|---|
| MIA en UTA | 42,7 % | 32,4 % | 22,5 % | +20,2 → +9,9 pp |
| ORL en SAC | 48,0 % | 37,8 % | 33,5 % | +14,5 → +4,3 pp |
| OKC en POR | 33,5 % | 42,3 % | 45,0 % (una cuota) | −11,6 → −2,7 pp |
| MIL en NYK | 85,8 % | 86,3 % | 91,6 % (spread) | −5,8 → −5,3 pp |

Las diferencias se reducen mucho, que es lo que ya mostraba el backtest: v0 las generaba por no conocer descanso, bajas ni la ventaja de campo actual. En términos de margen, las discrepancias con el mercado son de +3,2 (UTA), +1,2 (SAC), −0,2 (POR) y −0,5 (NYK) puntos, todas dentro de ~1 desviación típica (3,1 puntos) de la discrepancia habitual.

*Corrección posterior*: una versión anterior de `run_report.py` pasaba los días de descanso del JSON (0 = back-to-back, 1 = un día libre) como si fueran la convención del modelo (1 = jugó ayer), por lo que casi todos los equipos recibían la penalización de back-to-back por error. Ahora el descanso se calcula siempre desde las fechas reales (`rest_days_before`, con test).

## 8. Limitaciones

* El mercado de referencia es el spread de cierre de consenso (hoopR) y SBR; el spread se convierte a probabilidad con σ = 11,25 (ajustada en DEV). No hay cuotas históricas de moneyline después de 2019.
* La disponibilidad histórica usa quién jugó realmente (equivale a la lista de inactivos pública antes del salto inicial). Hoy se sustituye por el parte de lesiones con probabilidades de jugar, que es más incierto.
* El calendario de ESPN llegaba hasta el 8-nov; los resultados del 9-nov se añaden desde `data/snapshot_2026-11-10/games.csv` sin cajas de jugadores.
* Calibración: pendiente 1,05-1,08 en TEST (v2 es ligeramente poco confiado). No se recalibró para no sobreajustar.
* PHI-BOS y PHX-LAC siguen sin línea de hoy confirmada.

## 9. Modelo de jugadores (props v1) y portal diario

Reproducible con `python scripts/run_props.py`; cifras completas en `docs/RESULTADOS_PROPS.md`.

**Qué es.** Para cada jugador: minutos esperados × ritmo por minuto × contexto (rival, bajas de compañeros, casa, total de
puntos del mercado), con una binomial negativa alrededor de la media para obtener P(más de la línea). 10 coeficientes de
minutos y 7 por estadística, ajustados por mínimos cuadrados con 144.566 filas jugador-partido de DEV (2014-2019). Las
constantes de memoria se fijaron a priori; la mezcla de forma rápida y lenta la decide la regresión.

**Frente a las medias simples (RMSE, puntos).** DEV 5,65 · VAL 5,95 · TEST 6,01 · 2026-27 6,02, frente a 5,87 / 6,21 / 6,32 /
6,43 de la media de temporada. La mejora se mantiene o crece fuera de muestra en las ocho estadísticas (IC95 % de la
diferencia siempre por debajo de cero). Calibración de P(over) en TEST: ECE entre 0,003 y 0,015.

**Frente a la casa (líneas de cierre de DraftKings, 154 partidos, 20-oct a 9-nov-2026, 14.114 líneas).**
* La línea falla menos que el modelo en puntos (error medio 4,91 frente a 5,13) y combinadas; empatan en rebotes y triples.
* Apuestas simuladas a precios reales: −1,5 % (todas), −0,6 % (ventaja ≥ 3 pp), +0,8 % (≥ 6 pp), +2,4 % (≥ 10 pp, IC95 %
  [−2,2; +6,8]). Ningún intervalo excluye el cero. Umbrales fijados antes de mirar.
* El modelo aporta algo que la casa no tiene del todo (peso 0,25 ± 0,03 en una regresión conjunta, casa 0,77 ± 0,10), pero
  no lo bastante para superar el margen de forma demostrable.

**Cautelas de ese contraste.** (1) Son tres semanas. (2) Las bajas se toman de quién jugó de verdad (como en el resto del
proyecto); en vivo se usa el parte de lesiones, más incierto. (3) Solo cuentan jugadores que jugaron (si no, la apuesta se
anula). (4) ESPN fecha esas líneas después del partido (liquidación); su error, 4,9 puntos, es el de una línea previa al
partido, pero no hay marca de tiempo que lo confirme. (5) Ese periodo ya se miró (punto siguiente). La prueba limpia es el
historial que el portal guarda cada día.

**Qué se corrigió y qué se descartó.**
* *Sesgo de inicio de temporada.* La primera versión sobreestimaba minutos (+1,8) y puntos (+1,7) en las tres primeras
  semanas de 2026-27. Se comprobó que pasaba igual en todas las temporadas de DEV (+0,9 a +1,3 minutos), se añadieron dos
  variables (`depth`: minutos habituales de los que juegan frente a 240; `early`: partidos del jugador en la temporada), se
  validaron solo con DEV (sesgo inicial de minutos −0,05 y −0,39 en las dos mitades; MAE de puntos 4,452 → 4,432 y 4,342 →
  4,319) y se reevaluó. Consecuencia: TEST se miró dos veces y el periodo 2026-27 ya no es virgen.
* *Encogimiento hacia la liga.* Daba triples a pívots que no tiran; se cambió por encogimiento hacia la media de carrera.
* *Varianza proporcional a la media.* Infravaloraba la dispersión de suplentes; se cambió a a·mu^p ajustada por tramos.
* *Descartado: bajas de larga duración* (`missl`, lo que falta hoy frente a lo que faltaba durante la memoria del ritmo
  lento). Mejora en DEV de 0,02 % en RMSE: no compensa la complejidad.
* *Alineación esperada en vivo.* Con DEV 2018-19: contar a todos los sanos da 248 minutos, ponderar a todos por su fracción
  de apariciones 215, y la regla elegida (peso 1 si jugó al menos la mitad de los últimos partidos) 232 frente a 235 reales.

**Datos nuevos.** La API pública de ESPN da jornada, cuotas de DraftKings (apertura y actual), parte de lesiones, cajas y
props de jugador. No etiqueta cuál precio es over y cuál under: van en ese orden, comprobado con el mercado de «hitos» en
475 de 493 casos (los 18 restantes tenían los dos precios casi iguales); si un hito lo contradice, el precio no se usa.
