// Verificaciones del desafío diario. Usa la población simulada (sin BACKEND
// configurado), que es determinista a partir de la fecha.
import { chromium } from "playwright";
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium",
                                  args: ["--headless=new", "--no-sandbox"] });
const GAME = new URL("../index.html", import.meta.url).href;
const errs = [];
let fails = 0;
const ok = (c, m) => { if (!c) fails++; console.log((c ? "✓" : "✗ FALLO") + " " + m); };

async function nueva() {
  const ctx = await b.newContext();
  const pg = await ctx.newPage();
  pg.on("pageerror", e => errs.push(String(e)));
  await pg.goto(GAME);
  await pg.waitForFunction(() => window.__gameReady === true, null, { timeout: 30000 });
  return { ctx, pg };
}
// Juega el diario completo con la cadena óptima y espera el cartel.
async function jugarDiario(pg) {
  await pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("daily"); });
  await pg.waitForTimeout(400);
  const chain = await pg.evaluate(() => window.game.optimalChain().map(i => window.game.streets[i].n));
  for (const n of chain) { await pg.evaluate(x => window.game.guess(x), n); await pg.waitForTimeout(40); }
  await pg.waitForFunction(() => overlay.style.display === "flex", null, { timeout: 15000 });
  return chain;
}

// ---------------------------------------------------------------- 1. el puzzle
let { ctx, pg } = await nueva();
const meta = await pg.evaluate(() => {
  const d = window.game.daily;
  return { key: d.today(), n: d.number(d.today()), seed: d.seed(d.today()),
           seedAyer: d.seed("2026-08-26"), seedHoy: d.seed("2026-08-27") };
});
console.log(`  diario #${meta.n} · ${meta.key} · semilla ${meta.seed}`);
ok(Number.isInteger(meta.n) && meta.n > 0, "el número de día es un entero positivo: " + meta.n);
ok(meta.seedAyer !== meta.seedHoy, "días consecutivos → semillas sin parentesco");

await pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("daily"); });
await pg.waitForTimeout(400);
let s = await pg.evaluate(() => ({
  modo: window.game.gameMode(), blind: window.game.blind(), sub: window.game.mode(),
  seed: window.game.state().seed, esperada: window.game.daily.seed(window.game.daily.today()),
  daily: !!window.game.state().daily,
  nuevoOculto: getComputedStyle(document.getElementById("new")).display === "none",
  pickOculto: getComputedStyle(document.getElementById("pick")).display === "none",
  t0: window.game.state().t0,
  A: window.game.state().A.label, B: window.game.state().B.label,
}));
ok(s.modo === "daily" && s.blind && s.sub === "places", "el diario es lugares a ciegas");
ok(s.seed === s.esperada && s.daily, "el puzzle sale de la semilla del día");
ok(s.nuevoOculto && s.pickOculto, "en el diario no hay ↻ ni 📍");
ok(s.t0 === null, "el reloj no corre antes del primer intento");
console.log(`  conectar ${s.A} → ${s.B}`);

// el mismo puzzle en otra sesión del mismo día
const otra = await nueva();
await otra.pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("daily"); });
await otra.pg.waitForTimeout(400);
const s2 = await otra.pg.evaluate(() => ({ A: window.game.state().A.label,
                                           B: window.game.state().B.label,
                                           seed: window.game.state().seed }));
ok(s2.seed === s.seed && s2.A === s.A && s2.B === s.B,
   "otro jugador, el mismo día, recibe el mismo puzzle");
await otra.ctx.close();
await ctx.close();

// ------------------------------------------------- 2. jugarlo, ranking, compartir
({ ctx, pg } = await nueva());
const chain = await jugarDiario(pg);
console.log("  cadena:", chain.join(" → "));
let r = await pg.evaluate(() => ({
  st: window.game.daily.stored(),
  ovDaily: getComputedStyle(document.getElementById("ovDaily")).display !== "none",
  ovNew: getComputedStyle(document.getElementById("ovNew")).display === "none",
}));
ok(r.st.done && r.st.ms > 0, "el resultado queda guardado: " + JSON.stringify(r.st.ms));
ok(r.st.started > 0, "quedó marcado el momento del primer intento");
ok(r.ovDaily && r.ovNew, "el cartel ofrece el ranking y no 'jugar otro'");

await pg.waitForFunction(() => window.game.daily.stored().sent === true, null, { timeout: 10000 });
await pg.evaluate(() => window.game.daily.open(true));
await pg.waitForFunction(() => !window.game.daily.state().loading, null, { timeout: 10000 });
await pg.waitForTimeout(100);
r = await pg.evaluate(() => {
  const st = window.game.daily.stored(), bd = window.game.daily.state().board;
  return { rank: st.rank, total: st.total, ms: st.ms,
           abierto: document.getElementById("daily").classList.contains("open"),
           filas: document.querySelectorAll("#dBoard table.board tr").length,
           hists: document.querySelectorAll("#dBoard .hist").length,
           barras: [...document.querySelectorAll("#dBoard .hist")].map(h => h.children.length),
           mias: document.querySelectorAll("#dBoard .hist .bar.me").length,
           notas: [...document.querySelectorAll("#dBoard .histnote")].map(p => p.textContent),
           masRapidos: bd.times.filter(t => t < st.ms).length,
           total_bd: bd.total,
           share: window.game.daily.share(),
  };
});
ok(r.abierto, "la pantalla del diario se abre");
ok(r.rank >= 1 && r.rank <= r.total && r.total > 1,
   `puesto ${r.rank} de ${r.total}`);
