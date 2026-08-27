# StreetJoin — Fase 2: Prototipo jugable ✅ (2026-08-14)

## Resultado

Prototipo completo y testeado en `web/streetjoin.html` (0.48 MB, 100% autocontenido: Leaflet + city.json embebidos, sin dependencias externas salvo las teselas del mapa base de CARTO). Entregado también como artifact persistente **streetjoin-santiago** en el escritorio de Juani.

## Cómo funciona

- **Puzzle**: elige dos intersecciones al azar (con al menos una calle no-residencial en cada punta, a ≥1.2 km) cuya cadena óptima esté entre 4 y 6 calles. Intentos = óptimo + 4. Generador con seed determinista (`game.start(seed)`).
- **Adivinanza**: input con autocompletar (≥3 letras, máx. 6 sugerencias), normalización idéntica al pipeline (tildes, ñ→n, prefijos av/calle/pasaje…). Nombre inexistente → no consume intento. Una clave que matchea varias calles ilumina todas y consume 1 intento.
- **Feedback**: verde = en una ruta óptima (dO+dD ≤ opt+1), amarillo = cerca (≤ opt+3), rojo = lejos. Precomputa distancias BFS desde origen y destino al iniciar cada puzzle.
- **Victoria**: BFS solo sobre calles nombradas, desde las calles del punto A hasta las del punto B. Al terminar (gane o pierda) revela una ruta óptima en azul.

## Arquitectura del código

- `web/template.html` — fuente única (HTML+CSS+JS del juego, con placeholders).
- `web/build_web.py` — inyecta Leaflet (de node_modules) y city.json → `streetjoin.html`.
- API expuesta para tests: `window.game.start(seed)`, `window.game.guess(txt)`, `window.game.state()`, `window.__lastResult`.

## Testing (Playwright headless, todo ✓)

Partida ganada completa (seed 42: 5/5 intentos óptimos), partida perdida por agotar intentos, nombre inexistente no consume intento, alias "alameda" → Av. Libertador Bernardo O'Higgins, rendering verificado por screenshots (marcadores como círculos dibujados — los íconos PNG de Leaflet no funcionan inline).

## Pendientes para Fase 3 (pulido)

- Jugar de verdad y calibrar dificultad (¿4–6 calles está bien? ¿margen +4?).
- Curar puzzles: evitar esquinas poco reconocibles; quizás lista curada de puntos emblemáticos (Plaza de Armas, Estación Central…).
- Compartir resultado (texto tipo Wordle), hints, modo sin autocompletar (difícil).
- Revisar rendimiento y usabilidad en móvil.

## Actualización RM (2026-08-14, misma sesión)

- Cobertura ampliada a Gran Santiago (41.876 calles, HTML 6.2 MB, carga ~4.7 s).
- Capa base del mapa dibuja solo clases ≤3 (las residenciales se crean lazy al adivinarlas).
- Sugerencias agrupan homónimas bajo un renglón con contador "×N"; elegirla juega todas.
- Guess con nombre completo exacto ("Avenida Balmaceda") juega solo esa calle; nombre a secas ("balmaceda") juega todas las variantes/homónimas.
- Generador de puzzles: 1 BFS desde A + scan de intersecciones candidatas (~116 ms); óptimo 4–6 calles, distancia mínima 1,5 km. Los puzzles pueden cruzar la ciudad entera (ej. Maipú → Peñalolén) — calibrar en Fase 3.

## Optimización de rendimiento (2026-08-14)

Medición previa: lo lento NO era el motor del juego (el generador de puzzles corre en ~20 ms). El costo estaba en el tamaño del payload y en trabajo de arranque innecesario.

| Cambio | Efecto |
|---|---|
| **Sacar pasajes del dataset** (living_street/pedestrian + nombres "Pasaje *") | 41.876 → 15.280 calles; city.json 5,2 → 2,1 MB. Grafo sigue 97,3% conexo y la dificultad no cambia. Además limpia las sugerencias. |
| **`JSON.parse("…")` en vez de objeto literal JS** | ~2x más rápido: el motor usa el parser de JSON, no el de JavaScript completo. |
| **No dibujar la red de base** | Antes se creaban ~8.000 polilíneas Leaflet al iniciar; el mapa base de CARTO ya muestra todas las calles. Ahora solo se crean las adivinadas (lazy). Fallback: si no cargan las teselas, dibuja las arterias como contexto. |
| **Podar claves derivables del JSON** | Las variantes normalizadas del nombre se regeneran en JS; solo viajan los alias reales de OSM. |

**Resultado: HTML 6,22 → 2,49 MB, tiempo hasta jugable ~780 → ~250 ms** (Chromium headless, teselas bloqueadas).

Fix relacionado: los tramos homónimos de una misma calle ahora comparten el color del mejor de ellos, para que el mapa concuerde con el chip (antes un tramo lejano de "Vicuña Mackenna" salía rojo mientras el chip decía verde).

### Optimizaciones aún disponibles (si hiciera falta)
- Teselas del mapa: es la carga de red restante; se puede usar un basemap más liviano o cachear.
- Formato binario (Float32Array + base64) en vez de JSON para las geometrías: ~30% menos, bastante más complejidad.
- Cargar geometrías por zona bajo demanda: solo tiene sentido si se agregan más ciudades.

## Fase 3 — primeros ajustes de jugabilidad (2026-08-15)

**Zoom fluido.** Leaflet por defecto salta de a niveles enteros. Ahora el mapa usa
`zoomSnap: 0` (niveles fraccionarios), `zoomDelta: 0.5` para los botones y el teclado, y
`wheelPxPerZoomLevel: 90` para que rueda y trackpad avancen de forma progresiva.

**Modo "elegir los dos puntos" (botón 📍).** Permite armar un puzzle propio: primer clic
fija el origen, segundo el destino; ambos se enganchan a la esquina real más cercana y se
muestran con el nombre de sus calles. Antes de empezar se valida con BFS que exista un
camino entre ambos (si no, avisa y pide otro destino) y los intentos se calculan igual que
en los puzzles al azar (óptimo + 4). `Esc` o el mismo botón cancelan y restauran la partida
que estaba en curso, sin perder los intentos ya hechos.

