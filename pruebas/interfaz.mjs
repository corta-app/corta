// Pruebas de la interfaz (ui/) en un navegador real con los datos ficticios de ui/demo.json.
// Uso: node pruebas/interfaz.mjs   (necesita Playwright; PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
// Revisa: 1) la lógica de ui/app.js da lo mismo que Python (pruebas/casos.json); 2) ninguna vista tira errores de JavaScript
// (español e inglés, escritorio y celular); 3) todo texto tiene traducción en ui/idiomas/en.json; 4) nada se sale de la pantalla a
// ancho de celular; 5) contraste del botón principal; 6) editar por texto corta de verdad. Con CAPTURAS=carpeta guarda capturas.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(import.meta.url)(process.env.PLAYWRIGHT || "playwright");
const CAPTURAS = process.env.CAPTURAS || "";
const errores = [];
const falla = (m) => { errores.push(m); console.log("  ✗ " + m); };
const tipos = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".mp4": "video/mp4", ".ttf": "font/ttf" };
function servir(q, r, ruta, tipo) {
  // Con rangos (Range), como GitHub Pages: sin esto el navegador no puede adelantar el video.
  const total = fs.statSync(ruta).size, m = /bytes=(\d*)-(\d*)/.exec(q.headers.range || "");
  if (!m) { r.writeHead(200, { "Content-Type": tipo, "Content-Length": total, "Accept-Ranges": "bytes" }); return fs.createReadStream(ruta).pipe(r); }
  const i = m[1] ? Number(m[1]) : 0, f = m[2] ? Number(m[2]) : total - 1;
  r.writeHead(206, { "Content-Type": tipo, "Content-Range": `bytes ${i}-${f}/${total}`, "Content-Length": f - i + 1, "Accept-Ranges": "bytes" });
  fs.createReadStream(ruta, { start: i, end: f }).pipe(r);
}
const servidor = http.createServer((q, r) => {
  const ruta = path.join(RAIZ, "ui", decodeURIComponent(new URL(q.url, "http://x").pathname));
  if (!ruta.startsWith(path.join(RAIZ, "ui")) || !fs.existsSync(ruta) || fs.statSync(ruta).isDirectory()) { r.writeHead(404); return r.end(); }
  servir(q, r, ruta, tipos[path.extname(ruta)] || "application/octet-stream");
}).listen(0);
const BASE = `http://localhost:${servidor.address().port}/index.html`;
const demo = fs.readFileSync(path.join(RAIZ, "ui", "demo.json"), "utf8");
const casos = JSON.parse(fs.readFileSync(path.join(RAIZ, "pruebas", "casos.json"), "utf8"));
const esDato = (t) => demo.includes(t) || /^(Corta|Claude|ChatGPT \(Codex\)|Gemini|English|Español|9:16|1:1|4:5|16:9)$/.test(t);

const VISTAS = [
  ["texto", "E=>{E.pestana='texto'}"],
  ["texto-seleccion", "E=>{E.seleccion=[4,8];E.ancla=4}"],
  ["texto-limpio", "E=>{E.seleccion=null;E.ultimoAhorro=9.3}"],
  ["subtitulos", "E=>{E.pestana='subtitulos'}"],
  ["ia", "E=>{E.pestana='ia';E.ia={texto:'',enviando:false,historial:[{pedido:'Pon zoom',ok:true,resumen:'Listo.',aplicadas:1},{pedido:'x',ok:false,error:'x'}]}}"],
  ["ia-enviando", "E=>{E.ia.enviando=true;E.ia.texto='Pon un título'}"],
  ["shorts", "E=>{E.ia.enviando=false;E.pestana='shorts'}"],
  ["shorts-buscando", "E=>{E.buscandoShorts=true}"],
  ["shorts-lista", "E=>{E.buscandoShorts=false;E.shorts={lista:[{i:4,f:28,duracion:24,titulo:'Ahorra una hora',gancho:'¿Sabías…?',por_que:'Pregunta directa.'}]}}"],
  ["shorts-error", "E=>{E.shorts={error:'x'}}"],
  ["cuadrado-borroso", "E=>{E.pestana='texto';const p=E.proyectos[0].proyecto;p.lienzo='1:1';p.relleno='desenfoque'}"],
  ["horizontal", "E=>{const p=E.proyectos[0].proyecto;p.lienzo='16:9';p.relleno='recorte'}"],
  ["sin-transcripcion", "E=>{E.proyectos[0].proyecto.lienzo='9:16';E.sel=E.proyectos[1].carpeta}"],
  ["transcribiendo", "E=>{E.progreso[E.sel]={texto:'Transcribiendo en tu computador…',pct:40}}"],
  ["exportar", "E=>{E.progreso={};E.sel=E.proyectos[0].carpeta;E.exportar={paso:'pedir'}}"],
  ["exportando", "E=>{E.exportar={paso:'exportando',pct:45}}"],
  ["exportado", "E=>{E.exportar={paso:'listo',duracion:21}}"],
  ["exportar-error", "E=>{E.exportar={paso:'error',error:'x'}}"],
  ["ajustes", "E=>{E.exportar=null;E.ajustes=true}"],
  ["ajustes-al-dia", "E=>{E.buscando='alDia'}"],
  ["vacio", "E=>{E.ajustes=false;E.proyectos=[];E.sel=null}"],
];
const navegador = await chromium.launch();

