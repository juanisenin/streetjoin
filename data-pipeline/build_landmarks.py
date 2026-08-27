#!/usr/bin/env python3
"""StreetJoin — lugares icónicos del Gran Santiago.

Lee los POIs del extracto OSM, los cruza con una lista curada de lugares
reconocibles y los engancha a las calles vecinas del grafo de city.json.
Escribe la clave "landmarks" dentro de city.json:

    [lon, lat, "Nombre", "emoji", [índices de calles vecinas], "Comuna"]

Uso: python3 build_landmarks.py Santiago.osm.pbf city.json
"""
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict

import os

import geopandas as gpd
import pandas as pd
from pyrosm import OSM
from shapely.affinity import scale as shp_scale
from shapely.geometry import LineString, Point
from shapely import STRtree

PBF = sys.argv[1] if len(sys.argv) > 1 else "Santiago.osm.pbf"
CITY = sys.argv[2] if len(sys.argv) > 2 else "city.json"

# Radio para enganchar un lugar a las calles que lo rodean
RADII_M, MIN_STREETS, MAX_STREETS = (60, 120, 250, 450, 700), 3, 20

# --- Lista curada -----------------------------------------------------------
# (patrón de búsqueda, nombre a mostrar, ícono[, (lon, lat) de referencia])
# El patrón se busca dentro del nombre OSM normalizado y las coordenadas salen
# de OSM, para no escribirlas a mano. El 4º campo es opcional: desempata entre
# varios POIs que matchean el patrón eligiendo el más cercano a esa referencia.
# En los lugares agregados por comuna va SIEMPRE (sale del propio POI de OSM),
# porque con ~200 entradas los nombres genéricos se repiten entre comunas
# ("Parque Juan Pablo II" existe en Las Condes y en Puente Alto).
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

    # ======== Cobertura por comuna (2026-08-27) ========
    # --- Independencia ---
    ("universidad de chile (campus eloísa díaz)", "Campus Eloísa Díaz U. de Chile", "🎓", (-70.65337, -33.42002)),
    ("mall barrio independencia", "Mall Barrio Independencia", "🛍️", (-70.65365, -33.4242)),
    ("hospital de niños doctor roberto del río", "Hospital Roberto del Río", "🏥", (-70.65483, -33.41527)),
    # --- Recoleta ---
    ("clínica dávila", "Clínica Dávila", "🏥", (-70.64828, -33.4274)),
    ("parque mahuidahue", "Parque Mahuidahue", "🌳", (-70.61875, -33.40405)),
    ("estación intermodal vespucio norte", "Intermodal Vespucio Norte", "🚌", (-70.64708, -33.38063)),
    ("cementerio israelita de recoleta", "Cementerio Israelita", "🪦", (-70.63396, -33.39722)),
    # --- Conchalí ---
    ("ilustre municipalidad de conchalí", "Municipalidad de Conchalí", "🏛️", (-70.67086, -33.39626)),
    ("parque las américas", "Parque Las Américas", "🌳", (-70.69104, -33.38525)),
    ("parque pedro fontova", "Parque Pedro Fontova", "🌳", (-70.67204, -33.38437)),
    ("parque arboleda el cortijo", "Parque El Cortijo", "🌳", (-70.68726, -33.37859)),
    # --- Huechuraba ---
    ("parque del recuerdo américo vespucio", "Parque del Recuerdo", "🪦", (-70.63346, -33.38468)),
    ("bosque santiago", "Bosque Santiago", "🌲", (-70.6033, -33.37265)),
    ("universidad mayor", "Universidad Mayor", "🎓", (-70.61462, -33.37705)),
    ("estadio municipal raúl inostroza", "Estadio Raúl Inostroza", "🏟️", (-70.64273, -33.37012)),
    # --- Quilicura ---
    ("mall arauco quilicura", "Mall Arauco Quilicura", "🛍️", (-70.72998, -33.36829)),
    ("arauco premium outlet buenaventura", "Outlet Buenaventura", "🛍️", (-70.70362, -33.33198)),
    ("ilustre municipalidad de quilicura", "Municipalidad de Quilicura", "🏛️", (-70.73231, -33.36889)),
    ("humedal urbano de quilicura", "Humedal de Quilicura", "🦆", (-70.76431, -33.34081)),
    ("cementerio municipal quilicura", "Cementerio de Quilicura", "🪦", (-70.74101, -33.38409)),
    # --- Renca ---
    ("parque metropolitano cerros de renca", "Cerro Renca", "⛰️", (-70.71837, -33.39804)),
    ("parque de la alegría", "Parque de la Alegría", "🌳", (-70.73344, -33.41167)),
    ("estadio los tilos", "Estadio Los Tilos", "🏟️", (-70.6945, -33.40463)),
    ("ilustre municipalidad de renca", "Municipalidad de Renca", "🏛️", (-70.70415, -33.40454)),
    ("parque las palmeras", "Parque Las Palmeras", "🌳", (-70.69456, -33.40203)),
    # --- Cerro Navia ---
    ("parque la hondonada", "Parque La Hondonada", "🌳", (-70.75873, -33.42582)),
    ("hospital clínico félix bulnes", "Hospital Félix Bulnes", "🏥", (-70.7417, -33.42396)),
    ("ilustre municipalidad de cerro navia", "Municipalidad de Cerro Navia", "🏛️", (-70.72903, -33.43437)),
    # --- Lo Prado ---
    ("estadio municipal santa anita", "Estadio Santa Anita", "🏟️", (-70.71603, -33.4408)),
    ("parque de los niños", "Parque de los Niños", "🌳", (-70.71901, -33.44042)),
    ("municipalidad de lo prado", "Municipalidad de Lo Prado", "🏛️", (-70.71838, -33.44263)),
    # --- Pudahuel ---
    ("ilustre municipalidad de pudahuel", "Municipalidad de Pudahuel", "🏛️", (-70.74296, -33.44646)),
    ("estadio modelo de pudahuel", "Estadio Modelo de Pudahuel", "🏟️", (-70.74082, -33.44825)),
    ("parque santiago amengual", "Parque Santiago Amengual", "🌳", (-70.74917, -33.44701)),
    ("cementerio canaán", "Cementerio Canaán", "🪦", (-70.80423, -33.44244)),
    # --- Quinta Normal ---
    ("parque de la familia", "Parque de la Familia", "🌳", (-70.68021, -33.42407)),
    ("basílica de lourdes", "Basílica de Lourdes", "⛪", (-70.68585, -33.43838)),
    ("estadio municipal bernardo o'higgins", "Estadio Bernardo O'Higgins", "🏟️", (-70.69903, -33.44665)),
    ("centro cultural perrera arte", "Perrera Arte", "🎭", (-70.67278, -33.42736)),
    # --- Estación Central ---
    ("mall plaza alameda", "Mall Plaza Alameda", "🛍️", (-70.6822, -33.45288)),
    ("parque bernardo leighton", "Parque Bernardo Leighton", "🌳", (-70.69491, -33.46565)),
    # --- Cerrillos ---
    ("parque bicentenario cerrillos", "Parque Bicentenario de Cerrillos", "🌳", (-70.6995, -33.49399)),
    ("museo nacional aeronáutico", "Museo Aeronáutico", "✈️", (-70.69684, -33.48741)),
    ("escuela de formación de carabineros", "Escuela de Carabineros", "🎖️", (-70.71184, -33.49747)),
    ("parque san luis de orione", "Parque San Luis de Orione", "🌳", (-70.71232, -33.51085)),
    # --- Maipú ---
    ("mall arauco maipú", "Mall Arauco Maipú", "🛍️", (-70.7509, -33.48258)),
    ("plaza de maipú", "Plaza de Maipú", "⛲", (-70.757, -33.5102)),
    ("estadio municipal santiago bueras", "Estadio Santiago Bueras", "🏟️", (-70.74884, -33.50826)),
    ("hospital metropolitano el carmen", "Hospital El Carmen", "🏥", (-70.77427, -33.50807)),
    ("parque tres poniente", "Parque Tres Poniente", "🌳", (-70.77861, -33.51542)),
    ("parque municipal de maipú", "Parque Municipal de Maipú", "🌳", (-70.80151, -33.52439)),
    # --- Pedro Aguirre Cerda ---
    ("mercado mayorista lo valledor", "Lo Valledor", "🥬", (-70.68373, -33.48225)),
    ("parque andré jarlán", "Parque André Jarlán", "🌳", (-70.66978, -33.48529)),
    ("portal ochagavía", "Portal Ochagavía", "🛍️", (-70.66798, -33.5011)),
    ("estadio corvi", "Estadio Corvi", "🏟️", (-70.67217, -33.4826)),
    # --- Lo Espejo ---
    ("cementerio metropolitano", "Cementerio Metropolitano", "🪦", (-70.68372, -33.52691)),
    ("parque pablo neruda", "Parque Pablo Neruda", "🌳", (-70.68488, -33.51269)),
    ("estadio clara estrella", "Estadio Clara Estrella", "🏟️", (-70.67706, -33.5183)),
    ("ilustre municipalidad de lo espejo", "Municipalidad de Lo Espejo", "🏛️", (-70.69852, -33.52263)),
    # --- San Miguel ---
    ("parque llano subercaseaux", "Parque Llano Subercaseaux", "🌳", (-70.65019, -33.485)),
    ("espacio urbano gran avenida", "Espacio Urbano Gran Avenida", "🛍️", (-70.65602, -33.5123)),
    ("hospital de niños doctor exequiel gonzález", "Hospital Exequiel González Cortés", "🏥", (-70.64813, -33.48485)),
    ("estadio el llano", "Estadio El Llano", "🏟️", (-70.65341, -33.48273)),
    # --- San Joaquín ---
    ("parque la castrina", "Parque La Castrina", "🌳", (-70.62955, -33.5111)),
    ("parque intercomunal victor jara", "Parque Víctor Jara", "🌳", (-70.63658, -33.47912)),
    ("la fábrica patio outlet", "La Fábrica Patio Outlet", "🛍️", (-70.62657, -33.48698)),
    # --- La Cisterna ---
    ("complejo deportivo la cisterna", "Complejo Deportivo La Cisterna", "🏟️", (-70.67254, -33.52009)),
    ("centro deportivo azul", "Centro Deportivo Azul (CDA)", "⚽", (-70.66879, -33.52135)),
    ("persa lo ovalle", "Persa Lo Ovalle", "🛍️", (-70.65963, -33.51721)),
    # --- El Bosque ---
    ("escuela de aviación capitán manuel ávalos", "Escuela de Aviación", "✈️", (-70.68301, -33.56203)),
    ("estadio lo blanco", "Estadio Lo Blanco", "🏟️", (-70.68176, -33.57873)),
    ("arauco el bosque", "Mall Arauco El Bosque", "🛍️", (-70.67684, -33.55324)),
    ("ilustre municipalidad de el bosque", "Municipalidad de El Bosque", "🏛️", (-70.66549, -33.55669)),
    # --- La Granja ---
    ("museo interactivo mirador", "Museo Interactivo Mirador (MIM)", "🔬", (-70.61342, -33.51888)),
    ("parque municipal de la granja", "Parque La Granja", "🌳", (-70.6139, -33.51946)),
    ("estadio san gregorio", "Estadio San Gregorio", "🏟️", (-70.63256, -33.53659)),
    ("centro cultural espacio matta", "Espacio Matta", "🎭", (-70.63273, -33.54374)),
    # --- San Ramón ---
    ("parque la bandera", "Parque La Bandera", "🌳", (-70.64159, -33.54225)),
    ("hospital padre hurtado", "Hospital Padre Hurtado", "🏥", (-70.63511, -33.55238)),
    ("estadio municipal de san ramón", "Estadio de San Ramón", "🏟️", (-70.64278, -33.53215)),
    # --- La Pintana ---
    ("campus antumapu", "Campus Antumapu U. de Chile", "🎓", (-70.63298, -33.56961)),
    ("estadio municipal de la pintana", "Estadio de La Pintana", "🏟️", (-70.63629, -33.58664)),
    ("parque mapuhue", "Parque Mapuhue", "🌳", (-70.6294, -33.59134)),
    ("ilustre municipalidad de la pintana", "Municipalidad de La Pintana", "🏛️", (-70.62963, -33.58484)),
    # --- San Bernardo ---
    ("parque metropolitano sur cerro chena", "Cerro Chena", "⛰️", (-70.72059, -33.60143)),
    ("mallplaza sur", "Mallplaza Sur", "🛍️", (-70.70978, -33.63222)),
    ("estadio municipal san bernardo", "Estadio Municipal de San Bernardo", "🏟️", (-70.68997, -33.59457)),
    ("hospital el pino", "Hospital El Pino", "🏥", (-70.67475, -33.58475)),
    ("mall paseo san bernardo", "Paseo San Bernardo", "🛍️", (-70.70726, -33.59546)),
    # --- Puente Alto ---
    ("mall plaza tobalaba", "Mall Plaza Tobalaba", "🛍️", (-70.55765, -33.56928)),
    ("plaza de puente alto", "Plaza de Puente Alto", "⛲", (-70.57547, -33.60952)),
    ("parque juan pablo ii", "Parque Juan Pablo II", "🌳", (-70.61514, -33.62421)),
    ("club de campo las vizcachas", "Las Vizcachas", "🏁", (-70.52382, -33.60213)),
    ("open plaza puente alto", "Open Plaza Puente Alto", "🛍️", (-70.57708, -33.59702)),
    # --- La Florida ---
    ("estadio bicentenario municipal de la florida", "Estadio Bicentenario La Florida", "🏟️", (-70.57807, -33.54074)),
    ("hospital clínico metropolitano de la florida", "Hospital de La Florida", "🏥", (-70.59859, -33.51421)),
    ("parque comunitario bosque panul", "Bosque Panul", "🌲", (-70.51115, -33.53556)),
    ("clínica bupa santiago", "Clínica Bupa Santiago", "🏥", (-70.59764, -33.5106)),
    ("ilustre municipalidad de la florida", "Municipalidad de La Florida", "🏛️", (-70.58713, -33.55881)),
    # --- Macul ---
    ("complejo deportivo juan pinto durán", "Juan Pinto Durán", "⚽", (-70.59438, -33.49973)),
    ("instituto de nutrición y tecnología", "INTA", "🎓", (-70.59263, -33.50234)),
    ("inacap santiago sur", "Inacap Macul", "🎓", (-70.61671, -33.49026)),
    # --- Ñuñoa ---
    ("plaza ñuñoa", "Plaza Ñuñoa", "⛲", (-70.59371, -33.45608)),
    ("universidad metropolitana de ciencias de la", "UMCE (Pedagógico)", "🎓", (-70.60308, -33.46712)),
    ("mall cenco ñuñoa", "Mall Cenco Ñuñoa", "🛍️", (-70.59733, -33.46533)),
    ("parque juan moya", "Parque Juan Moya", "🌳", (-70.59059, -33.4672)),
    # --- Peñalolén ---
    ("campus peñalolén universidad adolfo ibáñez", "U. Adolfo Ibáñez", "🎓", (-70.51481, -33.48843)),
    ("parque viña cousiño macul", "Viña Cousiño Macul", "🍇", (-70.56613, -33.4951)),
    ("parque natural quebrada de macul", "Quebrada de Macul", "⛰️", (-70.48243, -33.49089)),
    ("estadio municipal de peñalolen", "Estadio de Peñalolén", "🏟️", (-70.5429, -33.47909)),
    ("hospital doctor luis tisné", "Hospital Luis Tisné", "🏥", (-70.57903, -33.50035)),
    # --- La Reina ---
    ("hospital militar de santiago", "Hospital Militar", "🏥", (-70.53779, -33.45026)),
    ("aldea del encuentro", "Aldea del Encuentro", "🎪", (-70.53196, -33.45121)),
    ("aeródromo eulogio sánchez", "Aeródromo de Tobalaba", "🛩️", (-70.54807, -33.45688)),
    # --- Las Condes ---
    ("escuela militar del general", "Escuela Militar", "🎖️", (-70.58142, -33.40974)),
    ("club de golf los leones", "Club de Golf Los Leones", "⛳", (-70.59283, -33.40863)),
    ("complejo deportivo san carlos de apoquindo", "San Carlos de Apoquindo", "🏟️", (-70.49911, -33.39676)),
    ("parque juan pablo ii", "Parque Juan Pablo II", "🌳", (-70.56807, -33.40033)),
    # --- Vitacura ---
    ("club de polo y equitación san cristóbal", "Club de Polo San Cristóbal", "🐴", (-70.58791, -33.38656)),
    ("aeródromo municipal de vitacura", "Aeródromo de Vitacura", "🛩️", (-70.58064, -33.38007)),
    ("casacostanera", "Casacostanera", "🛍️", (-70.5986, -33.39842)),
    # --- Lo Barnechea ---
    ("parque de la chilenidad", "Parque de la Chilenidad", "🌳", (-70.49476, -33.35682)),
    ("ilustre municipalidad de lo barnechea", "Municipalidad de Lo Barnechea", "🏛️", (-70.52, -33.35341)),
    ("espacio urbano la dehesa", "Espacio Urbano La Dehesa", "🛍️", (-70.52074, -33.3523)),
    # --- Colina ---
    ("espacio urbano la laguna", "Espacio Urbano La Laguna", "🛍️", (-70.62784, -33.27796)),
    ("cementerio de colina", "Cementerio de Colina", "🪦", (-70.66254, -33.19642)),
    ("ilustre municipalidad de colina", "Municipalidad de Colina", "🏛️", (-70.68397, -33.20509)),
    ("medialuna municipal de colina", "Medialuna de Colina", "🐴", (-70.63723, -33.17775)),
    # --- Santiago ---
    ("mercado matadero franklin", "Matadero Franklin", "🛍️", (-70.64512, -33.47354)),
    ("plaza brasil", "Plaza Brasil", "⛲", (-70.66591, -33.44057)),
    ("plaza yungay", "Plaza Yungay", "⛲", (-70.67403, -33.43752)),
    # --- Providencia ---
    ("plaza baquedano", "Plaza Baquedano", "⛲", (-70.63432, -33.43674)),
]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s)).strip()