Para que el enganche a esquinas sea preciso, las intersecciones exportadas subieron de
6.000 a 14.000 (city.json 2,1 → 2,4 MB; el arranque sigue en ~300 ms).

Refactor asociado: `clearBoard()` / `drawBoard()` permiten limpiar el mapa al entrar al
modo elegir y reconstruir la partida anterior si se cancela; `startWith(puzzle)` separa el
armado del juego de la generación aleatoria, así el modo manual reutiliza toda la lógica.

## Autopistas y zoom sin parpadeo (2026-08-15)

**Autopistas incorporadas.** `motorway` y `trunk` estaban fuera de `KEEP`. Al agregarlas
aparecieron Costanera Norte, Vespucio Norte/Sur/Oriente, Nororiente, Acceso Sur y Los
Libertadores… pero **Autopista Central seguía sin aparecer**: las autopistas se conectan a
la superficie solo por rampas (`*_link`) que casi nunca tienen nombre, y el pipeline
descartaba todo lo sin nombre — así que quedaban como islas fuera de la componente conexa mayor.

Solución: las rampas ya no se descartan, se usan como **pegamento de conectividad**. Un
union-find une los extremos de cada rampa en un mismo nodo lógico, y la adyacencia entre
calles se calcula sobre esos nodos. Las rampas no son adivinables (no tienen nombre), solo
transmiten conexión. Resultado: componente mayor 97,3% → **98,7%** (15.517 calles) y las
autopistas quedan jugables y conectadas (Autopista Central ↔ Vespucio Norte: 1 salto).

**El mapa ya no desaparece al hacer zoom.** Cada zoom aplicado con `setView`/`setZoomAround`
dispara un `viewreset` de Leaflet, y `GridLayer` responde destruyendo todas las teselas —
por eso el mapa quedaba en blanco durante el gesto. Ahora el zoom de rueda usa el mismo
mecanismo interno que Leaflet aplica al pinch táctil: `map._move(center, z, {pinch: true,
round: false})`, que reescala lo que ya está dibujado sin descartarlo. Al terminar el gesto
(180 ms sin eventos) un `_moveEnd(true)` pide las teselas del nivel final, que reemplazan a
las anteriores recién cuando cargan. Complementos: `fadeAnimation: false`,
`updateWhenZooming: false`, `updateWhenIdle: true` y `keepBuffer: 4`.

Nota: se usan APIs privadas de Leaflet (`_move`, `_moveEnd`, `_stop`). Son estables en la
1.9.x fijada en `package.json`; si se sube de versión mayor, revisar esto.

Testing: como el sandbox no alcanza las teselas de CARTO, se levantó un servidor local de
teselas falsas para verificar que durante el gesto siguen visibles (18/18) y que al soltar
se refresca el nivel.

## Modo Lugares y accesibilidad de color (2026-08-18)

**Bug del modo Lugares: los lugares se enganchaban por su centroide.** Un lugar se
asociaba a las calles cercanas al centro de su geometría; en un parque o un estadio ese
punto está a cientos de metros de cualquier calle, así que el conjunto de calles del
extremo quedaba casi vacío o directamente equivocado (Parque O'Higgins colgaba de
"Santiaguillo", el Estadio Nacional de un pasaje interno). El jugador nombraba las calles
que de verdad bordean el lugar y la conexión no se cerraba.

Ahora el enganche usa el **polígono real** vía un `STRtree` de shapely sobre los 24.789
tramos de calle, con radio progresivo (60 → 120 → 250 → 450 m, parando al juntar 3 calles)
y sin tope artificial: antes se cortaba en 8 calles y 18 de los 84 lugares perdían
bordes válidos. Parque O'Higgins ahora cuelga de Tupper, Autopista Central, Matta y Viel.
Verificado con 60 partidas automáticas llegando por el extremo más lejano de cada lugar:
60/60 detectan la conexión.

**Distinción de estados sin depender del color.** Un jugador daltónico no podía separar
verde/amarillo/rojo. Ahora cada estado se marca con **tres señales simultáneas**:

| Estado | Color (Okabe-Ito) | Trazo | Símbolo |
|---|---|---|---|
| En la ruta óptima | azul `#0072B2` | línea llena | ✓ |
| Cerca de la ruta | naranja `#E69F00` | cortada | ≈ |
| Lejos de la ruta | rosa `#CC79A7` | punteada | ✕ |

La paleta Okabe-Ito está diseñada para ser distinguible con deuteranopía, protanopía y
tritanopía, y el trazo distinto hace que funcione incluso en escala de grises. Los símbolos
aparecen en los chips y en el mensaje de estado. El halo de la ruta óptima revelada pasó a
gris neutro para no competir con el azul, y el resaltado del cursor también.
El panel ⚙ incluye una leyenda con los tres estados.

## Corrección de lugares mal ubicados (2026-08-18)

El aeropuerto aparecía en el Parque Bicentenario de Cerrillos: el patrón
`"arturo merino benitez"` matcheaba **"Edificio Arturo Merino Benítez"** (un edificio en el
ex aeropuerto de Cerrillos) en vez de **"Aeropuerto Internacional Comodoro Arturo Merino
Benítez"**, porque el desempate elegía el nombre OSM más parecido en largo al patrón y el
del edificio es mucho más corto.

Auditando los 85 emparejamientos aparecieron cuatro más del mismo tipo:

| Lugar | Estaba en | Ahora |
|---|---|---|
| Aeropuerto | "Edificio Arturo Merino Benítez", Cerrillos | Pudahuel, Autopista Aeropuerto |
| Parque Padre Hurtado | "Cementerio Parque Padre Hurtado", comuna de Padre Hurtado | La Reina, Av. Francisco Bilbao |
| Campus Juan Gómez Millas | "Villa Juan Gómez Millas", Puente Alto | Ñuñoa, Av. Grecia |
| Campus San Joaquín UC | un jardín infantil del campus | el campus, Vicuña Mackenna |
| Clínica Alemana | sede La Reina | sede Vitacura |

Dos cambios en el pipeline para que esto no se repita:

1. **Campo opcional de referencia** en la lista curada: `(patrón, nombre, ícono, (lon, lat))`.
   Cuando varios POIs comparten exactamente el mismo nombre (sedes de una clínica, por
   ejemplo) se elige el más cercano a esa referencia. Solo se usa donde hace falta.
