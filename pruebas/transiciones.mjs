// Lo que ves es lo que exportas, también en las transiciones: la vista previa (CSS y el lienzo de pintarPasos) en Chromium contra
// los cuadros que exporta ffmpeg de verdad (pruebas/cuadros_transiciones.py), en una grilla chica. Mide además cuánto cuesta exportar.
// Uso: node pruebas/transiciones.mjs   (necesita Playwright y ffmpeg; CAPTURAS=carpeta guarda la vista previa y lo exportado en PNG)
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const CAPTURAS = process.env.CAPTURAS || "";
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".ttf": "font/ttf", ".jpg": "image/jpeg", ".mp3": "audio/mpeg" };
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, "ui", decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(path.join(RAIZ, "ui")) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  const total = fs.statSync(ruta).size, m = /bytes=(\d*)-(\d*)/.exec(q.headers.range || ""), tipo = tipos[path.extname(ruta)] || "application/octet-stream";
  if (!m) { r.writeHead(200, { "Content-Type": tipo, "Content-Length": total, "Accept-Ranges": "bytes" }); return fs.createReadStream(ruta).pipe(r); }
  const i = m[1] ? Number(m[1]) : 0, f = m[2] ? Number(m[2]) : total - 1;
  r.writeHead(206, { "Content-Type": tipo, "Content-Range": `bytes ${i}-${f}/${total}`, "Content-Length": f - i + 1, "Accept-Ranges": "bytes" });
  fs.createReadStream(ruta, { start: i, end: f }).pipe(r);
}).listen(0);
const BASE = `http://localhost:${servidor.address().port}/index.html?idioma=es`;

// El proyecto de la demo con dos pedazos: 5–6,5 s y 8–9,5 s del original → una unión (un corte) en 1,5 s del video exportado.
const demo = JSON.parse(fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8"));
const proyecto = { ...demo.proyectos[0].proyecto, palabras: [], zooms: [], textos: [], musica: null, divisiones: [],
  subtitulos: { ...demo.proyectos[0].proyecto.subtitulos, activos: false },
  cortes: [{ i: 0, f: 5, motivo: "manual" }, { i: 6.5, f: 8, motivo: "manual" }, { i: 9.5, f: demo.proyectos[0].proyecto.fuente.duracion, motivo: "manual" }] };
const original = (te) => (te < 1.5 ? 5 + te : 8 + te - 1.5);
// Cada transición en cuadros donde se nota (cuadro n = n/30 s del exportado).
const CASOS = [
  { nombre: "interferencia", pasos: [{ tipo: "interferencia", duracion: 0.6, intensidad: 1 }], cuadros: [41, 46] },
  { nombre: "destello", pasos: [{ tipo: "destello", duracion: 0.5, color: "#FFC46B", intensidad: 0.8, exposicion: 0.7 }], cuadros: [43, 46] },
  { nombre: "franjas", pasos: [{ tipo: "franjas", duracion: 0.8, franjas: 3, direccion: "vertical" }], cuadros: [41, 48] },
  { nombre: "persiana", pasos: [{ tipo: "franjas", duracion: 0.6, franjas: 2, direccion: "horizontal" }], cuadros: [42, 47] },
  { nombre: "rebote", pasos: [{ tipo: "rebote", duracion: 0.6, intensidad: 1 }], cuadros: [44, 47] },
  { nombre: "barrido", pasos: [{ tipo: "barrido", duracion: 0.6, direccion: "izquierda", desenfoque: 0.5 }], cuadros: [40, 49] },
  { nombre: "deslizar-arriba", pasos: [{ tipo: "barrido", duracion: 0.6, direccion: "arriba" }], cuadros: [42, 48] },
  { nombre: "zoom-de-paso", pasos: [{ tipo: "zoom_paso", duracion: 0.6, intensidad: 0.8, desenfoque: 0.4 }], cuadros: [43, 47] },
];
const [GW, GH] = [18, 32];

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "corta-transiciones-"));
fs.writeFileSync(path.join(tmp, "entrada.json"), JSON.stringify({ proyecto: { ...proyecto, fuente: { ...proyecto.fuente, archivo: "ana.mp4" } },
  video: path.join(RAIZ, "ui", "demo", "ana.mp4"), grilla: [GW, GH],
  casos: [{ nombre: "sin", pasos: null, tiempos: [...new Set(CASOS.flatMap((c) => c.cuadros))].map((n) => n / 30) },
    ...CASOS.map((c) => ({ nombre: c.nombre, pasos: c.pasos, tiempos: c.cuadros.map((n) => n / 30) }))] }));
const r = spawnSync("python3", [path.join(RAIZ, "pruebas", "cuadros_transiciones.py"), path.join(tmp, "entrada.json"), path.join(tmp, "salida.json")], { encoding: "utf8" });
if (r.status !== 0) { console.log(r.stderr); process.exit(1); }
const exportado = JSON.parse(fs.readFileSync(path.join(tmp, "salida.json"), "utf8"));
const sin = Object.fromEntries(exportado.sin.tiempos.map((t, k) => [Math.round(t * 30), exportado.sin.cuadros[k]]));

