# StreetJoin — Fase 4: Deploy ✅ (2026-08-25)

## Dónde está

- **Jugable en https://juanisenin.github.io/streetjoin/**
- Repo: https://github.com/juanisenin/streetjoin (público — GitHub Pages gratis lo exige)
- Rama `main`, carpeta raíz. Cada `git push` republica solo (build de Pages ~30 s).

## Cambios de estructura

`build_web.py` ahora escribe **`index.html` en la raíz del repo** en vez de
`web/streetjoin.html`, que es lo que GitHub Pages sirve sin configuración. El build viejo
quedó en `.gitignore`. Se agregó `.nojekyll` para que Pages no procese nada.

`web/test_blind.mjs` apuntaba a una ruta absoluta de un sandbox viejo
(`file:///root/StreetJoin/…`); ahora resuelve `../index.html` relativo al propio test.

## Bug de móvil encontrado al publicar

Con el juego arriba, lo primero fue medirlo en viewport de celular (Playwright, iPhone 13
y Pixel 5). El resultado: `window.innerWidth` daba **589 px en una pantalla de 390**.

**Causa.** `#inputrow` es un flex de una fila con el input y hasta 5 botones
(Probar · 📍 · ↻ · 🏠 · ⚙). Su ancho mínimo —el input no baja de su `min-content` y los
botones no encogen— es ~589 px. Al no entrar, el navegador móvil aplica *shrink-to-fit* y
achica **toda la página al 66%**: el juego se veía entero pero con todo el texto chico y
los botones difíciles de tocar. No es un bug visible en el escritorio, por eso nunca había
aparecido.

**Arreglo** (`@media (max-width: 560px)`, primer media query del proyecto):

| | Antes | Ahora |
|---|---|---|
| Input | en la fila con los botones | fila propia, ancho completo (`flex: 1 0 100%`) |
| Botones | misma fila, `padding: 10px 18px` | segunda fila, `padding: 10px 14px`, Probar se estira |
| Sugerencias | `right: 90px` (dejaba lugar a los botones) | `right: 0` + `max-height: 45vh` con scroll |
| Alto | `height: 100%` | `100dvh` donde exista, por la barra del navegador |
| Panel | `padding` fijo | suma `env(safe-area-inset-bottom)` para el iPhone |

Después del cambio el viewport es el real (390 / 393 px), no hay overflow horizontal y
ningún botón queda por debajo de 40 px de lado.

## Verificación

- Suite propia `web/test_blind.mjs` completa en verde (incluidas las 40 partidas del camino
  final y las 60 del desvío de ruta: máximo 74 m, mediana 18 m).
- Capturas en viewport de iPhone del menú, la partida y el autocompletar.
- El commit publicado por Pages coincide con el local.

## Pendiente

- Jugarlo en un celular de verdad (el test es emulación, no reemplaza el dedo).
- Fase 3 — desafío diario: es lo que le falta para que tenga sentido volver todos los días.
