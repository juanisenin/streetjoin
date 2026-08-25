#!/usr/bin/env python3
"""StreetJoin — lugares icónicos del Gran Santiago.

Lee los POIs del extracto OSM, los cruza con una lista curada de lugares
reconocibles y los engancha a las calles vecinas del grafo de city.json.
Escribe la clave "landmarks" dentro de city.json:

    [lon, lat, "Nombre", "emoji", [índices de calles vecinas]]

Uso: python3 build_landmarks.py Santiago.osm.pbf city.json
"""
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict

import pandas as pd
from pyrosm import OSM
from shapely.affinity import scale as shp_scale
from shapely.geometry import LineString
from shapely import STRtree

PBF = sys.argv[1] if len(sys.argv) > 1 else "Santiago.osm.pbf"
CITY = sys.argv[2] if len(sys.argv) > 2 else "city.json"

# Radio para enganchar un lugar a las calles que lo rodean
RADII_M, MIN_STREETS, MAX_STREETS = (60, 120, 250, 450), 3, 20

# --- Lista curada -----------------------------------------------------------
# (patrón de búsqueda, nombre a mostrar, ícono[, (lon, lat) de referencia])
# El patrón se busca dentro del nombre OSM normalizado y las coordenadas salen
# de OSM, para no escribirlas a mano. El 4º campo es opcional y solo se usa
# cuando hay varios POIs con el MISMO nombre (p. ej. sedes de una clínica):
# entre los candidatos se elige el más cercano a esa referencia.
CURATED = [
    # Centro cívico e hitos
    ("palacio de la moneda",        "Palacio de La Moneda", "🏛️"),
    ("plaza de armas",              "Plaza de Armas", "⛲"),
    ("catedral metropolitana",      "Catedral Metropolitana", "⛪"),
    ("mercado central",             "Mercado Central", "🐟"),
    ("vega central",                 "La Vega Central", "🥬"),
    ("estacion mapocho",            "Estación Mapocho", "🚉"),
    ("biblioteca nacional",         "Biblioteca Nacional", "📚"),
    ("teatro municipal de santiago", "Teatro Municipal", "🎭"),
    ("centro cultural gabriela mistral gam", "Centro Cultural GAM", "🎭"),
    ("matucana 100",                "Matucana 100", "🎭"),
    ("londres 38",                  "Londres 38", "🕯️"),
    ("villa grimaldi",              "Villa Grimaldi", "🕯️"),
    ("museo de la memoria",         "Museo de la Memoria", "🏛️"),
    ("museo nacional de bellas artes", "Museo de Bellas Artes", "🖼️"),
    ("museo historico nacional",    "Museo Histórico Nacional", "🏛️"),
    ("museo artequin",              "Museo Artequin", "🖼️"),
    ("planetario",                  "Planetario Usach", "🔭"),
    ("la chascona",                 "La Chascona", "🏠"),
    ("palacio cousino",             "Palacio Cousiño", "🏛️"),
    ("iglesia de san francisco",    "Iglesia de San Francisco", "⛪"),
    ("basilica de la merced",       "Basílica de la Merced", "⛪"),
    ("basilica del salvador",       "Basílica del Salvador", "⛪"),
    ("iglesia de los dominicos",    "Los Dominicos", "⛪"),
    ("templo votivo de maipu",      "Templo Votivo de Maipú", "⛪"),
    ("cementerio general",          "Cementerio General", "🪦"),
    ("costanera center",            "Costanera Center", "🏙️"),
    ("ex congreso nacional",        "Ex Congreso Nacional", "🏛️"),
    ("palacio de los tribunales",    "Palacio de Tribunales", "⚖️"),

    # Parques y cerros
    ("cerro santa lucia",           "Cerro Santa Lucía", "⛰️"),
    ("cerro san cristobal",          "Cerro San Cristóbal", "⛰️"),
    ("cerro blanco",                "Cerro Blanco", "⛰️"),
    ("cerro renca",                 "Cerro Renca", "⛰️"),
    ("parque forestal",             "Parque Forestal", "🌳"),
    ("parque bustamante",           "Parque Bustamante", "🌳"),
    ("parque o'higgins",            "Parque O'Higgins", "🌳"),
    ("parque ohiggins",             "Parque O'Higgins", "🌳"),
    ("quinta normal",               "Parque Quinta Normal", "🌳"),
    ("parque araucano",             "Parque Araucano", "🌳"),
    ("parque bicentenario",         "Parque Bicentenario", "🌳"),
    ("parque almagro",              "Parque Almagro", "🌳"),
    ("parque balmaceda",            "Parque Balmaceda", "🌳"),
    ("parque intercomunal padre hurtado", "Parque Padre Hurtado", "🌳"),
    ("parque mahuida",              "Parque Mahuida", "🌳"),
    ("parque de los reyes",         "Parque de los Reyes", "🌳"),
    ("jardin botanico chagual",      "Jardín Botánico Chagual", "🌳"),
    ("zoologico nacional",          "Zoológico Nacional", "🦁"),
    ("fantasilandia",               "Fantasilandia", "🎡"),

    # Deportes
    ("estadio nacional",            "Estadio Nacional", "🏟️"),
    ("estadio monumental",          "Estadio Monumental", "🏟️"),
    ("movistar arena",              "Movistar Arena", "🏟️"),
    ("club hipico",                 "Club Hípico", "🏇"),
    ("hipodromo chile",             "Hipódromo Chile", "🏇"),
    ("estadio victor jara",         "Estadio Víctor Jara", "🏟️"),

    # Universidades
    ("casa central universidad de chile", "Casa Central U. de Chile", "🎓"),
    ("pontificia universidad catolica de chile", "Casa Central UC", "🎓"),
    ("pontificia universidad catolica de chile campus san joaquin",
     "Campus San Joaquín UC", "🎓"),
    ("campus oriente",              "Campus Oriente UC", "🎓"),
    ("universidad de chile campus juan gomez millas", "Campus Juan Gómez Millas", "🎓"),
    ("universidad de santiago de chile", "Universidad de Santiago (Usach)", "🎓"),
    ("universidad diego portales",  "Universidad Diego Portales", "🎓"),
    ("universidad central",         "Universidad Central", "🎓"),
    ("universidad tecnica federico santa maria campus san joaquin", "UTFSM San Joaquín", "🎓"),

    # Salud
    ("hospital del salvador",       "Hospital del Salvador", "🏥"),
    ("hospital barros luco",        "Hospital Barros Luco", "🏥"),
    ("hospital san juan de dios",   "Hospital San Juan de Dios", "🏥"),
    ("calvo mackenna",              "Hospital Calvo Mackenna", "🏥"),
    ("hospital san jose",           "Hospital San José", "🏥"),
    ("sotero del rio",              "Hospital Sótero del Río", "🏥"),
    ("clinica alemana",             "Clínica Alemana", "🏥", (-70.5728, -33.3925)),
    ("clinica las condes",          "Clínica Las Condes", "🏥"),
    ("clinica santa maria",         "Clínica Santa María", "🏥"),
    ("hospital san borja",          "Hospital San Borja Arriarán", "🏥"),

    # Comercio
    ("costanera center",            "Costanera Center", "🛍️"),
    ("parque arauco",               "Mall Parque Arauco", "🛍️"),
    ("alto las condes",             "Mall Alto Las Condes", "🛍️"),
    ("mall plaza vespucio",         "Mall Plaza Vespucio", "🛍️"),
    ("mall plaza norte",            "Mall Plaza Norte", "🛍️"),
    ("mall plaza egana",            "Mall Plaza Egaña", "🛍️"),
    ("apumanque",                   "Apumanque", "🛍️"),
    ("portal la dehesa",            "Portal La Dehesa", "🛍️"),
    ("persa bio bio",               "Persa Bío Bío", "🛍️"),

    # Transporte
    ("estacion central",            "Estación Central", "🚉"),
    ("aeropuerto internacional comodoro arturo merino benitez",
     "Aeropuerto A. Merino Benítez", "✈️"),
    ("terminal san borja",          "Terminal San Borja", "🚌"),
    ("terminal alameda",            "Terminal Alameda", "🚌"),
    ("intermodal la cisterna",      "Intermodal La Cisterna", "🚌"),
    ("intermodal pajaritos",        "Intermodal Pajaritos", "🚌"),
]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s)).strip()


