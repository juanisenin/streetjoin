#!/usr/bin/env python3
"""Genera index.html autocontenido (raiz del repo, lo que publica GitHub Pages):
template + Leaflet inline + city.json"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

tpl = open(os.path.join(HERE, "template.html")).read()
css = open(os.path.join(ROOT, "node_modules/leaflet/dist/leaflet.css")).read()
js = open(os.path.join(ROOT, "node_modules/leaflet/dist/leaflet.js")).read()
data = open(os.path.join(ROOT, "data-pipeline/city.json")).read()

tpl = re.sub(r'<link rel="stylesheet" href="[^"]*leaflet[^"]*">',
             lambda m: "<style>" + css + "</style>", tpl)
tpl = re.sub(r'<script src="[^"]*leaflet[^"]*"></script>',
             lambda m: "<script>" + js + "</script>", tpl)
# JSON.parse(string) es ~2x más rápido que un objeto literal JS de este tamaño:
# el motor usa el parser de JSON en vez del parser de JavaScript completo.
tpl = tpl.replace("__CITY_DATA__", "JSON.parse(" + json.dumps(data) + ")")

out = os.path.join(ROOT, "index.html")
open(out, "w").write(tpl)
print(f"OK -> {out} ({os.path.getsize(out)/1e6:.2f} MB)")
