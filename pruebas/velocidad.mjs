// Lo que ves es lo que exportas, también con velocidad por tramo: un proyecto con cámara lenta, rápida, una rampa y un corte se
// exporta de verdad (pruebas/cuadros_velocidad.py, con el número de cada cuadro del original escrito en la imagen) y se compara
// con la lógica de la vista previa (ui/app.js): cada cuadro exportado muestra el cuadro del original que dice aSalida (± 1), cada
// palabra aparece en su cuadro (± 1) y dura lo mismo. Después la vista previa reproduce el proyecto de verdad en Chromium y se mide
// que vaya al mismo ritmo y termine a tiempo. Al final mide cuánto cuesta exportar 8 s a cada velocidad.
// Uso: node pruebas/velocidad.mjs   (necesita Playwright y ffmpeg; MEDIR_FLUIDO=1 mide también «Más fluido», que tarda minutos)
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const CUADRO = 1 / 30;

// 8 s: 1–2,5 a 0,5×, 3–4 a 2×, un corte de 4 a 4,5, una rampa a 0,3× de 5 a 7 (con la voz) y 7–7,8 a 3×.
const proyecto = {
  subtitulos: { activos: true, estilo: "pop", palabras_por_linea: 1, posicion: 0.9 },
  cortes: [{ i: 4, f: 4.5, motivo: "manual" }],
  palabras: [["uno", 0.5], ["dos", 1.4], ["tres", 2.2], ["cuatro", 3.2], ["cinco", 4.7], ["seis", 5.6], ["siete", 6.3], ["ocho", 7.2]].map(([t, i]) => ({ t, i, f: i + 0.3 })),
  velocidades: [{ i: 1, f: 2.5, v: 0.5 }, { i: 3, f: 4, v: 2 }, { i: 5, f: 7, v: 0.3, rampa: true, audio: "tono" }, { i: 7, f: 7.8, v: 3 }],
};
const medir = [["1×", null], ["0,5×", { v: 0.5 }], ["0,25×", { v: 0.25 }], ["0,25× suavizado", { v: 0.25, suavizar: "mezcla" }], ["2×", { v: 2 }],
  ["3×", { v: 3 }], ["rampa 0,3×", { v: 0.3, rampa: true }], ...(process.env.MEDIR_FLUIDO ? [["0,5× más fluido", { v: 0.5, suavizar: "movimiento" }]] : [])]
  .map(([nombre, velocidad]) => ({ nombre, velocidad }));

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "corta-velocidad-"));
fs.writeFileSync(path.join(tmp, "entrada.json"), JSON.stringify({ proyecto, carpeta: tmp, medir, demo: path.join(RAIZ, "ui", "demo", "ana.mp4") }));
const r = spawnSync("python3", [path.join(RAIZ, "pruebas", "cuadros_velocidad.py"), path.join(tmp, "entrada.json"), path.join(tmp, "salida.json")], { encoding: "utf8" });
if (r.status !== 0) { console.log(r.stderr); process.exit(1); }
const ex = JSON.parse(fs.readFileSync(path.join(tmp, "salida.json"), "utf8"));

