# Sitio web del modelo NBA

Sitio estático (HTML + CSS + JS, sin servidor ni dependencias) que enseña lo que calcula el modelo: la jornada, las
proyecciones de jugadores, los mercados de equipo, la liga y el historial real de aciertos. Se abre con doble clic y
se puede subir tal cual a cualquier alojamiento estático (GitHub Pages, Netlify, un bucket).

```
uv run python webapp/build.py --open                         # genera webapp/dist y lo abre
uv run python webapp/build.py --bundle viz/sitio-nba.html    # además, todo en un solo archivo para compartir
uv run python webapp/build.py --portal                       # además, el portal de un solo archivo de siempre
```

En Windows también vale el doble clic en `sitio.bat` (en Mac y Linux, `./sitio.sh`): usan el entorno `.venv` del proyecto,
así que no hace falta tener `uv` en el PATH una vez creado el entorno con `uv sync`.

Otras opciones: `--date AAAA-MM-DD`, `--no-fetch` (no actualiza resultados), `--no-save` (no guarda las predicciones
del día; para pruebas), `--upcoming N` (días de calendario; por defecto 6), `--out carpeta`.

`build.py` hace lo mismo que `scripts/portal.py` (calcula la jornada, puntúa el historial y guarda las predicciones en
`data/predictions/`), así que basta con ejecutar uno de los dos cada día.

## Páginas

| Página | Qué enseña |
|---|---|
| **Partidos** | La jornada de hoy con la probabilidad del modelo y la lectura frente al mercado. Con las flechas: días anteriores (lo que se predijo y lo que pasó) y calendario de los siguientes. |
| **Ficha de partido** | Apuestas de jugador, apuestas de equipo, estadísticas de jugadores, cara a cara, quintetos probables y desglose del modelo. En días anteriores: resultado de cada línea. |
| **Liga** | Clasificación por conferencia con el nivel del modelo, calendario, líderes y tablas de la temporada. |
| **Buscador de props** | Jugadores que han llegado a una cifra en sus últimos partidos, con filtros sobre qué partidos cuentan. |
| **Apuestas de jugador** | Líneas con precio: cuota, probabilidad del modelo frente a la casa, acierto reciente, racha e historial. Tarjetas o vista compacta. |
| **Apuestas de equipo** | Ganador, hándicap y total con la probabilidad del modelo, la de la casa sin margen y la forma de los dos equipos. |
| **Proyecciones** | Tabla completa; se puede escribir la línea y las cuotas de otra casa. |
| **Favoritos** | Lo marcado con la estrella (se guarda en el navegador, por jornada). |
| **Historial** y **Metodología** | Acierto real acumulado y cómo se calcula todo, con sus límites. |

## Estructura

```
webapp/
  build.py                 comando de generación (envoltorio fino)
  src/index.html           esqueleto de la página
  src/assets/css/app.css   estilos (tema claro y oscuro según el sistema, móvil incluido)
  src/assets/js/core.js    utilidades, datos, estado de la interfaz y piezas compartidas
  src/assets/js/partidos.js, analisis.js, liga.js, seguimiento.js   una página (o grupo) por archivo
  src/assets/js/app.js     barra lateral, rutas (#/pagina) y eventos
  dist/                    generado, no se versiona
nba_model/site.py          prepara los datos: liga, forma, cara a cara, registros de jugador, días anteriores y calendario
tests/test_site.py         tests de todo lo anterior
```

`dist/data/` lleva un archivo por día (`day-AAAA-MM-DD.js`), el índice y la liga. Se cargan con etiquetas `<script>`
para que el sitio funcione también abierto desde el disco.

## Reglas (además de las de `AGENTS.md`)

- **Ninguna matemática del modelo en el JS del sitio.** `assets/js/calc.js` se extrae al generar del bloque
  `CALC-START/END` de `web/portal_template.html`, que ya tiene su test de paridad con Python. Todo lo demás llega
  calculado desde `nba_model/site.py`; el navegador solo cuenta aciertos y ordena. `tests/test_site.py` comprueba que
  no hay otra copia.
- **«Acierto», «racha» y «forma» son descriptivos.** La ventana de partidos es la misma para todos (5, 10, 15 o 20):
  no se añade una opción que busque la mejor ventana de cada jugador, porque eso es elegir el dato que mejor queda.
- **Nada de lo que enseña el sitio usa datos del día o posteriores** (los tests lo comprueban con las fechas).
- Los avisos de que no son recomendaciones se mantienen en las páginas de apuestas (`AGENTS.md`, regla 5).
- Sin recursos externos (fuentes, logos, analítica): la página no hace ninguna petición fuera de su carpeta.

## Qué no tiene (y por qué)

- Cuentas de usuario, suscripción o referidos: es un sitio estático; eso es la fase 9 del `ROADMAP.md` y antes va la
  consulta legal (8.1).
- Probabilidad en directo y combinadas: aparecen como «Pronto»; no hay modelo todavía (7.5 del roadmap).
- Alineaciones confirmadas y comparación entre varias casas: ESPN solo da el parte de lesiones y las cuotas de DraftKings.
- Predicciones de días futuros: se calculan el día del partido, con las bajas y las líneas de ese momento.