const navegador = await chromium.launch();
const p = await navegador.newPage({ viewport: { width: 1360, height: 860 }, deviceScaleFactor: 1 });
p.on("pageerror", (e) => falla("error de JavaScript: " + e.message));
await p.goto(BASE); await p.waitForSelector(".app");
await p.evaluate((pr) => window.Corta._probar((E) => { Object.assign(E.proyectos[0].proyecto, JSON.parse(pr)); E.pestana = "efectos"; }), JSON.stringify(proyecto));
await p.waitForFunction(() => document.querySelector("#video")?.readyState >= 2, null, { timeout: 8000 }).catch(() => {});
const conVideo = await p.evaluate(() => { const v = document.querySelector("#video"); return v.readyState >= 2 && !!v.videoWidth; });
// Promedio por bloques de la vista previa (la captura de la pantalla), igual que la grilla de ffmpeg.
const grilla = (png) => p.evaluate(async ([b64, gw, gh]) => {
  const im = new Image(); im.src = "data:image/png;base64," + b64; await im.decode();
  const c = document.createElement("canvas"); c.width = im.width; c.height = im.height;
  const x = c.getContext("2d", { willReadFrequently: true }); x.drawImage(im, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height).data, r = [];
  for (let gy = 0; gy < gh; gy++) for (let gx = 0; gx < gw; gx++) {
    const s = [0, 0, 0]; let n = 0;
    for (let y = Math.floor(gy * c.height / gh); y < Math.floor((gy + 1) * c.height / gh); y++)
      for (let xx = Math.floor(gx * c.width / gw); xx < Math.floor((gx + 1) * c.width / gw); xx++) { const k = (y * c.width + xx) * 4; s[0] += d[k]; s[1] += d[k + 1]; s[2] += d[k + 2]; n++; }
    r.push(...s.map((v) => v / n));
  }
  return r;
}, [png.toString("base64"), GW, GH]);
// Diferencia media (0–255), sin el borde de la grilla (las esquinas redondeadas de la pantalla).
const dif = (a, b) => { let s = 0, n = 0; for (let y = 1; y < GH - 1; y++) for (let x = 1; x < GW - 1; x++) for (let c = 0; c < 3; c++) { const k = (y * GW + x) * 3 + c; s += Math.abs(a[k] - b[k]); n++; } return s / n; };

if (!conVideo) console.log("  - Este Chromium no reproduce H.264: la comparación con lo exportado no se hace");
else {
  const filas = [];
  for (const c of CASOS) {
    await p.evaluate((pasos) => window.Corta._probar((E) => { E.proyectos[0].proyecto.efectos = [{ efecto: "prueba", pasos: JSON.parse(pasos) }]; }), JSON.stringify(c.pasos));
    for (const [k, n] of c.cuadros.entries()) {
      await p.evaluate((t) => new Promise((listo) => { const v = document.querySelector("#video"); v.pause(); v.addEventListener("seeked", () => listo(), { once: true }); v.currentTime = t; }), original(n / 30) + 0.004);
      await p.evaluate(() => new Promise((listo) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(listo)))));
      const png = await p.locator("#pantalla").screenshot();
      if (CAPTURAS) fs.writeFileSync(path.join(CAPTURAS, `vista-${c.nombre}-${n}.png`), png);
      const vista = await grilla(png), con = exportado[c.nombre].cuadros[k], base = sin[n];
      const dCon = dif(vista, con), dSin = dif(vista, base), efecto = dif(con, base);
      filas.push(`${c.nombre} ${n}: vista↔export ${dCon.toFixed(1)} · vista↔sin efecto ${dSin.toFixed(1)} · el efecto mueve ${efecto.toFixed(1)}`);
      if (efecto < 4) falla(`${c.nombre} (cuadro ${n}): casi no cambia la imagen exportada (${efecto.toFixed(1)})`);
      // Lo fino (la interferencia) casi no mueve la grilla: basta que se parezca tanto como dos cuadros iguales (≈5).
      else if (dCon > 14 || (dCon > 0.6 * dSin && dCon > 7)) falla(`${c.nombre} (cuadro ${n}): la vista previa no se parece a lo exportado (${dCon.toFixed(1)}; sin efecto ${dSin.toFixed(1)})`);
    }
  }
  if (process.env.DETALLE) filas.forEach((f) => console.log("    " + f));
  if (!errores.length) console.log(`  ✓ Transiciones: la vista previa se parece a lo exportado en ${CASOS.length} transiciones (${filas.length} cuadros)`);
}
// Exportar con cada transición dura lo mismo y cuesta poco más que sin ella (3 s a 1080×1920 con ffmpeg de verdad).
for (const c of CASOS) if (Math.abs(exportado[c.nombre].duracion - 3) > 0.1) falla(`${c.nombre}: el video exportado dura ${exportado[c.nombre].duracion} s y no 3 s`);
console.log("  · Exportar 3 s: sin efecto " + exportado.sin.segundos + " s; " + CASOS.map((c) => `${c.nombre} ${exportado[c.nombre].segundos} s`).join(", "));
await navegador.close(); servidor.close();
fs.rmSync(tmp, { recursive: true, force: true });
if (errores.length) { console.log(`✗ Transiciones: ${errores.length} problemas`); process.exit(1); }
console.log("✓ Transiciones OK");