2. **Auditoría impresa en cada corrida**: el script lista `lugar -> POI de OSM elegido` con
   sus coordenadas, así un emparejamiento equivocado se ve al construir y no jugando.

`Estadio San Carlos de Apoquindo` se sacó de la lista: OSM no tiene el estadio como POI en
este extracto y el único candidato era un monolito a 3 km.

## Modo ciego (2026-08-18)

Un modificador ortogonal a Esquinas/Lugares, en el panel ⚙: se juega sobre un mapa **sin
ningún nombre** y contra el reloj. Cambia el objetivo del juego — ya no importa usar pocas
calles, importa cerrar el camino rápido.

**Qué cambia respecto del modo normal:**

| | Normal | Ciego |
|---|---|---|
| Mapa base | CARTO `light_all` (con etiquetas) | CARTO `light_nolabels` |
| Nombre al apuntar | opcional (checkbox) | forzado en off y bloqueado |
| Medida | intentos vs. óptimo | cronómetro + nº de calles |
| Feedback | ✓ óptima / ≈ cerca / ✕ lejos | ✓ conectada / ○ suelta |

Se mantienen el autocompletar (escribir sigue siendo el input) y los nombres de los
extremos A y B: son el enunciado del puzzle, no la respuesta.

**Feedback conecta/suelta.** Una calle nombrada está *conectada* si se encadena con otras
ya nombradas hasta alguna calle de A o de B; si no, queda *suelta*. Es un estado dinámico:
una calle suelta se vuelve azul sola cuando el camino la alcanza. Por eso el repintado dejó
de ser incremental — `refresh()` recalcula BFS sobre las nombradas y redibuja calles y
chips enteros en cada jugada (también arregla, de paso, que los chips viejos quedaran
congelados). Colores Okabe-Ito: azul sólido ✓ / gris punteado ○.

**Cronómetro.** Arranca con el primer intento (no al abrir el puzzle: mirar el mapa antes
de tirar la primera calle es parte del juego), se detiene al ganar. La mejor marca se
guarda en memoria por modo (`bestTime.corners` / `.places`) — no hay `localStorage` en los
artifacts. Se muestra la marca *previa* a la partida en curso (`game.prevBest`), si no la
primera victoria se anunciaba a sí misma como récord.

**Al ganar vuelven las etiquetas** al mapa base: terminar es justamente el momento de leer
por dónde pasaste. También se revela la ruta mínima, igual que en el modo normal.

**Anti-atajos.** Cambiar el modo reinicia el puzzle: si no, se podía destapar el mapa a
mitad de partida para leer los nombres y volver a taparlo. Y a ciegas `canPoint()` deja de
identificar calles gratis con el cursor — solo funciona el clic si está activado "jugar con
clics", y ahí el nombre recién aparece en el chip cuando la calle ya se jugó.

**Testing** (`web/test_blind.mjs`, 26 verificaciones, todas ✓): teselas sin etiquetas al
entrar y con etiquetas al ganar, leyenda y checkbox de nombres, cronómetro parado antes del
primer intento y detenido al ganar, calle del medio → ○ y calle de A → ✓, las sueltas pasan
a ✓ al cerrarse el camino, mejor marca, vuelta a modo normal y combinación con Lugares.

Nota para tests: `window.game` ahora expone también `setBlind`, `blind()`, `elapsed`,
`bestTime`, `optimalChain`, `streets` y `connectedNamed`.

## Calles con aspecto de ruta de navegador (2026-08-21)

Las calles adivinadas se dibujaban como una polilínea plana de 4–5 px: sobre el mapa
base parecían un rayón encima del mapa, no un camino trazado *sobre* él.

Ahora cada calle se dibuja como un **sándwich de tres trazos** apilados, que es lo que
usan Waze y Google Maps para que la ruta se despegue del fondo:

| Trazo | Qué hace |
|---|---|
| sombra (`#0f172a`, ancho +8, opacidad .07–.12) | despega la cinta del mapa |
| borde blanco / *casing* (ancho +4,5) | la separa de las calles del mapa base |
| núcleo del color del estado (ancho base) | el color/patrón que comunica el estado |

Detalles que hacen la diferencia:

- **Un pane por nivel** (`sj-shadow` 406, `sj-case` 408, `sj-core` 410, cada uno con su
  propio `L.canvas`). Si compartieran capa, dos calles que se cruzan se comerían el borde
  la una a la otra: el núcleo de una taparía el casing de la otra.
- **`lineCap`/`lineJoin: round` en todo**: las puntas y los quiebres dejan de ser esquinas.
- **Ancho según el zoom** (`baseWeight()`: de 3,5 px a z≤11,5 hasta 11 px a z≈18). Se
  repinta en `zoomend` — incluidos el hover y la ruta revelada.
- **Punteado proporcional al ancho**, no fijo: `dot` = `[1, w*2,1]` con cap redondo (puntos
  redondos parejos) y `dash` = `[w*2,1, w*1,5]`. Antes `"2 8"` y `"14 8"` se veían como
  guiones aplastados al acercarse y como línea llena al alejarse.
- **Jerarquía visual con `lift`**: cada estado declara +1 / 0 / −1. Lo que está en la ruta
  va más grueso y por encima; lo lejano, más fino, con casing más tenue y por debajo.
  `refresh()` pinta ordenando por `lift` para que el orden dentro de cada pane sea correcto
  sin importar en qué orden se nombraron las calles.
- La **ruta mínima revelada** pasó a ser una banda ancha y redondeada (`#475569`, ancho
  +11, opacidad .22) en su propio pane por debajo de todo, y el **resaltado del cursor**
  también es ahora una banda redondeada en vez de una línea dura.
- Los marcadores A/B se mudaron a un pane por encima de las calles (`sj-pts` 412): con las
  calles ahora más gruesas, quedaban tapados.

`styleFor()` desapareció; su lugar lo toman `strokeStyles(st)` (los tres estilos) y
`paintStreet(i, st)` (los aplica y ordena). `layerOf(i)` ya no devuelve una polilínea sino
`{shadow, case, core, st}`.