# --- Comunas -----------------------------------------------------------------
# Con lugares repartidos por todo el Gran Santiago, el nombre solo no alcanza:
# "Parque Juan Pablo II" existe en Las Condes y en Puente Alto, y un jugador no
# puede ubicar "Parque Las Palmeras" sin saber que está en Renca. La comuna
# viaja en el JSON y el juego la muestra debajo del nombre.
COMUNAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comunas-rm.geojson")
_com = gpd.read_file(COMUNAS)
_com_tree = STRtree(list(_com.geometry.values))
_com_names = list(_com["Comuna"].values)


def comuna_de(lon, lat):
    """Comuna que contiene el punto; si cae en un hueco, la más cercana."""
    p = Point(lon, lat)
    for j in _com_tree.query(p):
        if _com.geometry.values[j].contains(p):
            return _com_names[j]
    j = _com_tree.nearest(p)
    return _com_names[int(j)]


print(f"Leyendo POIs de {PBF} ...")
osm = OSM(PBF)
flt = {
    "tourism": True,
    "leisure": ["park", "stadium", "sports_centre", "garden", "nature_reserve"],
    "amenity": ["university", "college", "hospital", "clinic", "theatre", "arts_centre",
                "place_of_worship", "marketplace", "library", "bus_station", "townhall",
                "cinema", "courthouse"],
    "historic": True, "aeroway": ["aerodrome"], "railway": ["station"],
    "shop": ["mall", "department_store"], "natural": ["peak"],
    "building": True, "landuse": ["cemetery", "recreation_ground"],
    "man_made": ["tower"], "office": ["government"], "place": ["square"],
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
    lon, lat = float(best["clon"]), float(best["clat"])
    com = comuna_de(lon, lat)
    key = (display, com)                   # el nombre solo se repite entre comunas
    if key in found:                       # patrones duplicados (ej. Costanera)
        continue
    found[key] = {"name": display, "icon": icon, "comuna": com,
                  "lon": lon, "lat": lat,
                  "geom": best["geometry"], "osm": str(best["name"])}
print(f"Emparejados: {len(found)} · sin match: {len(missing)}")
print("\n--- Auditoría: lugar -> POI de OSM elegido ---")
for f in found.values():
    print(f"  {f['comuna'][:18]:19} {f['name'][:32]:34} <- {f['osm'][:44]:46} ({f['lon']:.4f}, {f['lat']:.4f})")
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
                      lm["name"], lm["icon"], ids, lm["comuna"]])

if sin_calles:
    print("  sin calles cerca (descartados) ->", ", ".join(sin_calles))
print(f"Lugares con calles asociadas: {len(landmarks)}")

# Resumen de cobertura: el objetivo del dataset es que ninguna comuna del Gran
# Santiago quede vacía, no maximizar el total.
por_com = defaultdict(int)
for l in landmarks:
    por_com[l[5]] += 1
print("\n--- Lugares por comuna ---")
for c, n in sorted(por_com.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"  {n:3}  {c}")
print(f"  ({len(por_com)} comunas)")

city["landmarks"] = landmarks
with open(CITY, "w", encoding="utf-8") as f:
    json.dump(city, f, ensure_ascii=False, separators=(",", ":"))
import os
print(f"OK -> {CITY} ({os.path.getsize(CITY)/1e6:.2f} MB)")
