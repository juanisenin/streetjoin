import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium", args: ["--headless=new","--no-sandbox"] });
const pg = await b.newPage();
const errs = [];
pg.on("pageerror", e => errs.push(String(e)));
await pg.goto("file:///root/StreetJoin/web/streetjoin.html");
await pg.waitForFunction(() => window.__gameReady === true, null, { timeout: 30000 });
let fails = 0;
const ok = (c, m) => { if (!c) fails++; console.log((c ? "✓" : "✗ FALLO") + " " + m); };

// --- el juego arranca en el menú, con Lugares a ciegas como modo principal ---
let m = await pg.evaluate(() => ({
  menu: document.getElementById("menu").classList.contains("open"),
  modo: window.game.gameMode(), blind: window.game.blind(), sub: window.game.mode(),
}));
ok(m.menu, "arranca en el menú principal");
ok(m.modo === "lugares" && m.blind && m.sub === "places",
   "el modo principal es lugares a ciegas: " + JSON.stringify(m));

// --- entrar a esquinas a ciegas ---
await pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("esquinas"); });
await pg.waitForTimeout(300);
let s = await pg.evaluate(() => ({
  blind: window.game.blind(),
  legendOff: legend.style.display === "none",
  legendBlindOn: legendBlind.style.display !== "none",
  namesDisabled: optNames.disabled,
  tileUrls: [...document.querySelectorAll("img.leaflet-tile")].map(i => i.src).slice(0, 3),
  tries: tries.textContent,
  t0: window.game.state().t0,
  showNamesEff: window.game.opts.hoverName,
}));
ok(s.blind, "modo ciego activo");
ok(s.legendOff && s.legendBlindOn, "leyenda cambia a conecta/suelta");
ok(s.namesDisabled, "'mostrar nombre al apuntar' bloqueado");
ok(s.tileUrls.every(u => u.includes("light_nolabels")), "teselas sin etiquetas: " + s.tileUrls[0]);
ok(/⏱ 0:00/.test(s.tries), "cronómetro en 0:00 antes del 1er intento → " + s.tries);
ok(s.t0 === null, "el reloj no corre todavía");

// --- jugar en orden invertido: la del medio primero (debe quedar SUELTA) ---
const chain = await pg.evaluate(() => window.game.optimalChain().map(i => window.game.streets[i].n));
console.log("  cadena óptima:", chain.join(" → "));
ok(chain.length >= 3, "puzzle con al menos 3 calles para probar 'suelta'");

const mid = chain[Math.floor(chain.length / 2)];
await pg.evaluate(n => window.game.guess(n), mid);
await pg.waitForTimeout(50);
s = await pg.evaluate(() => ({
  msg: msg.textContent, chips: [...chips.children].map(c => c.textContent),
  t0: window.game.state().t0, tries: tries.textContent,
}));
ok(/○/.test(s.msg), "calle del medio → 'todavía suelta': " + s.msg);
// Un nombre puede arrastrar más de una calle si comparte alias ("Ruta 78" es
// también "Avenida Isabel Riquelme"): lo que importa es que TODAS queden sueltas.
ok(s.chips.length >= 1 && s.chips.every(c => c.startsWith("○")),
   "chip con ○: " + s.chips);
ok(s.t0 !== null, "el cronómetro arrancó con el primer intento");
ok(new RegExp(`· ${s.chips.length} calles?`).test(s.tries),
   "el contador coincide con los chips: " + s.tries);

// --- ahora la primera de la cadena: toca A, debe quedar conectada ---
await pg.evaluate(n => window.game.guess(n), chain[0]);
await pg.waitForTimeout(50);
s = await pg.evaluate(() => ({ msg: msg.textContent,
  chips: [...chips.children].map(c => c.textContent[0]) }));
ok(/✓/.test(s.msg), "calle que toca A → conectada: " + s.msg);

// --- completar la cadena y verificar que las sueltas se vuelven ✓ ---
for (const n of chain) {
  if (await pg.evaluate(() => window.game.state().over)) break;
  await pg.evaluate(x => window.game.guess(x), n);
  await pg.waitForTimeout(30);
}
// al ganar se dibuja el camino final: el cartel aparece recién cuando termina
await pg.waitForFunction(() => getComputedStyle(overlay).display === "flex",
                         null, { timeout: 10000 });
s = await pg.evaluate(() => ({
  over: window.game.state().over,
  routePts: window.__lastResult.routePts,
  res: window.__lastResult,
  chips: [...chips.children].map(c => c.textContent[0]),
  title: ovTitle.textContent, text: ovText.textContent,
  overlay: getComputedStyle(overlay).display,
  tiles: [...document.querySelectorAll("img.leaflet-tile")].map(i => i.src).slice(0, 3),
  tries: tries.textContent,
}));
ok(s.over && s.res.win, "partida ganada");
ok(s.res.blind === true && typeof s.res.ms === "number", "resultado registra modo ciego y ms: " + s.res.ms);
// Las calles de la cadena tienen que quedar ✓; una homónima arrastrada por un
// alias puede quedar suelta y está bien.
ok(s.chips.filter(c => c === "✓").length >= chain.length,
   "al cerrar el camino la cadena queda ✓: " + s.chips.join(""));