Testing: las 26 verificaciones de `web/test_blind.mjs` siguen pasando, sin errores de JS al
hacer zoom, y se revisaron capturas a z12 / z14 / z16 en modo normal y ciego.

## Degradado desde el lugar y color por extremo (2026-08-21)

En modo Lugares costaba saber si una calle había llegado al lugar: todas las calles útiles
salían del mismo azul, y las que bordean un parque o un estadio no se distinguían del resto
de la ruta.

Ahora **cada extremo tiene su color** y la calle que lo toca se enciende con ese color
justo donde está el lugar, apagándose hacia el resto de la calle:

| Extremo | Color |
|---|---|
| A | verde azulado `#009E73` |
| B | bermellón `#D55E00` |

Son los dos colores de Okabe-Ito que quedaban libres: se distinguen entre sí con cualquier
tipo de daltonismo y no se confunden con el azul/naranja/rosa de los estados.

El mismo color aparece en **cuatro lugares a la vez**, para que la asociación sea evidente:
el degradado en la calle, el aro del ícono (o el relleno del punto) del extremo, el fondo de
su etiqueta `A · …` / `B · …`, y una pastilla con la letra en el chip de la calle. En la
referencia del panel ⚙ se agregaron las dos entradas.

**Cómo se dibuja el degradado.** Leaflet pinta con `options.color`, que además de un string
acepta un `CanvasGradient`; alcanza con envolver `L.Canvas.prototype._fillStroke` y
reemplazar el color por un gradiente antes de delegar. Hay que rehacerlo en cada dibujo
porque sus coordenadas son píxeles de la capa y cambian al mover el mapa o hacer zoom.

Detalles que importan:

- Es un **gradiente radial centrado en el lugar**, no lineal a lo largo del trazo. Un lugar
  puede estar a cientos de metros de la calle (el centro de un parque) y las calles son
  curvas: lo que se quiere es "más encendido cuanto más cerca del lugar", que es exactamente
  lo que hace un radial.
- El radio interior es la **distancia del lugar al punto más cercano del trazo** (calculada
  sobre `layer._parts`, ya recortados al viewport) y el desvanecido dura `0,6 ×` el largo
  visible de la calle, acotado a 70–260 px. Así una calle corta se enciende entera y una
  avenida larga solo cerca del lugar.
- Si una calle toca **los dos extremos** el gradiente pasa a ser lineal de A a B: verde en
  una punta, bermellón en la otra y el color del estado en el medio. El chip muestra `AB`.

`game` guarda ahora `setA` / `setB` (las calles de cada extremo) y `endTouch(i)` devuelve
`"A"`, `"B"`, `"AB"` o `null`. `paintStreet()` le pasa el gradiente al núcleo de la calle;
la sombra y el borde blanco no cambian.

Caso límite conocido: una calle que toca B y además quedó *cerca de la ruta* (naranja) tiene
poco contraste entre el bermellón y el naranja. Pasa rara vez — una calle que toca un extremo
casi siempre queda en la ruta óptima — y la pastilla del chip lo desambigua igual.

Nota de testing: `web/test_blind.mjs` tiene un flake previo a estos cambios — cuando la calle
del medio de la cadena resulta tener alias (p. ej. "Ruta 78" / "Avenida Isabel Riquelme"),
un intento juega dos entidades y fallan tres asserts que asumen una sola. Se reproduce igual
en la versión anterior del juego.

## Halo continuo y cruces a distinto nivel (2026-08-21)

### El degradado ahora cruza de una calle a la siguiente

El degradado se calculaba **por calle**: cada una tomaba como radio interior su propia
distancia al lugar y como desvanecido una fracción de su propio largo. Resultado: una calle
corta que bordea el lugar se pintaba entera del color del extremo y la siguiente arrancaba
azul de golpe, con un escalón en la esquina.

Ahora es **un solo halo radial por extremo**, con los mismos parámetros para todas las
calles. Al ser puramente espacial, dos calles que se encuentran en una esquina llegan a ella
con exactamente el mismo color y el degradado pasa de una a la otra sin costura — no hace
falta propagar nada por el grafo.

- `r0` (radio donde el color está a full) = distancia del punto del extremo a la calle suya
  más cercana, en metros, calculada una vez por partida (`nearMeters`). En una esquina da
  ~0; en un parque, los cientos de metros que hay del centro a la vereda.
- `fade` = 650 m convertidos a píxeles al zoom actual, acotado a 60–320 px: alejado no
  desaparece, acercado no tiñe la pantalla entera.
- Una calle recibe el halo si *alguno* de sus puntos cae dentro de `r0 + fade`; ya no hace
  falta que toque el extremo. Si alcanza los dos, sigue siendo un degradado lineal A→B.
- Las paradas del degradado se concentran en el tramo central (`0–.38` color del extremo,
  `.82–1` color del estado). Entre dos colores casi opuestos —el bermellón de B y el azul
  de la ruta— un desvanecido largo pasa demasiado tiempo por el gris del medio; comprimirlo
  deja una transición corta y limpia en vez de una franja marrón.

### Cruces a distinto nivel

Dos calles dibujadas que se cruzan en el mapa pero **no comparten intersección en el grafo**
pasan una por encima de la otra. Dibujadas planas parecían conectar, que es exactamente lo
contrario de lo que el juego tiene que mostrar.

Ahora en cada cruce así se dibuja un **parche corto de la calle de arriba** —sombra, borde
blanco y núcleo— en tres panes por encima de todos los núcleos (`bshadow` 412, `bcase` 414,
`bcore` 416; los marcadores subieron a 420). El parche corta a la calle de abajo y le
proyecta sombra.

- `findCrossings()` corre en cada jugada: descarta los pares adyacentes en el grafo (ahí el
  cruce es real), rechaza por bounding box y recién entonces busca intersección
  segmento-segmento. Con 19 calles nombradas —varias avenidas enormes— un `refresh()`
  completo tarda ~11 ms. Se topa a 24 cruces y se dedupean los que caen a menos de ~15 m.
- **Quién pasa por arriba**: sin datos de puente/túnel en el pipeline, se usa la jerarquía
  de la vía (`c` más chico = más importante). Es un proxy: la autopista suele ser la
  elevada. Si algún día se quiere exacto, hay que exportar `bridge`/`layer` desde OSM.