ok(r.rank === r.masRapidos + 1, "el puesto coincide con cuántos fueron más rápidos");
ok(r.total === r.total_bd, "el total del puesto y el de la distribución coinciden");
ok(r.filas > 1 && r.filas <= 20, "tabla del top con " + r.filas + " filas");
ok(r.hists === 2, "las dos distribuciones (tiempo y calles): " + r.hists);
ok(r.barras.every(n => n >= 2 && n <= 15), "bins razonables: " + JSON.stringify(r.barras));
ok(r.mias === 2, "tu bin marcado en las dos distribuciones: " + r.mias);
ok(r.notas.length >= 2 && r.notas.every(t => /%/.test(t)), "percentiles: " + r.notas.join(" | "));
ok(/StreetJoin 📅 #\d+/.test(r.share) && /⏱ \d+:\d\d/.test(r.share) &&
   /puesto \d+ de \d+/.test(r.share) && r.share.includes("streetjoin"),
   "texto para compartir:\n---\n" + r.share + "\n---");

// apodo
await pg.evaluate(() => {
  document.getElementById("dNickInput").value = "  el  cuico  ";
  document.getElementById("dNickSave").click();
});
await pg.waitForTimeout(300);
r = await pg.evaluate(() => ({
  nick: window.game.daily.store.get("sj.nick"),
  enBoard: [...document.querySelectorAll("#dBoard tr.me td")].map(t => t.textContent),
  mine: document.getElementById("dMine").textContent,
}));
ok(r.nick === "el cuico", "el apodo se normaliza y se guarda: " + JSON.stringify(r.nick));
ok(r.mine.includes("el cuico"), "el apodo aparece en tu resultado");

// ------------------------------------------- 3. no se puede jugar dos veces hoy
await pg.reload();
await pg.waitForFunction(() => window.__gameReady === true, null, { timeout: 30000 });
r = await pg.evaluate(() => {
  window.game.showMenu(true);
  const card = document.querySelector('#menu [data-daily]').textContent;
  document.querySelector('#menu [data-go="daily"]').click();
  return { card, abierto: document.getElementById("daily").classList.contains("open"),
           modo: window.game.gameMode(), daily: !!window.game.state().daily };
});
ok(/Hoy:/.test(r.card), "el menú muestra el resultado de hoy: " + r.card.trim());
ok(r.abierto && !r.daily, "con el diario jugado, la tarjeta lleva al ranking y no a otra partida");

// --------------------------------- 4. recargar a mitad de partida no reinicia nada
const media = await nueva();
await media.pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("daily"); });
await media.pg.waitForTimeout(400);
const primera = await media.pg.evaluate(() => window.game.streets[window.game.optimalChain()[0]].n);
await media.pg.evaluate(x => window.game.guess(x), primera);
await media.pg.waitForTimeout(1600);
const antes = await media.pg.evaluate(() => ({ ms: window.game.elapsed(),
                                               seed: window.game.state().seed }));
await media.pg.reload();
await media.pg.waitForFunction(() => window.__gameReady === true, null, { timeout: 30000 });
await media.pg.evaluate(() => { window.game.showMenu(false); window.game.setGameMode("daily"); });
await media.pg.waitForTimeout(400);
const desp = await media.pg.evaluate(() => ({ ms: window.game.elapsed(),
                                              seed: window.game.state().seed,
                                              corriendo: window.game.state().t0 !== null,
                                              msg: document.getElementById("msg").textContent }));
ok(desp.seed === antes.seed, "tras recargar sigue el mismo puzzle del día");
ok(desp.corriendo && desp.ms >= antes.ms,
   `el reloj no se reinicia: ${(antes.ms/1000).toFixed(1)}s → ${(desp.ms/1000).toFixed(1)}s`);
ok(/reloj/.test(desp.msg), "se avisa que la partida sigue: " + desp.msg);
await media.ctx.close();
await ctx.close();

// ------------------------------------------------ 5. la capa de red está aislada
({ ctx, pg } = await nueva());
r = await pg.evaluate(async () => {
  const d = window.game.daily;
  const board = await d.net.fetchBoard("2026-01-15");
  const board2 = await d.net.fetchBoard("2026-01-15");
  return { online: d.online(),
           claves: Object.keys(board).sort(),
           mismo: JSON.stringify(board.times) === JSON.stringify(board2.times),
           n: board.times.length, top: board.top.length,
           ordenado: board.top.every((x, i) => i === 0 || board.top[i - 1].ms <= x.ms) };
});
ok(!r.online, "sin credenciales el juego usa la población simulada");
ok(JSON.stringify(r.claves) === '["streets","times","top","total"]',
   "fetchBoard devuelve {top, times, streets, total}: " + r.claves);
ok(r.mismo, "la población del día es determinista entre llamadas");
ok(r.n > 50 && r.top === 20 && r.ordenado, `${r.n} resultados, top ${r.top} ordenado por tiempo`);
await ctx.close();

await b.close();
if (errs.length) { console.log("\nErrores de JS en la página:"); errs.forEach(e => console.log("  " + e)); }
console.log(`\n${fails === 0 && !errs.length ? "TODO OK" : "HAY FALLOS"} · fallos: ${fails} · errores JS: ${errs.length}`);
process.exit(fails || errs.length ? 1 : 0);
