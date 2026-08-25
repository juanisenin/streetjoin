# StreetJoin — Fase 1: Datos ✅ (v2 Gran Santiago, 2026-08-14)

## Resultado actual

`city.json` (6.0 MB) con **todo el Gran Santiago**: 41.876 calles, grafo 98.8% conexo (se usa la componente mayor), 6000 intersecciones candidatas a puzzle. Reemplaza a la v1 que cubría solo el centro (1039 calles).

- **Fuente**: extracto BBBike `Santiago.osm.pbf` (40 MB, OSM agosto 2026, quedó en Descargas del Mac). Cobertura real de calles: lon −70.97 → −70.42, lat −33.73 → −33.16 — toda la mancha urbana (Maipú, Puente Alto, San Bernardo, Colina, Las Condes…). **Melipilla, Talagante y San José de Maipo NO están en este extracto**; si se quieren, usar el de Geofabrik Chile (329 MB) y recortar.
- 529k segmentos con nombre, 27.069 nombres únicos, clases primary→residential + pedestrian (sin autopistas ni footways).

## Decisiones de diseño v2 (importante)

1. **Una "calle" = componente conexa de segmentos con el mismo nombre**, no todo lo que comparte nombre. Con 26 "Los Aromos" en comunas distintas, fusionarlas por nombre crearía "teletransportes" en el grafo. Cada homónima es una entidad separada; comparten claves de búsqueda.
2. **Fusión por cercanía**: componentes del mismo nombre a <150 m se unen (calles cortadas por plazas/autopistas siguen siendo una).
3. **Fusión Avenida X / X** solo si comparten intersección (160 pares).
4. **Geometrías delta-encoded**: enteros ×1e5, primera coordenada absoluta y luego deltas (campo `enc` en el JSON); simplificación más agresiva en calles residenciales.
5. **Intersecciones candidatas precomputadas**: ≥2 calles, al menos una arterial (clase ≤2), muestreadas a 6000 con seed fija.

## Pipeline

`python3 build_city.py Santiago.osm.pbf city.json` (~3 min; pyrosm + networkx + shapely + numpy). El formato de `streets[].{n,k,c,g,a}` e `intersections` se mantiene de v1, con `g` ahora delta-encoded.

## Notas

- El frontend juega TODAS las entidades de una clave ("los aromos" ilumina las 26, 1 intento), pero un texto que matchea exacto un nombre completo ("Avenida Balmaceda") juega solo esas entidades.
- Restricción del sandbox: sin acceso directo a servidores OSM; los datos entran por carpeta conectada del Mac.