// 1) Lógica compartida con Python
{
  const p = await navegador.newPage();
  await p.goto(BASE); await p.waitForFunction(() => window.Corta);
  const malos = await p.evaluate((c) => {
    const P = window.Corta._pruebas, m = [], igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    for (const k of c.conservados) { const r = P.conservados({ fuente: { duracion: k.duracion }, cortes: k.cortes }); if (!igual(r, k.esperado)) m.push("conservados " + JSON.stringify(r)); }
    for (const k of c.a_salida) { const r = P.aSalida({ fuente: { duracion: k.duracion }, cortes: k.cortes }, k.t); if (r !== k.esperado) m.push("aSalida " + r); }
    for (const k of c.cortar) { const p = { fuente: { duracion: c.duracion }, palabras: c.palabras, cortes: [] }; P.cortarPalabras(p, k.desde, k.hasta); if (!igual(p.cortes, k.esperado)) m.push("cortar " + JSON.stringify(p.cortes)); }
    { const p = { cortes: JSON.parse(JSON.stringify(c.restaurar.cortes)) }; P.restaurar(p, c.restaurar.i, c.restaurar.f); if (!igual(p.cortes, c.restaurar.esperado)) m.push("restaurar " + JSON.stringify(p.cortes)); }
    { const r = P.cortesPorPalabras(c.palabras, c.limpiar.silencio, c.limpiar.muletillas, c.duracion); if (!igual(r, c.limpiar.esperado)) m.push("limpiar " + JSON.stringify(r)); }
    { const r = P.lineas(c.palabras, c.lineas.por_linea).map((g) => g.map((w) => w.t)); if (!igual(r, c.lineas.esperado)) m.push("lineas " + JSON.stringify(r)); }
    return m;
  }, casos);
  malos.forEach((x) => falla("lógica distinta a Python: " + x));
  if (!malos.length) console.log("  ✓ Misma lógica que Python (pruebas/casos.json)");
  // 6) Editar por texto: elegir palabras y borrar las saca del video
  await p.evaluate(() => window.Corta._probar((E) => { E.bv = null; }));
  await p.click('[data-w="4"]'); await p.click('[data-w="8"]', { modifiers: ["Shift"] }); await p.keyboard.press("Backspace");
  const cortadas = await p.$$eval(".w.cortada", (els) => els.map((e) => e.dataset.w));
  if (!["4", "5", "6", "7", "8"].every((k) => cortadas.includes(k))) falla("borrar palabras elegidas no las cortó: " + cortadas.join(","));
  else console.log("  ✓ Editar por texto corta las palabras elegidas");
  await p.click('[data-accion="limpiar"]'); await p.waitForSelector(".ahorro, .limpiar small b", { timeout: 3000 }).catch(() => {});
  const ahorro = await p.textContent(".limpiar small");
  if (!/s/.test(ahorro || "")) falla("limpiar no mostró el ahorro"); else console.log("  ✓ Limpiar silencios muestra el ahorro");
  await p.close();
}

// 2–4) Todas las vistas
for (const [idioma, consulta] of [["español", "idioma=es"], ["inglés", "idioma=en"]]) {
  for (const [modo, opciones] of [["escritorio", { viewport: { width: 1360, height: 860 } }], ["celular", { viewport: { width: 390, height: 844 }, colorScheme: "light" }]]) {
    for (const bv of [false, true]) {
      const p = await navegador.newPage(opciones);
      p.on("pageerror", (e) => falla(`error de JavaScript (${idioma}, ${modo}): ${e.message}`));
      await p.addInitScript(() => { window._faltantes = new Set(); });
      await p.goto(BASE + "?" + [consulta, bv ? "bienvenida" : ""].filter(Boolean).join("&"));
      await p.waitForFunction(() => window.Corta && document.querySelector(".app"));
      const pasos = bv ? [0, 1, 2].map((n) => [`bienvenida-${n}`, `E=>{E.bv=${n}}`]) : VISTAS;
      for (const [nombre, f] of pasos) {
        await p.evaluate(`window.Corta._probar(${f})`);
        await p.waitForTimeout(80);
        if (modo === "celular") {
          const ancho = await p.evaluate(() => document.documentElement.scrollWidth);
          if (ancho > 392) falla(`se sale de la pantalla a ancho de celular (${ancho}px) en «${nombre}» (${idioma})`);
        }
        if (CAPTURAS && (idioma === "español" || modo === "escritorio")) await p.screenshot({ path: path.join(CAPTURAS, `${idioma}-${modo}-${nombre}.png`) });
      }
      if (idioma === "inglés") {
        const faltan = [...new Set(await p.evaluate(() => [...window._faltantes]))].filter((t) => !esDato(t));
        if (faltan.length) falla(`${faltan.length} textos sin traducción en ui/idiomas/en.json:\n      ` + faltan.map((t) => JSON.stringify(t)).join("\n      "));
      }
      await p.close();
    }
  }
  console.log(`  ✓ Vistas en ${idioma}`);
}

// 5) Contraste del botón principal
for (const esquema of ["light", "dark"]) {
  const p = await navegador.newPage({ colorScheme: esquema });
  await p.goto(BASE); await p.waitForSelector(".boton.principal");
  const c = await p.evaluate(() => {
    const lum = (s) => { const [r, g, b] = s.match(/[\d.]+/g).slice(0, 3).map((x) => { x = x / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const cs = getComputedStyle(document.querySelector(".boton.principal")); const a = lum(cs.color), b = lum(cs.backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
  if (c < 4.5) falla(`contraste del botón principal en modo ${esquema}: ${c.toFixed(2)} (mínimo 4.5)`);
  else console.log(`  ✓ Contraste en modo ${esquema === "light" ? "claro" : "oscuro"}: ${c.toFixed(2)}`);
  await p.close();
}
await navegador.close();
servidor.close();
if (errores.length) { console.log(`\n✗ ${errores.length} problemas`); process.exit(1); }
console.log("✓ Interfaz OK");