- El largo del parche se mide en píxeles (tiene que tapar el ancho de la calle de abajo,
  extendido por `1/sin θ` en los cruces oblicuos) pero se dibuja en coordenadas del mapa, así
  que se reconstruye en cada `zoomend`.
- La sombra usa un degradado lineal que se desvanece hacia las puntas del trazo
  (`options.soft`, atendido en el mismo parche de `_fillStroke`): un stroke plano y corto
  deja dos bordes rectos que se leen como un rectángulo gris, no como una sombra.
- El núcleo del parche va **sin punteado**: el patrón reiniciado en un tramo tan corto se ve
  como un guión desparejo, y un puente sólido se lee mejor igual.

### El halo solo en las calles que llegan al lugar (2026-08-21)

El halo era puramente geométrico, así que también teñía calles que pasan cerca del lugar
sin tener nada que ver con él — la señal decía "conectaste" donde no había conexión.

Ahora el halo está **filtrado por conectividad real**: `reachFrom(extremo)` hace un BFS sobre
las calles ya nombradas desde las del extremo, y una calle responde al halo de A solo si está
en `reachA` (ídem B). La geometría sigue decidiendo *cuánto* color le toca; la conectividad
decide *si* le toca.

Como el filtro es por calle y los parámetros del degradado siguen siendo los mismos para
todas, la continuidad no se pierde: el subconjunto de calles encadenadas comparte el mismo
halo y el color cruza las esquinas igual que antes. Y el efecto ahora es dinámico —una calle
suelta cerca del lugar está sin teñir, y se enciende sola en cuanto nombrás la calle que la
une al lugar.

`connectedNamed()` (modo ciego) pasó a ser la unión de los dos `reachFrom`, que es lo mismo
que calculaba antes con un solo BFS.

Ojo con la distinción, que es intencional: la **pastilla A/B del chip** sigue marcando las
calles que *tocan* el lugar (adyacencia en el grafo), mientras que el **halo** marca las que
*llegan* a él encadenándose. Una calle a tres saltos del lugar puede tener halo y no pastilla.

### El parche del cruce, en proporción a la calle (2026-08-21)

El parche estaba dimensionado con constantes en píxeles (`+3` de margen al largo, `+15` al
ancho de la sombra) sobre una base que también traía constantes (la sombra de la calle de
abajo, `w + 8`). Al alejarse, las calles adelgazan hasta 3,5 px pero esas constantes no se
mueven: el parche pasaba a ser un rectángulo varias veces más grande que las dos calles.

Dos cambios:

1. **Todo se mide en proporción al ancho del trazo.** El largo se calcula sobre el *casing*
   de la calle de abajo (`w + 4,5`) en vez de sobre su sombra, con margen `0,25 × w`; el
   ancho de la sombra pasó de `w + 15` a `w × 2,4`. Así la proporción parche/calle es la
   misma a cualquier zoom. El tope del factor oblicuo subió de `1/0,35` a `1/0,45` (2,2×),
   que sigue alcanzando para tapar la calle de abajo en un cruce de 27°.
2. **Alejado no se dibujan** (`baseWeight() < 5,5`, es decir por debajo de z≈13,4). Con la
   calle en 4 px, cualquier parche legible es más grande que las dos calles juntas, y a esa
   escala el cruce a distinto nivel no es información que se esté mirando.

### Del parche al hueco: el cruce sin costuras (2026-08-21)

El parche sobre la calle de arriba nunca iba a quedar liso. Era un segmento recto apoyado
sobre una calle curva, con puntas al ras y el núcleo sólido contra una calle punteada: tres
motivos para que se viera dónde empieza y dónde termina. Achicarlo o difuminarlo tapaba el
síntoma, no la causa — cualquier trazo apoyado encima deja costura.

Se dio vuelta el enfoque: **no se toca la calle de arriba, se le abre un hueco a la de
abajo**. Es lo que hacen los mapas de verdad con los pasos bajo nivel, y como no hay nada
apoyado, no hay costura posible. La calle de arriba pasa entera, con su punteado y su curva
intactos.

- `cutLines()` recorta la geometría de la calle de abajo contra un disco por cada cruce. El
  corte es **por segmento, con interpolación exacta** (intersección recta-círculo): cortar
  por vértices dejaría bordes dentados, porque la geometría simplificada tiene vértices a
  decenas de metros.
- El radio sale del ancho del *casing* de la calle de arriba, corregido por `1/sin θ` para
  los cruces oblicuos y con `0,4 × ancho` de aire. Las tres capas de la calle de abajo
  (sombra, borde, núcleo) se recortan igual, y las puntas redondeadas del trazo cierran el
  hueco de forma limpia.
- La geometría completa se cachea decodificada (`geoOf`) y se guarda una clave por calle
  recortada (`cutNow`) para no reproyectar miles de puntos si el zoom no cambió el hueco.
  Si el recorte se comiera la calle entera —una calle corta cruzada por una autopista— se
  deja sin cortar antes que hacerla desaparecer.
- En el hueco queda una **sombra difusa a lo largo de la calle de arriba**, en un pane por
  debajo de todas las calles (`bshadow` 405): eso es lo que se lee como "pasa por encima".
  Los panes `bcase` y `bcore` desaparecieron.

Costo: un `refresh()` con 19 calles nombradas y varias avenidas enormes tarda ~7,5 ms
(antes ~11 con el parche).

## Abreviaturas en el buscador (2026-08-21)

`keysOf()` deriva claves sacando prefijos ("Avenida Balmaceda" → `avenida balmaceda`,
`balmaceda`) pero nunca genera `av balmaceda`. Escribir "av balmaceda" no sugería nada, y
`guess()` caía al plan B —claves sin prefijo— y jugaba de una las cuatro Balmacedas.

Ahora la consulta se busca en **tres formas** a la vez:

1. **Lo escrito**, tal cual.
2. **Con las abreviaturas expandidas**, token por token y no solo el primero, porque también
   caen en el medio: `av pdte kennedy` → `avenida presidente kennedy`. La tabla `ABBR` tiene
   solo abreviaturas no ambiguas — av/avda/avd, gral/grl, pje/psje, cno, dr/dra, pdte,
   sta/sto, prof, cnel, tte, ing. **"pte" quedó afuera a propósito**: tanto puede ser
   presidente como puente (y Puente Alto existe).
