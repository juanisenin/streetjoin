// Verificación del backend real del diario. Corre contra el Supabase que esté
// configurado en web/template.html. No necesita navegador: node web/test_daily_live.mjs
//
// Escribe con la fecha de AYER y jugadores uuid al azar, así el ranking de hoy
// —el que ve la gente— no se ensucia. Al final dice cómo borrar esas filas.
import { readFileSync } from "node:fs";

const tpl = readFileSync(new URL("./template.html", import.meta.url), "utf8");
const url = /url:\s*"([^"]+)"/.exec(tpl)?.[1];
const key = /key:\s*"([^"]+)"/.exec(tpl)?.[1];
if (!url || !key) { console.error("No hay BACKEND configurado en template.html"); process.exit(1); }
const base = url.replace(/\/+$/, "").replace(/\/rest\/v1$/, "") + "/rest/v1";
console.log("proyecto:", base.replace("/rest/v1", ""));

let fails = 0;
const ok = (c, m) => { if (!c) fails++; console.log((c ? "✓" : "✗ FALLO") + " " + m); };
const headers = { "Content-Type": "application/json", apikey: key };
if (/^eyJ/.test(key)) headers.Authorization = "Bearer " + key;

async function rpc(fn, body) {
  const r = await fetch(`${base}/rpc/${fn}`, { method: "POST", headers, body: JSON.stringify(body) });
  const txt = await r.text();
  let json = null; try { json = JSON.parse(txt); } catch {}
  return { status: r.status, json, txt };
}
const uuid = () => crypto.randomUUID();
const dia = n => new Date(Date.now() - 4 * 3600e3 - n * 86400e3).toISOString().slice(0, 10);
const HOY = dia(0), AYER = dia(1);

// 1. las funciones existen y anon puede ejecutarlas
let r = await rpc("sj_today", {});
ok(r.status === 200, `sj_today responde ${r.status}` + (r.status !== 200 ? " → " + r.txt : ""));
ok(r.json === HOY, `el día del servidor coincide con el del cliente: ${r.json} vs ${HOY}`);

r = await rpc("daily_board", { p_day: "2020-01-01", p_player: null });
ok(r.status === 200 && r.json && r.json.total === 0 && Array.isArray(r.json.top),
   "daily_board de un día vacío devuelve un tablero vacío: " + r.txt.slice(0, 120));

// 2. la tabla NO se toca directo con la clave pública
const dir = await fetch(`${base}/daily_results?select=*`, { headers });
ok(dir.status !== 200 || (await dir.clone().json()).length === 0,
   `acceso directo a la tabla bloqueado (HTTP ${dir.status})`);

// 3. enviar un resultado y recibir el puesto
const p1 = uuid();
r = await rpc("submit_daily", { p_day: AYER, p_player: p1, p_nick: "  test  bot  ", p_ms: 251000, p_streets: 6 });
ok(r.status === 200 && r.json && r.json.rank >= 1 && r.json.total >= 1,
   `submit_daily devuelve puesto: ${r.txt.slice(0, 120)}`);
const total1 = r.json?.total;

// 4. un segundo jugador más rápido queda primero, y el primero baja un puesto
const p2 = uuid();
r = await rpc("submit_daily", { p_day: AYER, p_player: p2, p_nick: "test bot 2", p_ms: 99000, p_streets: 4 });
ok(r.json?.rank === 1, `el más rápido queda 1º: ${r.txt.slice(0, 80)}`);
ok(r.json?.total === total1 + 1, `el total sube a ${r.json?.total}`);

// 5. el tiempo no se pisa; el apodo sí se puede cambiar
r = await rpc("submit_daily", { p_day: AYER, p_player: p1, p_nick: "renombrado", p_ms: 1000, p_streets: 1 });
ok(r.status === 200, "re-enviar con otro apodo no falla");
r = await rpc("daily_board", { p_day: AYER, p_player: p1 });
const mio = r.json?.top?.find(x => x.me);
ok(mio && mio.ms === 251000, `el tiempo original se mantiene: ${mio?.ms}`);
ok(mio && mio.nick === "renombrado", `el apodo se actualizó: ${mio?.nick}`);

// 6. el tablero tiene la forma que espera el juego
const b = r.json;
ok(b && ["streets", "times", "top", "total"].every(k => k in b),
   "daily_board devuelve {top, times, streets, total}");
ok(b?.top?.every((x, i) => i === 0 || b.top[i - 1].ms <= x.ms), "el top viene ordenado por tiempo");
ok(b?.times?.length === b?.total, `times tiene ${b?.times?.length} valores para ${b?.total} resultados`);

// 7. validaciones del servidor
for (const [caso, body] of [
  ["tiempo absurdo (100 ms)",   { p_day: AYER, p_player: uuid(), p_nick: "x", p_ms: 100, p_streets: 5 }],
  ["calles absurdas (500)",     { p_day: AYER, p_player: uuid(), p_nick: "x", p_ms: 200000, p_streets: 500 }],
  ["fecha vieja (hace 10 días)",{ p_day: dia(10), p_player: uuid(), p_nick: "x", p_ms: 200000, p_streets: 5 }],
  ["fecha futura (mañana)",     { p_day: dia(-1), p_player: uuid(), p_nick: "x", p_ms: 200000, p_streets: 5 }],
]) {
  const q = await rpc("submit_daily", body);
  ok(q.status >= 400, `rechaza ${caso} (HTTP ${q.status})`);
}

console.log(`\n${fails ? "HAY FALLOS" : "TODO OK"} · fallos: ${fails}`);
console.log(`\nQuedaron filas de prueba en el día ${AYER} (apodos "renombrado" y "test bot 2").`);
console.log(`Para borrarlas: Supabase → Table Editor → daily_results → filtrar por day = ${AYER} → borrar.`);
console.log("No se tocó el ranking de hoy.");
process.exit(fails ? 1 : 0);
