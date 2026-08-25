#!/usr/bin/env python3
"""StreetJoin — pipeline OSM -> city.json (v2, escala Gran Santiago)

Cambios clave vs v1:
- Una "calle" ya no es todo lo que comparte nombre: es una COMPONENTE CONEXA
  de segmentos con el mismo nombre (evita fusionar homónimas de comunas
  distintas, que romperia la conectividad del juego con "teletransportes").
- Componentes del mismo nombre a <150 m se fusionan (calles interrumpidas
  por plazas/autopistas siguen siendo una sola calle).
- Geometrias delta-encoded (enteros x1e5) para reducir el peso del JSON.
- Exporta solo intersecciones candidatas a puzzle (>=2 calles, al menos una
  arterial), con tope de 6000 muestreadas.
"""
import json
import random
import re
import sys
import unicodedata
from collections import defaultdict

import numpy as np
import networkx as nx
from pyrosm import OSM
from shapely.geometry import MultiLineString
from shapely.ops import linemerge

PBF = sys.argv[1] if len(sys.argv) > 1 else "Santiago.osm.pbf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "city.json"

# living_street y pedestrian quedan fuera: en Santiago son casi todos pasajes
# interiores que nadie memoriza y representaban ~70% del peso del dataset.
KEEP = {"motorway", "trunk", "motorway_link", "trunk_link",
        "primary", "secondary", "tertiary", "residential", "unclassified"}
# Rampas y enlaces: casi siempre sin nombre. No son calles "nombrables", pero
# son la única unión entre una autopista y las calles de superficie, así que se
# usan como pegamento de conectividad (ver GLUE más abajo).
LINK_CLASSES = {"motorway_link", "trunk_link", "primary_link",
                "secondary_link", "tertiary_link"}
# nombres que igual son pasajes aunque la vía esté tageada como residential
PASAJE_RE = re.compile(r"^(pasaje|psje|pje)\b", re.I)
CLASS_RANK = {"motorway": 0, "trunk": 0, "motorway_link": 0, "trunk_link": 0,
              "primary": 0, "secondary": 1, "tertiary": 2,
              "residential": 3, "unclassified": 3}
SIMPLIFY = {0: 6e-5, 1: 6e-5, 2: 1e-4, 3: 1.5e-4}
MERGE_DIST_M = 150
MAX_INTERSECTIONS = 14000

PREFIXES = re.compile(
    r"^(avenida|av|avda|calle|pasaje|pje|psje|paseo|camino|autopista|general|gral)\s+")
AV_PREFIX = re.compile(r"^(avenida|av|avda|calle)\s+")


def normalize(name):
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def alias_keys(name):
    keys, n = set(), normalize(name)
    if not n:
        return keys
    keys.add(n)
    st = PREFIXES.sub("", n)
    while st != n:
        n = st
        keys.add(n)
        st = PREFIXES.sub("", n)
    return keys


print(f"Leyendo {PBF} ...")
osm = OSM(PBF)
nodes, edges = osm.get_network(
    network_type="all", nodes=True,
    extra_attributes=["alt_name", "short_name", "loc_name", "official_name"])
all_edges = edges
edges = edges[edges["highway"].isin(KEEP) & edges["name"].notna()].copy()
edges["name"] = edges["name"].astype(str)
edges = edges[~edges["name"].str.match(PASAJE_RE)]
print(f"Segmentos con nombre (sin pasajes): {len(edges)}")

# --- 0) Pegamento: rampas/enlaces sin nombre --------------------------
# Une los extremos de cada rampa en un mismo "nodo virtual", de modo que las
# calles que tocan cualquiera de sus puntas queden adyacentes. Sin esto las
# autopistas quedan como islas y se caen de la componente conexa mayor.
glue_rows = all_edges[all_edges["highway"].isin(LINK_CLASSES)]
glue_parent = {}
def glue_find(x):
    glue_parent.setdefault(x, x)
    while glue_parent[x] != x:
        glue_parent[x] = glue_parent[glue_parent[x]]
        x = glue_parent[x]
    return x