3. **Sin el prefijo**, derivada de las dos anteriores (`pje los aromos` → `los aromos`, que
   es como se llama la calle de verdad). Esta va con **penalización de +3 al score**, así
   "av balmaceda" muestra primero la avenida y recién después el pasaje y la calle.

Cada sugerencia recuerda con qué variante matcheó, que es la que `highlight()` resalta en
negrita y la que decide si hay que mostrar el alias entre paréntesis.

`guess()` además prueba la forma expandida como **nombre completo exacto**, antes de abrirse
a las variantes sin prefijo: "av balmaceda" ahora juega solo Avenida Balmaceda, igual que
escribir el nombre entero.

Costo: la búsqueda recorre el índice una vez por variante. Por tecla pasó de ~1–4 ms a
~3–9 ms, holgado dentro del frame.

## El camino final, dibujado (2026-08-21)

Al ganar se dibuja el **recorrido real de punta a punta**: no las calles enteras, solo el
tramo de cada una que hizo falta. Mientras se dibuja, el resto del tablero se atenúa al 50 %;
ese contraste ES el mensaje ("de todo lo que nombraste, esto fue lo que sirvió").

### Cómo se arma el recorrido

El grafo del juego es a nivel de CALLES, no de nodos: sabe que dos calles se tocan, no dónde.
Hubo que reconstruir la geometría:

1. **`namedChain()`** — BFS sobre las calles *nombradas* para sacar la cadena más corta de A
   a B. Es la que el jugador realmente usó, no la óptima teórica.
2. **`streetGraph(i)`** — grafo caminable de una calle. La geometría no viene como una
   polilínea de punta a punta sino como decenas de tramos sueltos; los nodos son los vértices
   compartidos entre tramos. Son pocos (la simplificación deja ~50 vértices por avenida), así
   que todo es barato. Las componentes que el pipeline fusionó por cercanía se unen por su
   par de nodos más cercano.
3. **`crossPoints(a,b)`** — todos los cruces geométricos entre dos calles vecinas; si la
   simplificación las dejó sin tocarse, el punto más cercano entre ambas.
4. **Un solo grafo combinado** con las calles de la cadena pegadas por sus cruces, y un
   Dijkstra de A a B.

Los puntos 4 y 2 fueron los dos bugs que costaron:

- **Elegir el cruce calle por calle (greedy) no sirve.** Cuando dos calles se cruzan en más
  de un lugar, el camino se iba y volvía. Con un único grafo y un solo Dijkstra el problema
  desaparece: minimizar el largo total elige los cruces correctos solo.
- **Las avenidas con bandejón vienen como dos calzadas paralelas** que solo se tocan en las
  puntas. Si el cruce de entrada engancha en una calzada y el de salida en la otra, el camino
  más corto entre ambas se va hasta la punta y vuelve — 1,4 km de más en Manuel Rodríguez
  Norte. Por eso `attach()` engancha un punto a **todos** los tramos que pasan cerca
  (hasta 70 m más que el más cercano, tope 130 m) y no solo al más cercano: una esquina cruza
  la avenida entera, así que además es lo correcto.

Un `winRoute()` completo tarda entre 0,3 y 3,3 ms.

### La animación

Tres trazos apilados en sus propios panes por encima de todo (`winGlow` 413, `winCase` 414,
`winCore` 415; los marcadores subieron a 418) más un punto blanco en la cabeza. Cada frame
recalcula la sub-polilínea hasta la distancia recorrida, con `ease-out` cúbico. Dura entre
0,9 y 2,2 s según el largo del camino.

- El cartel de resultado **taparía la animación**, así que aparece recién cuando termina.
  El contenido se llena igual de entrada; solo se demora el `showOverlay(true)`.
- Cualquier click o tecla completa el dibujo de una vez.
- El atenuado se queda después de la animación: las calles que nombraste de más siguen
  visibles pero apagadas, y el recorrido es el que manda.
- `test_blind.mjs` ahora espera a que aparezca el cartel y verifica que el camino se armó
  (`__lastResult.routePts`).

## Reestructuración en modos, con menú principal (2026-08-21)

Cambio de concepto: **el modo principal pasa a ser ciego + lugares**. El juego ya no arranca
tirando un puzzle: arranca en un **menú principal** con cuatro entradas —Lugares a ciegas
(destacado), Desafío diario (deshabilitado, "pronto"), Esquinas a ciegas y Práctica—. Cada
tarjeta de modo a ciegas muestra tu mejor marca si tenés.

Por debajo siguen siendo las dos variables de siempre (`mode` ∈ corners|places y `blind`);
lo nuevo es `gameMode` ∈ `lugares|esquinas|practica`, que es lo que decide **qué se le
ofrece al jugador**:

| | lugares | esquinas | practica |
|---|---|---|---|
| `blind` | sí | sí | no |
| `mode` | places | corners | el que elijas |
| Selector "qué conectar" | — | — | ✅ |
| Jugar con clics / ver nombre al apuntar | — | — | ✅ |
| Elegir los dos puntos (📍) | ✅ | — | solo en lugares |

Decisión: fuera de práctica las ayudas **no aparecen apagadas, no aparecen**. Mostrarlas
deshabilitadas invitaba a buscarlas; el panel de opciones queda con una nota corta que
explica que a ciegas no hay ayudas y la referencia de colores. Al entrar a un modo a ciegas
se fuerzan `opts.clickPlay` y `opts.hoverName` a false, por si venías de práctica.

Lo que **no** cambió: al terminar una partida el mapa siempre pasa a modo exploración —
vuelven los nombres y se puede apuntar—, porque ese es el momento de aprendizaje.

Detalles de implementación:

- `setGameMode(kind, restart)` es el único punto de entrada; `setMode()` quedó para el
  submodo dentro de práctica y `setBlind()` se mantiene como envoltorio por compatibilidad.
- `applyModeUI()` concentra todo lo que depende del modo (visibilidad del selector, de las
  ayudas, de la nota, de 📍 y qué leyenda se muestra).
