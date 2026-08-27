// Calibración del modo Lugares: distribución de distancia y de dificultad de
// los puzzles, y cuántas comunas aparecen. Es la medición con la que se fijó
// MAX_KM_PLACES al ampliar la lista de lugares a las 35 comunas.
//   node web/measure_places.mjs [nº de semillas]
import { chromium } from "playwright";

const N = Number(process.argv[2] || 400);
const b = await chromium.launch({ executablePath: "/opt/pw-browsers/chromium",
                                  args: ["--headless=new", "--no-sandbox"] });
const pg = await b.newPage();
pg.on("pageerror", e => console.log("JS ERROR", e.message));
await pg.route("**basemaps.cartocdn.com**", r => r.abort());
await pg.goto(new URL("../index.html", import.meta.url).href);
await pg.waitForFunction(() => window.__gameReady === true);

const rows = await pg.evaluate(n => {
  window.game.setGameMode("lugares", false);
  const out = [];
  for (let s = 1; s <= n; s++) {
    window.game.start(s);
    const g = window.game.state();
    if (!g) { out.push(null); continue; }
    const [A, B] = [g.A, g.B];
    const k = Math.cos(A[1] * Math.PI / 180);
    out.push({ a: A.label, ca: A.sub, b: B.label, cb: B.sub, opt: g.opt,
               km: +Math.hypot((A[0] - B[0]) * 111.32 * k, (A[1] - B[1]) * 111.32).toFixed(1) });
  }
  return out;
}, N);
await b.close();

const ok = rows.filter(Boolean);
const kms = ok.map(x => x.km).sort((a, b) => a - b);
const q = f => kms[Math.floor(f * (kms.length - 1))];
console.log(`puzzles: ${ok.length} de ${rows.length}`);
console.log(`km  min ${q(0)}  p25 ${q(.25)}  mediana ${q(.5)}  p75 ${q(.75)}  p90 ${q(.9)}  max ${q(1)}`);
const opts = {}; ok.forEach(x => opts[x.opt] = (opts[x.opt] || 0) + 1);
console.log("óptimo (nº de calles):", opts);
const com = new Set(); ok.forEach(x => { com.add(x.ca); com.add(x.cb); });
console.log("comunas que aparecen:", com.size);
console.log("\nmuestra:");
ok.slice(0, 8).forEach(x => console.log(`   ${x.km} km · ${x.opt} calles   ${x.a} (${x.ca}) → ${x.b} (${x.cb})`));