print(f"Leyendo POIs de {PBF} ...")
osm = OSM(PBF)
flt = {
    "tourism": True, "leisure": ["park", "stadium", "sports_centre", "garden"],
    "amenity": ["university", "hospital", "clinic", "theatre", "arts_centre",
                "place_of_worship", "marketplace", "library", "bus_station"],
    "historic": True, "aeroway": ["aerodrome"], "railway": ["station"],
    "shop": ["mall", "department_store"], "natural": ["peak"],
    "building": True, "landuse": ["cemetery"], "man_made": ["tower"],
    "office": ["government"],
}
pois = osm.get_pois(custom_filter=flt)
pois = pois[pois["name"].notna()].copy()
pois["nn"] = pois["name"].map(norm)
# centroide: los POIs de área vienen como geometría
geoms = pois.geometry.centroid if hasattr(pois, "geometry") else None
pois["clon"] = geoms.x.values
pois["clat"] = geoms.y.values
print(f"POIs con nombre: {len(pois)}")

# --- Emparejar la lista curada con los POIs ---------------------------
found, missing = {}, []
for entry in CURATED:
    pattern, display, icon = entry[:3]
    ref = entry[3] if len(entry) > 3 else None
    p = norm(pattern)
    hits = pois[pois["nn"].str.contains(re.escape(p), regex=True, na=False)]
    if not len(hits):
        missing.append(display)
        continue
    if ref is not None:                    # desempate por cercanía a la referencia
        d = (hits["clon"] - ref[0]) ** 2 + (hits["clat"] - ref[1]) ** 2
        best = hits.loc[d.idxmin()]
    else:
        # el candidato cuyo nombre se parece más al patrón (menos "sobrante")
        best = hits.iloc[(hits["nn"].str.len() - len(p)).abs().argsort().values[0]]
    key = display
    if key in found:                       # patrones duplicados (ej. Costanera)
        continue
    found[key] = {"name": display, "icon": icon,
                  "lon": float(best["clon"]), "lat": float(best["clat"]),
                  "geom": best["geometry"], "osm": str(best["name"])}