ok(s.overlay === "flex" && /Conectado en \d+:\d\d|Nueva mejor marca/.test(s.title), "overlay con tiempo: " + s.title);
ok(s.routePts > 1, "se armó el camino final punto a punto: " + s.routePts + " vértices");
ok(/volvieron los nombres/.test(s.text), "avisa que vuelven los nombres");
ok(s.tiles.every(u => u.includes("light_all")), "teselas CON etiquetas al terminar: " + s.tiles[0]);

// --- el reloj se detiene ---
const t1 = await pg.evaluate(() => window.game.elapsed());
await pg.waitForTimeout(600);
const t2 = await pg.evaluate(() => window.game.elapsed());
ok(t1 === t2, "el cronómetro se detiene al ganar");

// --- mejor marca ---
ok(await pg.evaluate(() => window.game.bestTime.corners !== null), "guarda la mejor marca");

// --- práctica restaura todo ---
await pg.evaluate(() => window.game.setGameMode("practica"));
await pg.waitForTimeout(300);
s = await pg.evaluate(() => ({
  blind: window.game.blind(), namesDisabled: optNames.disabled,
  tries: tries.textContent, legendOn: legend.style.display !== "none",
  tiles: [...document.querySelectorAll("img.leaflet-tile")].map(i => i.src).slice(0, 2),
}));
ok(!s.blind && !s.namesDisabled && s.legendOn, "práctica vuelve a mapa con nombres");
ok(/Intentos: 0 · óptimo/.test(s.tries), "vuelve el contador de intentos: " + s.tries);
ok(s.tiles.every(u => u.includes("light_all")), "teselas con etiquetas en modo normal");

// --- las ayudas solo existen en práctica ---
s = await pg.evaluate(() => ({
  opts: getComputedStyle(practiceOpts).display,
  modos: getComputedStyle(modesRow).display,
}));
ok(s.opts !== "none" && s.modos !== "none", "en práctica se ven las ayudas y el selector");

// --- volver al modo principal ---
await pg.evaluate(() => window.game.setGameMode("lugares"));
await pg.waitForTimeout(300);
s = await pg.evaluate(() => ({ mode: window.game.mode(), blind: window.game.blind(),
  obj: objective.textContent, tries: tries.textContent,
  opts: getComputedStyle(practiceOpts).display,
  modos: getComputedStyle(modesRow).display }));
ok(s.mode === "places" && s.blind, "el modo principal es ciego + lugares");
ok(s.opts === "none" && s.modos === "none", "fuera de práctica no existen las ayudas");
ok(/⏱/.test(s.tries), "cronómetro en Lugares: " + s.tries);
console.log("  objetivo:", s.obj);

// --- el camino final se arma siempre, no solo cuando el lugar cae sobre la calle ---
// (regresión: un tope absoluto de 130 m dejaba sin enganchar los extremos que
// son el centro de un parque o un estadio, y no se dibujaba nada)
const rutas = await pg.evaluate(() => {
  const g = window.game, S = g.streets, malas = [];
  let n = 0;
  for (const modo of ["lugares", "esquinas"])
    for (let s = 2000; s < 2020; s++) {
      g.setGameMode(modo, false); g.start(s);
      for (const i of g.optimalChain()) g.guess(S[i].n);
      n++;
      if (!(window.__lastResult?.routePts > 1)) malas.push(modo + ":" + s);
    }
  return { n, malas };
});
ok(rutas.malas.length === 0,
   `se armó el camino final en las ${rutas.n} partidas probadas` +
   (rutas.malas.length ? " — fallaron " + rutas.malas.join(", ") : ""));

// --- la ruta dibujada no se sale de las calles usadas ---
// (regresión: el fallback de crossPoints miraba en un solo sentido y podía
// enganchar dos calles en un punto a cientos de metros de una de ellas)
const desvio = await pg.evaluate(() => {
  const g = window.game, S = g.streets, D = g.__dbg, peores = [];
  const M = 110574, mLon = l => 111320 * Math.cos(l * Math.PI / 180);
  for (const modo of ["lugares", "esquinas"])
    for (let s = 3000; s < 3030; s++) {
      g.setGameMode(modo, false); g.start(s);
      for (const i of g.optimalChain()) g.guess(S[i].n);
      const route = g.winRoute(), chain = g.namedChain();
      if (!route || !chain) continue;
      const segs = [];
      for (const i of chain) for (const L of D.geoOf(i))
        for (let k = 1; k < L.length; k++) segs.push([L[k - 1], L[k]]);
      let peor = 0;
      // el primer y el último tramo son la recta de acceso al lugar: no cuentan
      for (let k = 1; k < route.length - 2; k++) {
        const p = route[k], q = route[k + 1];
        for (const f of [0, .25, .5, .75, 1]) {
          const m = [p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f];
          let d = Infinity;
          for (const [a, c] of segs) d = Math.min(d, D.segDist(m, a, c));
          peor = Math.max(peor, d);
        }
      }
      peores.push(Math.round(peor));
    }
  peores.sort((a, b) => a - b);
  return { n: peores.length, max: peores[peores.length - 1],
           mediana: peores[Math.floor(peores.length / 2)] };
});
ok(desvio.max <= 120,
   `la ruta se mantiene sobre las calles usadas en ${desvio.n} partidas ` +
   `(desvío máximo ${desvio.max} m, mediana ${desvio.mediana} m)`);

ok(errs.length === 0, "sin errores de JS " + errs.join(" | "));
await b.close();
console.log(fails ? `\n${fails} FALLOS` : "\nTodo OK");
process.exit(fails ? 1 : 0);