- Al cargar se arranca una partida **detrás** del menú (`setGameMode(..., false)` + `start()`
  + `showMenu(true)`): así el mapa tiene estado y ningún handler se encuentra con `game`
  nulo, y de fondo se ve el mapa desenfocado.
- Botón 🏠 en la barra de entrada y "Menú" en el cartel de resultado. Escape y clic en el
  fondo cierran el menú.
- `test_blind.mjs` se actualizó: ahora verifica que el juego arranca en el menú con lugares
  a ciegas, que las ayudas existen solo en práctica y que salir de práctica las saca.

### Lo que viene: el desafío diario

Decidido con Juani: **sin backend por ahora**. Se arma toda la UI del daily y los dos
leaderboards contra datos locales, con la capa de red aislada detrás de una interfaz chica
(`submitResult` / `fetchDistribution`) para enchufarle Supabase o similar después.

- Puzzle del día por semilla derivada de la fecha (UTC−4), en el modo principal, una sola
  vez por día.
- Dos leaderboards **sin nombres**: son distribuciones de frecuencia para ubicarte en la
  población. El de calles va por valor discreto; el de tiempo, por **bins autocalculados a
  partir de los resultados del día**, no fijos.
- Compartir estilo Wordle.

### Bug: el camino final casi nunca se dibujaba (2026-08-21)

Reportado como "aparece a veces nada más, y muchas veces no te muestra ni la animación". No
era la animación: era que `winRoute()` devolvía `null` y `end()` caía al camino corto de
mostrar el cartel directo.

**Diagnóstico.** Un script que juega 14 partidas midiendo la distancia de cada extremo a su
calle dejó el patrón a la vista:

```
seed 1000  ruta=NO   A→calle 144 m   B→calle 136 m
seed 1004  ruta=sí   A→calle  66 m   B→calle  56 m
seed 1010  ruta=NO   A→calle 944 m   B→calle 137 m
seed 1013  ruta=sí   A→calle   8 m   B→calle   1 m
```

La ruta se armaba **solo cuando los dos extremos caían a menos de ~130 m de su calle**:
12 de 14 partidas fallaban.

**Causa.** Una regresión de la sesión anterior. Al enganchar los extremos y los cruces al
grafo, el umbral quedó así:

```js
const lim = Math.min(edges[0][0] + 70, 130);   // ← el 130 es el problema
for (const [d, a, m] of edges) { if (d > lim) break; ... }
```

Cuando el tramo más cercano está a más de 130 m, `lim` queda **por debajo** de la distancia
del primer tramo, el `break` salta en la primera vuelta y el nodo queda **suelto**: el grafo
no tiene camino de A a B, Dijkstra devuelve `null` y no se dibuja nada. El tope absoluto se
había puesto para no enganchar calzadas lejanas, pero el punto de un lugar es el **centro de
un parque o de un estadio** y está a cientos de metros del asfalto por definición — es el
caso normal en el modo principal, no un caso raro.

**Arreglo.** El umbral tiene que ser **relativo** al tramo más cercano, nunca absoluto:
`lim = edges[0][0] + 70`, con un tope de 8 tramos enganchados para que no se desmadre.

Después del cambio: 14/14 en el repro y 40 semillas × 3 modos sin un solo fallo.

**Test de regresión** en `test_blind.mjs`: 40 partidas (lugares y esquinas) verificando que
`__lastResult.routePts > 1` en todas.

### Bug: la ruta final se salía de las calles usadas (2026-08-21)

**Medición primero.** Un script que juega 60 partidas y mide, para cada tramo del camino
dibujado, la distancia al conjunto de calles de la cadena (salteando la recta de acceso al
lugar, que es legítima):

```
partidas: 60 · con desvío >40 m: 16   máximo 297 m
```

**Descarte.** El primer sospechoso eran los huecos entre calles vecinas, pero la
distribución los absolvió: de 204 pares consecutivos, 157 se cruzan de verdad, 36 quedan a
menos de 20 m y solo 4 superan los 80 m (máximo 149 m). Ningún hueco explicaba 297 m.

**Causa.** Exponiendo las internas, el par culpable quedó claro:

```
Avenida México → Avenida Diego Portales
   punto de enganche a 606 m de la primera, 0 m de la segunda
```

El fallback de `crossPoints` —el que se usa cuando la simplificación dejó a dos calles sin
tocarse— miraba en **un solo sentido**: vértices de B contra los tramos de A. Si el
acercamiento real pasa por un vértice de **A** cerca de un tramo de B, ese punto no se
evaluaba nunca y se elegía uno cientos de metros más lejos. Como ese punto es el que engancha
las dos calles en el grafo, el camino más corto lo atravesaba en línea recta.

**Arreglo.** El fallback ahora prueba **los dos sentidos** y devuelve el **punto medio** del
acercamiento más cercano (con `pointAt()`, que da el pie exacto sobre el tramo, no el vértice
más próximo). El par de arriba pasó de 606 m a 1 m.

| | antes | después |
|---|---|---|
| partidas con desvío >40 m (de 60) | 16 | 5 |
| desvío máximo | 297 m | 74 m |
| mediana del desvío | — | 18 m |

Lo que queda son los cuatro pares con hueco real de 80–149 m: calles que el grafo declara
vecinas pero cuyas geometrías no llegan a tocarse. Ahí el camino cruza el hueco derecho, que
a esa escala se lee como una esquina redondeada.

**Test de regresión** en `test_blind.mjs`: 60 partidas verificando que el desvío máximo se
mantenga por debajo de 120 m, e informando la mediana.

### De paso: el flake de los alias

`test_blind.mjs` venía fallando de a ratos desde hacía varias sesiones. Era un bug del test,
no del juego: asumía que un nombre juega una sola calle, pero "Ruta 78" es alias de "Avenida
Isabel Riquelme" y un intento juega las dos. Las tres verificaciones afectadas ahora aceptan
que una homónima arrastrada por un alias quede suelta, que es el comportamiento correcto.
Cinco corridas seguidas en verde.

### Internas expuestas

`window.game.__dbg` ahora expone `crossPoints`, `streetGraph`, `segDist`, `geoOf` e `INT`.
Sin eso, diagnosticar esto habría sido adivinar: la medición es la que descartó los huecos
entre calles y señaló el par exacto.

## Lugares por comuna: de 84 a 216 (2026-08-27)