print(f"Emparejados: {len(found)} · sin match: {len(missing)}")
print("\n--- Auditoría: lugar -> POI de OSM elegido ---")
for f in found.values():
    print(f"  {f['name']:34} <- {f['osm'][:46]:48} ({f['lon']:.4f}, {f['lat']:.4f})")
print()
if missing:
    print("  sin match ->", ", ".join(missing))

# --- Enganchar cada lugar a las calles vecinas ------------------------
city = json.load(open(CITY, encoding="utf-8"))
S, ENC = city["streets"], city.get("enc", 1e5)

def decode(enc):
    out, x, y = [], 0, 0
    for i in range(0, len(enc), 2):
        x += enc[i]; y += enc[i + 1]
        out.append((x / ENC, y / ENC))          # (lon, lat)
    return out

# Los lugares de área (parques, cerros, estadios) se enganchan a las calles
# que bordean su POLÍGONO, no a las cercanas a su centroide: en un parque
# grande el centro está a cientos de metros de cualquier calle, y el jugador
# que nombra las calles que lo rodean no lograba cerrar la conexión.
K = math.cos(math.radians(-33.45))        # escala de longitud -> métrica local
DEG_M = 111320.0

def scale(geom):
    return shp_scale(geom, xfact=K, yfact=1.0, origin=(0, 0))

lines, owner = [], []
for i, s in enumerate(S):
    for enc in s["g"]:
        pts = decode(enc)
        if len(pts) >= 2:
            lines.append(scale(LineString(pts)))
            owner.append(i)
tree = STRtree(lines)
print(f"Segmentos indexados: {len(lines)}")

landmarks = []
sin_calles = []
for lm in found.values():
    g = scale(lm["geom"])
    # Radio progresivo: un polígono grande ya toca varias calles en su borde;
    # un POI puntual (un cerro, un edificio) necesita alcance para llegar a la
    # calle de al lado. Se para al juntar MIN_STREETS.
    dists = {}
    for radio in RADII_M:
        idx = tree.query(g.buffer(radio / DEG_M))
        dists = {}
        for j in idx:
            d = g.distance(lines[j]) * DEG_M
            i = owner[j]
            if d <= radio and (i not in dists or d < dists[i]):
                dists[i] = d
        if len(dists) >= MIN_STREETS:
            break
    if not dists:
        sin_calles.append(lm["name"])
        continue
    ids = sorted({i for _, i in sorted((d, i) for i, d in dists.items())[:MAX_STREETS]})
    landmarks.append([round(lm["lon"], 5), round(lm["lat"], 5),
                      lm["name"], lm["icon"], ids])

if sin_calles:
    print("  sin calles cerca (descartados) ->", ", ".join(sin_calles))
print(f"Lugares con calles asociadas: {len(landmarks)}")

city["landmarks"] = landmarks
with open(CITY, "w", encoding="utf-8") as f:
    json.dump(city, f, ensure_ascii=False, separators=(",", ":"))
import os
print(f"OK -> {CITY} ({os.path.getsize(CITY)/1e6:.2f} MB)")
