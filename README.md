# StreetJoin

Juego para aprenderse las calles de una ciudad: se dan dos puntos del mapa y hay que
conectarlos nombrando las calles que los unen, con intentos limitados (inspirado en Travle).

Ciudad actual: **Gran Santiago**, con datos de OpenStreetMap.

![estado](https://img.shields.io/badge/estado-jugable-brightgreen)

## Jugar

**👉 __PAGES_URL__**

Anda en celular y en compu, sin instalar nada. También podés abrir `index.html`
directamente: es un archivo autocontenido (Leaflet y los datos van embebidos); lo único
que pide red son las teselas del mapa base.

Se entra por el menú principal:

- **🕶️ Lugares a ciegas** — el modo principal: dos lugares icónicos, el mapa sin ningún
  nombre y un cronómetro. Importa cerrar el camino rápido, no usar pocas calles.
- **🚦 Esquinas a ciegas** — lo mismo entre dos esquinas cualquiera.
- **🎓 Práctica** — con los nombres a la vista, sin reloj y con ayudas, para aprenderse la
  ciudad sin apuro.

Escribís nombres de calles y las sugerencias aparecen desde la 2ª letra. Es tolerante con
tildes, prefijos y abreviaturas: "alameda" → Avenida Libertador Bernardo O'Higgins,
"av pdte kennedy" → Avenida Presidente Kennedy. Un nombre que no existe no gasta intento.

## Estructura

```
data-pipeline/
  build_city.py     OSM (.osm.pbf) -> city.json (grafo de calles)
  city.json         15.280 calles del Gran Santiago (2,1 MB)
index.html          build autocontenido: lo que publica GitHub Pages
web/
  template.html     fuente del juego (HTML + CSS + JS)
  build_web.py      template + Leaflet + city.json -> index.html
  test_blind.mjs    tests end-to-end con Playwright
docs/
  fase1-datos.md    decisiones y formato de los datos
  fase2-prototipo.md  diseño del prototipo, testing y optimizaciones
  plan.md           plan general del proyecto por fases
```

## Regenerar

```bash
# 1. datos (requiere el extracto .osm.pbf; ver docs/fase1-datos.md)
pip install pyrosm networkx shapely numpy
cd data-pipeline && python3 build_city.py Santiago.osm.pbf city.json

# 2. build web (requiere leaflet en node_modules)
npm install leaflet@1.9.4
cd web && python3 build_web.py
```

El extracto `Santiago.osm.pbf` (40 MB) no va al repo: se descarga de
[BBBike](https://download.bbbike.org/osm/bbbike/Santiago/) o
[Geofabrik](https://download.geofabrik.de/south-america/chile.html).

## Cómo funciona

La ciudad se modela como un grafo donde cada **calle** es un nodo y dos calles son
adyacentes si comparten una intersección. Conectar A con B es encontrar una cadena de
calles adyacentes; la dificultad de un puzzle es el largo de la cadena mínima (BFS).

Detalle importante: una "calle" no es todo lo que comparte nombre, sino cada componente
conexa de segmentos con ese nombre — hay decenas de "Los Aromos" en distintas comunas y
fusionarlas crearía saltos imposibles en el grafo.

## Estado

- ✅ Fase 1 — datos
- ✅ Fase 2 — prototipo jugable (+ optimización: 2,5 MB, arranca en ~250 ms)
- ✅ Fase 4 — deploy en GitHub Pages
- ⏳ Fase 3 — desafío diario: puzzle del día, distribuciones de resultados, compartir