const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".ttf": "font/ttf", ".jpg": "image/jpeg" };
const servidor = http.createServer((q, res) => {
  const nombre = decodeURIComponent(new URL(q.url, "http://x").pathname);
  const ruta = nombre === "/prueba-velocidad.mp4" ? ex.video : path.join(RAIZ, "ui", nombre);
  if ((ruta !== ex.video && !ruta.startsWith(path.join(RAIZ, "ui"))) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { res.writeHead(404); return res.end(); }
  const total = fs.statSync(ruta).size, m = /bytes=(\d*)-(\d*)/.exec(q.headers.range || ""), tipo = tipos[path.extname(ruta)] || "application/octet-stream";
  if (!m) { res.writeHead(200, { "Content-Type": tipo, "Content-Length": total, "Accept-Ranges": "bytes" }); return fs.createReadStream(ruta).pipe(res); }
  const i = m[1] ? Number(m[1]) : 0, f = m[2] ? Number(m[2]) : total - 1;
  res.writeHead(206, { "Content-Type": tipo, "Content-Range": `bytes ${i}-${f}/${total}`, "Content-Length": f - i + 1, "Accept-Ranges": "bytes" });
  fs.createReadStream(ruta, { start: i, end: f }).pipe(res);
}).listen(0);

const navegador = await chromium.launch();
const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
p.on("pageerror", (e) => falla("error de JavaScript: " + e.message));
await p.goto(`http://localhost:${servidor.address().port}/index.html?idioma=es`); await p.waitForSelector(".app");
const completo = { ...proyecto, fuente: { archivo: "prueba-velocidad.mp4", duracion: 8, ancho: 360, alto: 640 }, zooms: [], textos: [], efectos: [], divisiones: [], musica: null };
await p.evaluate((pr) => window.Corta._probar((E) => { Object.assign(E.proyectos[0].proyecto, JSON.parse(pr)); }), JSON.stringify(completo));

// 1) La lógica de la vista previa contra lo exportado, cuadro por cuadro
const vista = await p.evaluate((n) => {
  let pr; window.Corta._probar((E) => { pr = E.proyectos[0].proyecto; });
  const P = window.Corta._pruebas;
  return { duracion: P.duracionFinal(pr), cuadros: Array.from({ length: n + 1 }, (_, k) => P.aSalida(pr, k / 30)), palabras: pr.palabras.map((w) => P.aSalida(pr, w.i)) };
}, 240);
const malos = [];
if (Math.abs(ex.duracion - vista.duracion) > CUADRO + 0.002) malos.push(`el exportado dura ${ex.duracion} s y la vista previa ${vista.duracion} s`);
ex.cuadros.forEach((n, k) => {
  if (n < 0) return malos.push(`el cuadro ${k} no se pudo leer`);
  const desde = vista.cuadros[n], hasta = vista.cuadros[n + 1] ?? desde;
  if (desde == null) return malos.push(`el cuadro ${k} muestra el ${n} del original, que estaba cortado`);
  // El cuadro n del original se ve desde aSalida(n/30) hasta el siguiente: el cuadro k (k/30 s) tiene que caer ahí (± 1 cuadro).
  if (k * CUADRO < desde - CUADRO - 0.002 || k * CUADRO > Math.max(desde, hasta ?? desde) + CUADRO + 0.002) malos.push(`cuadro ${k}: muestra el ${n} del original; la vista previa lo pone en ${desde}–${hasta} s`);
});
proyecto.palabras.forEach((w, j) => {
  const te = vista.palabras[j], k = Math.round(te * 30), a = ex.ass.find(([, t]) => t === w.t.toUpperCase());
  if (!a || Math.abs(a[0] - te) > 0.011) malos.push(`«${w.t}»: el subtítulo exportado empieza en ${a?.[0]} s y la vista previa dice ${te} s`);
  const n = ex.cuadros[k];
  if (Math.abs(n - Math.round(w.i * 30)) > 1) malos.push(`«${w.t}»: en su cuadro (${k}) se ve el ${n} del original y no el ${Math.round(w.i * 30)}`);
  if (!ex.texto[Math.min(ex.texto.length - 1, k + 1)] || (k > 2 && j === 0 && ex.texto[k - 2])) malos.push(`«${w.t}»: el subtítulo no aparece en su cuadro (${k})`);
});
malos.slice(0, 12).forEach(falla);
if (!malos.length) console.log(`  ✓ Exportado ↔ vista previa: ${ex.cuadros.length} cuadros muestran el cuadro del original que dice la vista previa (± 1), las ${proyecto.palabras.length} palabras salen en su cuadro y dura ${ex.duracion.toFixed(3)} s (vista previa ${vista.duracion} s)`);

// 2) La vista previa de verdad: reproducir todo y medir el ritmo contra el reloj
const conVideo = await p.evaluate(() => new Promise((listo) => {
  const v = document.querySelector("#video"); if (!v) return listo(false);
  if (v.readyState >= 2) return listo(true);
  v.addEventListener("loadeddata", () => listo(true), { once: true }); setTimeout(() => listo(v.readyState >= 2), 6000);
}));
if (!conVideo) console.log("  - Este Chromium no reproduce H.264: la reproducción de la vista previa no se mide");
else {
  const rep = await p.evaluate(() => new Promise((listo) => {
    let pr; window.Corta._probar((E) => { pr = E.proyectos[0].proyecto; });
    const P = window.Corta._pruebas, v = document.querySelector("#video"), muestras = [];
    v.currentTime = 0;
    v.addEventListener("seeked", () => {
      document.querySelector('[data-accion="play"]').click();
      const inicio = performance.now();
      const mirar = () => {
        const reloj = (performance.now() - inicio) / 1000, sale = P.aSalida(pr, v.currentTime);
        if (sale != null && !v.seeking) muestras.push([reloj, sale, v.playbackRate]);
        if (v.paused && reloj > 1) return listo({ total: reloj, muestras });
        if (reloj > 30) return listo({ total: reloj, muestras, colgado: true });
        requestAnimationFrame(mirar);
      };
      requestAnimationFrame(mirar);
    }, { once: true });
  }));
  // El retraso de arrancar se descuenta (la mediana de reloj − salida en el primer segundo); después, cada muestra en su lugar.
  const primeras = rep.muestras.filter(([t]) => t < 1).map(([t, s]) => t - s).sort((a, b) => a - b);
  const arranque = primeras[Math.floor(primeras.length / 2)] || 0;
  const peor = rep.muestras.reduce((m, [t, s]) => Math.max(m, Math.abs(t - arranque - s)), 0);
  const final = rep.total - arranque;
  if (rep.colgado) falla("la vista previa no terminó de reproducir");
  else if (Math.abs(final - vista.duracion) > 0.4) falla(`la vista previa dura ${final.toFixed(2)} s y el exportado ${ex.duracion.toFixed(2)} s`);
  else if (peor > 0.3) falla(`la vista previa se desfasa ${peor.toFixed(2)} s del video exportado`);
  else console.log(`  ✓ Vista previa reproducida: dura ${final.toFixed(2)} s (exportado ${ex.duracion.toFixed(2)} s) y nunca se desfasa más de ${peor.toFixed(2)} s`);
}
await navegador.close(); servidor.close();

// 3) Lo que cuesta exportar 8 s de la demo (1280×720 → 1080×1920) a cada velocidad
console.log("  · Exportar 8 s: " + ex.costos.map((c) => `${c.nombre} ${c.segundos} s (sale de ${c.duracion} s)`).join(", "));
fs.rmSync(tmp, { recursive: true, force: true });
if (errores.length) { console.log(`✗ Velocidad: ${errores.length} problemas`); process.exit(1); }
console.log("✓ Velocidad OK");
