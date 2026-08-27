# StreetJoin — Plan del proyecto

*Un juego para aprenderse las calles de una ciudad, conectando dos puntos nombrando las calles que los unen (inspirado en Travle). Primera ciudad: Santiago de Chile.*

**▶ Jugable en https://juanisenin.github.io/streetjoin/**

---

## 1. Concepto del juego

Cada partida presenta un mapa con dos puntos marcados: un **origen** y un **destino**. El jugador escribe nombres de calles, una por turno. Cada calle que existe en la zona se ilumina en el mapa. Gana cuando el conjunto de calles nombradas forma un camino continuo entre los dos puntos, y ahí se dibuja el recorrido real de punta a punta.

### Los modos (reestructurado 2026-08-21)

Se entra a todos desde el **menú principal**:

| Modo | Qué es |
|---|---|
| **🕶️ Lugares a ciegas** | **El modo principal.** Dos lugares icónicos (216, al menos 3 en cada una de las 35 comunas del Gran Santiago), el mapa sin ningún nombre y un cronómetro desde el primer intento. No importa usar pocas calles: importa cerrar el camino rápido. Sin ayudas de ningún tipo. |
| **📅 Desafío diario** | El mismo puzzle para todos, una sola vez por día, con ranking del día (top 20 por tiempo) y las distribuciones de tiempos y de calles usadas. |
| **🚦 Esquinas a ciegas** | Lo mismo, pero entre dos esquinas cualquiera de la ciudad. |
| **🎓 Práctica** | El juego con los nombres a la vista, sin reloj, con intentos ilimitados, ayudas de accesibilidad (jugar con clics, ver el nombre al apuntar) y la opción de elegir vos los dos puntos. Para aprenderse la ciudad sin apuro. Acá sí se muestra el feedback de cercanía a la ruta óptima (verde/amarillo/rosa). |

**Decisión de diseño:** las ayudas (identificar calles apuntándolas, jugar con clics, el selector de qué conectar) **existen solo en Práctica**. En los modos a ciegas ni siquiera aparecen en el panel de opciones: mostrarlas apagadas invitaba a buscarlas. Al terminar una partida el mapa siempre pasa a modo exploración —vuelven los nombres y se puede apuntar— porque ese es el momento de aprendizaje.

**Reglas clave:**

- La validación de nombres es tolerante: ignora tildes, mayúsculas, prefijos ("Av.", "Avenida", "Calle", "Pasaje") y abreviaturas ("av", "gral", "pje", "dr", "cno"…). "bernardo ohiggins" matchea "Avenida Libertador Bernardo O'Higgins".
- Una calle nombrada se considera conectada si comparte intersección con el origen, el destino, o con otra calle ya nombrada.
- Al ganar se dibuja el **recorrido real** de punta a punta, usando solo el tramo de cada calle que hizo falta, y el resto del tablero se atenúa.
- El halo de color de cada extremo (verde para A, bermellón para B) marca las calles que **llegan** a ese lugar encadenándose con las ya nombradas.

**Fuera del alcance por ahora**: cuentas de usuario, rachas, más ciudades. El
diario identifica al jugador con un uuid del navegador y un apodo, sin cuenta.

## 2. Modelo de datos

La ciudad se modela como un **grafo de calles**: los nodos son intersecciones y las aristas son segmentos de calle con nombre. Vista "dual": cada **calle completa** es una unidad, y dos calles son "vecinas" si comparten al menos una intersección. Conectar A con B = encontrar una cadena de calles vecinas.

- **Fuente**: OpenStreetMap. **Zona**: todo el Gran Santiago (ver `fase1-datos.md`).
- **Formato**: un `city.json` estático precomputado. El navegador no necesita OSM ni servidor: todo el juego corre client-side sobre ese JSON.

## 3. Stack

| Capa | Herramienta |
|---|---|
| Pipeline de datos | Python + `pyrosm` + `networkx` (corre una sola vez por ciudad) |
| Frontend | HTML + JS puro + **Leaflet**, un solo archivo autocontenido |
| Mapa base | Teselas gratuitas de CARTO |
| Hosting | **GitHub Pages** — `index.html` en la raíz de `main` |
| Backend del daily | **Supabase** (PostgREST por `fetch`, sin SDK). Funciona sin credenciales contra una población simulada — ver `fase3-daily.md` |

## 4. Fases

### Fase 0 — Ideación ✅
### Fase 1 — Datos ✅
Pipeline OSM → `city.json` con todo el Gran Santiago. Ver `fase1-datos.md`.

### Fase 2 — Prototipo jugable ✅ (varias sesiones)
Motor del juego, mapa, autocompletado, modo ciego, lugares icónicos, dibujo estilo navegador, cruces a distinto nivel, camino final animado, la reestructuración en modos con menú principal y la cobertura de lugares por comuna (84 → 216). Todo el detalle en `fase2-prototipo.md`.

### Fase 4 — Deploy ✅ (2026-08-25)
Publicado en **https://juanisenin.github.io/streetjoin/** desde el repo
[juanisenin/streetjoin](https://github.com/juanisenin/streetjoin): `index.html` en la raíz
de `main`, y cada push republica solo. Incluye el arreglo del layout en celular (la barra
de entrada forzaba un zoom-out de toda la página). Detalle en `fase4-deploy.md`.

### Fase 3 — Desafío diario ✅ (2026-08-27)
Puzzle del día por semilla derivada de la fecha (UTC−4), una sola vez por día, en
el modo principal. **Ranking del día por tiempo** (top 20, con apodo) más las dos
distribuciones sin nombres — tiempos con bins autocalculados, calles por valor
discreto—, el percentil, y compartir estilo Wordle. Toda la red detrás de
`net.submitResult` / `net.fetchBoard`, con Supabase de un lado y una población
simulada del otro para que el juego funcione sin credenciales. Detalle en
`fase3-daily.md`; el esquema, en `daily-supabase.sql`.

**Falta para que sea real:** crear el proyecto de Supabase, correr el SQL y pegar
URL + anon key en `BACKEND` (`web/template.html`).

### Fase 5 — Futuro
Rachas y estadísticas locales del diario, más comunas o ciudades, dificultades.

## 5. Riesgos

- **Integridad del leaderboard**: cualquiera puede mandar un resultado falso desde la consola. Para un juego chico es aceptable; si molesta, lo mínimo razonable es validar server-side que el camino declarado realmente conecte.
- **Nombres de calles ambiguos o repetidos**: resuelto en el pipeline tratando cada componente conexa con el mismo nombre como una entidad separada.
- **Puzzles imposibles o triviales**: se filtran por rango de dificultad (óptimo entre 4 y 6 calles) y distancia mínima.
- **Datos OSM incompletos**: la zona está muy bien mapeada; los errores puntuales se corrigen con overrides en el pipeline.