def glue_union(a, b):
    ra, rb = glue_find(a), glue_find(b)
    if ra != rb:
        glue_parent[rb] = ra
for r in glue_rows.itertuples():
    glue_union(r.u, r.v)
print(f"Rampas/enlaces usados como conectores: {len(glue_rows)}")

def node_key(n):                       # nodo real -> nodo lógico (rampas unidas)
    return glue_find(n) if n in glue_parent else n

node_xy = dict(zip(nodes["id"], zip(nodes["lon"], nodes["lat"])))

# --- 1) Segmentos agrupados por nombre normalizado ---------------------
by_name = defaultdict(list)
EXTRA_COLS = [c for c in ("alt_name", "short_name", "loc_name", "official_name")
              if c in edges.columns]
for row in edges.itertuples():
    fk = normalize(row.name)
    if fk:
        by_name[fk].append(row)
print(f"Nombres únicos: {len(by_name)}")

# --- 2) Por nombre: componentes conexas + fusión por cercanía ----------
def components_by_nodes(rows):
    parent = {}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for r in rows:
        for n in (r.u, r.v):
            parent.setdefault(n, n)
        union(r.u, r.v)
    comp = defaultdict(list)
    for r in rows:
        comp[find(r.u)].append(r)
    return list(comp.values())


def merge_nearby(comps):
    if len(comps) <= 1:
        return comps
    pts = []
    for rows in comps:
        arr = np.array([node_xy[n] for r in rows for n in (r.u, r.v)])
        pts.append(arr)
    boxes = [(p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max())
             for p in pts]
    tol = MERGE_DIST_M / 92000  # grados aprox en lon a esta latitud
    parent = list(range(len(comps)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            bi, bj = boxes[i], boxes[j]
            if (bi[0] > bj[2] + tol or bj[0] > bi[2] + tol or
                    bi[1] > bj[3] + tol or bj[1] > bi[3] + tol):
                continue
            d2 = np.min(((pts[i][:, None, :] - pts[j][None, :, :]) ** 2).sum(-1)) \
                if len(pts[i]) * len(pts[j]) < 4e6 else tol ** 2  # cap: fusiona
            if d2 <= tol ** 2:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[rj] = ri
    merged = defaultdict(list)
    for i, rows in enumerate(comps):
        merged[find(i)].extend(rows)
    return list(merged.values())


streets = []
for fk, rows in by_name.items():
    for rows2 in merge_nearby(components_by_nodes(rows)):
        st = {"display": "", "keys": set(), "nodes": set(), "geoms": [], "rank": 9}
        for r in rows2:
            st["keys"] |= alias_keys(r.name)
            for col in EXTRA_COLS:
                extra = getattr(r, col, None)
                if isinstance(extra, str) and extra:
                    for part in re.split(r"[;,]", extra):
                        st["keys"] |= alias_keys(part)
            st["nodes"].update((r.u, r.v))
            st["geoms"].append(r.geometry)
            st["rank"] = min(st["rank"], CLASS_RANK.get(r.highway, 5))
            if len(r.name) > len(st["display"]):
                st["display"] = r.name
        streets.append(st)
print(f"Entidades de calle (componentes): {len(streets)}")

# --- 3) Fusión "Avenida X" / "X" si comparten intersección -------------
by_core = defaultdict(list)
for i, st in enumerate(streets):
    by_core[AV_PREFIX.sub("", normalize(st["display"]))].append(i)
parent = list(range(len(streets)))
def find_root(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
merged_pairs = 0
for group in by_core.values():
    for a in range(len(group)):
        for b in range(a + 1, len(group)):
            i, j = group[a], group[b]
            if streets[i]["nodes"] & streets[j]["nodes"]:
                ri, rj = find_root(i), find_root(j)
                if ri != rj:
                    parent[rj] = ri
                    merged_pairs += 1
if merged_pairs:
    new_streets, root_map = [], {}
    for i, st in enumerate(streets):
        r = find_root(i)
        if r not in root_map:
            root_map[r] = len(new_streets)
            new_streets.append({"display": "", "keys": set(), "nodes": set(),
                                "geoms": [], "rank": 9})
        t = new_streets[root_map[r]]
        t["keys"] |= st["keys"]; t["nodes"] |= st["nodes"]
        t["geoms"] += st["geoms"]; t["rank"] = min(t["rank"], st["rank"])
        if len(st["display"]) > len(t["display"]):
            t["display"] = st["display"]
    streets = new_streets
    print(f"Fusión av/calle: {merged_pairs} pares -> {len(streets)} calles")

# --- 4) Adyacencia y componente mayor ----------------------------------
node_streets = defaultdict(set)      # nodo lógico -> calles que lo tocan
real_of = {}                         # nodo lógico -> un nodo real (para coords)
for i, st in enumerate(streets):
    for n in st["nodes"]:
        k = node_key(n)
        node_streets[k].add(i)
        if k not in real_of or k == n:
            real_of[k] = n
adj = defaultdict(set)
for n, ss in node_streets.items():
    ss = list(ss)
    for a in range(len(ss)):
        for b in range(a + 1, len(ss)):
            adj[ss[a]].add(ss[b]); adj[ss[b]].add(ss[a])
G = nx.Graph(); G.add_nodes_from(range(len(streets)))
for a, bs in adj.items():
    for b in bs:
        G.add_edge(a, b)
comps = sorted(nx.connected_components(G), key=len, reverse=True)
giant = comps[0]
print(f"Componente mayor: {len(giant)}/{len(streets)} calles "
      f"({100*len(giant)/len(streets):.1f}%)")

# --- 5) Intersecciones candidatas (>=2 calles, una arterial) -----------
cands = []
for n, ss in node_streets.items():
    ss = sorted(s for s in ss if s in giant)
    real = real_of.get(n, n)
    if len(ss) >= 2 and any(streets[s]["rank"] <= 2 for s in ss) and real in node_xy:
        lon, lat = node_xy[real]
        cands.append([round(lon, 5), round(lat, 5), ss])
random.seed(20260814)
if len(cands) > MAX_INTERSECTIONS:
    cands = random.sample(cands, MAX_INTERSECTIONS)
print(f"Intersecciones candidatas: {len(cands)}")

# --- 6) Geometrías: linemerge + simplify + delta-encoding x1e5 ---------
def encode_lines(st):
    merged = linemerge(MultiLineString(
        [g for geom in st["geoms"]
         for g in (geom.geoms if geom.geom_type == "MultiLineString" else [geom])]))
    lines = merged.geoms if merged.geom_type == "MultiLineString" else [merged]
    tol = SIMPLIFY.get(st["rank"], 1.5e-4)
    out = []
    for line in lines:
        coords = list(line.simplify(tol, preserve_topology=False).coords)
        enc, px, py = [], 0, 0
        for k, (x, y) in enumerate(coords):
            xi, yi = round(x * 1e5), round(y * 1e5)
            enc += [xi - px, yi - py]
            px, py = xi, yi
        out.append(enc)
    return out

keep_ids = sorted(giant)
remap = {old: new for new, old in enumerate(keep_ids)}
out_streets = []
for old in keep_ids:
    st = streets[old]
    out_streets.append({
        "n": st["display"],
        # solo claves NO derivables del nombre (el frontend regenera las demás)
        "k": sorted(st["keys"] - alias_keys(st["display"])),
        "c": st["rank"],
        "g": encode_lines(st),
        "a": sorted(remap[b] for b in adj[old] if b in giant),
    })
out_inters = [[lon, lat, [remap[s] for s in ss]] for lon, lat, ss in cands]

city = {"city": "Gran Santiago", "enc": 1e5,
        "streets": out_streets, "intersections": out_inters}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(city, f, ensure_ascii=False, separators=(",", ":"))
import os
print(f"OK -> {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB)")