**El problema, medido.** Cruzando los 84 lugares con los límites comunales de la RM:
35 estaban en la comuna de Santiago, 10 en Providencia, y **16 comunas del Gran
Santiago no tenían ninguno** (Conchalí, Quilicura, Renca, Cerro Navia, Quinta Normal,
Cerrillos, Lo Espejo, Pedro Aguirre Cerda, El Bosque, La Granja, San Ramón, La Pintana,
San Bernardo, Colina, Padre Hurtado, Calera de Tango). Otras nueve tenían exactamente
uno. El modo principal es *lugares a ciegas*, así que eso no era un detalle del dataset:
era la mitad de la ciudad que nunca aparecía en un puzzle.

**Criterio.** La periferia no tiene hitos turísticos, y esperar a que los tenga es
quedarse con el mapa de siempre. Lo que sí tiene toda comuna es **referencias de barrio**:
la municipalidad, el mall, el parque grande, el estadio municipal, el cementerio, el
hospital. Ese es el filtro que se usó — reconocible para quien vive ahí, no
necesariamente para un turista. Resultado: **216 lugares en 35 comunas, ninguna con
menos de 3.**

Los candidatos no se escribieron a mano: se **minaron del propio extracto OSM**,
puntuando cada POI con nombre por tipo y por superficie, y listándolos por comuna para
elegir. De ahí salieron cosas que no estaban en la lista original y son buenas piezas de
juego: el MIM en La Granja, Lo Valledor en PAC, el Cementerio Metropolitano en Lo Espejo,
el Parque Bicentenario de Cerrillos, Cerro Chena en San Bernardo, el Parque La Bandera en
San Ramón.

### Cambios en el pipeline

1. **El filtro de POIs se quedaba corto.** `amenity=townhall` y `college` no estaban, y
   son justamente la municipalidad y las escuelas matrices (Aviación, Carabineros,
   Militar); `leisure=nature_reserve` tampoco, y ahí viven el Bosque Panul y el humedal de
   Quilicura. Se agregaron esos, más `landuse=recreation_ground`, `place=square`,
   `cinema` y `courthouse`. Sin esto, 11 de las entradas nuevas quedaban sin match.
2. **Dedup por (nombre, comuna), no por nombre.** Con 84 lugares céntricos los nombres
   eran únicos; con 216 no: hay un *Parque Juan Pablo II* en Las Condes y otro en Puente
   Alto. La clave del diccionario `found` pasó a ser el par.
3. **Referencia (lon, lat) en todas las entradas nuevas.** El desempate por "el nombre
   OSM más parecido en largo al patrón" alcanzaba para una lista corta; con nombres
   genéricos repartidos por la ciudad (*Estadio Municipal…*, *Plaza de…*) no. La
   referencia sale del propio POI elegido al minar, así que no hay coordenadas escritas a
   mano.
4. **Un radio de enganche más (700 m).** `Parque Metropolitano Cerros de Renca` tiene su
   borde a más de 450 m de la calle más cercana y se descartaba por "sin calles cerca".
   De paso se sacó de la lista el POI `natural=peak` "Cerro Renca", que es la cumbre y no
   tiene calle alguna alrededor; la entrada nueva apunta al polígono del parque.
5. **`comuna_de(lon, lat)`** con `comunas-rm.geojson` (los límites de las 52 comunas de la
   RM, simplificados a ~40 m: 304 KB, 99,7 % de coincidencia con el original sobre 4.000
   puntos de prueba). La comuna se calcula al construir y viaja en el JSON.

El registro de un lugar pasó a ser `[lon, lat, nombre, ícono, [calles], comuna]`, y el
script imprime al final el conteo por comuna: el objetivo del dataset es que ninguna
quede vacía, no maximizar el total.

### La comuna, en el juego

Un lugar céntrico se explica solo; *Parque Las Palmeras* no. A ciegas, sin saber que está
en Renca, el puzzle no es difícil: es imposible. Así que la comuna se muestra **debajo del
nombre** en los tres lugares donde aparece un lugar — el globo del extremo A/B, el
enunciado ("Conecta …") y los íconos del modo elegir-puntos— en una segunda línea más
chica y tenue (`.com`). `endpoint()` recibe un sexto argumento `sub` y `lmkEnd(l)`
centraliza la conversión lugar → extremo.

### `MAX_KM_PLACES = 13`

Efecto secundario que no era obvio: con lugares en las 35 comunas, dos puntos al azar
pueden quedar a 35 km, y el grafo **los une igual** en 3 o 4 calles (Vespucio + una
autopista + una avenida). El puzzle no se vuelve más difícil, se vuelve otro juego: deja
de ser "qué calles conectan estos dos barrios" y pasa a ser "qué autopista tomo".

Medición sobre 400 semillas (`web/measure_places.mjs`, nuevo):

| | antes (84 lugares) | sin tope (216) | con tope de 13 km |
|---|---|---|---|
| mediana | 6,4 km | 10,6 km | 8,4 km |
| p90 | 14,3 km | 20,3 km | 11,7 km |
| máximo | 28,8 km | 37,2 km | 13,0 km |
| óptimo = 3 calles | 43 % | 29 % | 43 % |
| comunas que aparecen | 21 | 35 | **35** |

El tope devuelve la escala y la dificultad de antes sin perder cobertura: los pares
periféricos que ahora existen (Colina con Quilicura, Maipú con Cerrillos, La Pintana con
El Bosque) están todos por debajo de 13 km. Es un puzzle *dentro* de la ciudad, no un
cruce de la ciudad entera.

### Verificación

- `web/test_blind.mjs` completo en verde, incluidas las 40 partidas del camino final y
  las 60 del desvío de ruta (máximo 60 m, mediana 20 m).
- Auditoría impresa del pipeline: los 216 emparejamientos lugar → POI de OSM revisados
  uno por uno, más las calles asociadas a cada lugar nuevo (que son las que de verdad lo
  bordean: el MIM cuelga de Punta Arenas y Estadio, Lo Valledor de General Velásquez y
  Avenida Maipú).
- Capturas en escritorio y en viewport de celular con la comuna en el enunciado y en los
  globos, y del modo elegir-puntos con los 216 íconos (se dibujan en ~420 ms).
