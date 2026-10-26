// Pruebas de la interfaz (ui/) en un navegador real con los datos ficticios de ui/demo.json.
// Uso: node pruebas/interfaz.mjs   (necesita Playwright; PLAYWRIGHT=/ruta/a/playwright si no está instalado aquí)
// Revisa: 1) la lógica de ui/app.js da lo mismo que Python (pruebas/casos.json); 2) ninguna vista tira errores de JavaScript
// (español e inglés, escritorio y celular); 3) todo texto tiene traducción en ui/idiomas/en.json; 4) nada se sale de la pantalla a
// ancho de celular; 5) contraste del botón principal; 6) editar por texto corta de verdad; 7) la línea de tiempo mueve bordes con
// mouse, toque y teclado sin cambiar el formato, y la música suena y baja cuando hablas. Con CAPTURAS=carpeta guarda capturas.
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
// Datos de la demo (títulos, palabras, nombres de estilos…): se comparan textos completos, no pedazos, para que un texto de la
// interfaz que por casualidad aparece dentro de un dato («Texto» en «Texto blanco sobre…») igual se revise.
const datosDemo = new Set();
(function juntar(v) { if (typeof v === "string") datosDemo.add(v.replace(/\s+/g, " ").trim()); else if (v && typeof v === "object") Object.values(v).forEach(juntar); })(JSON.parse(demo));
const esDato = (t) => datosDemo.has(t) || /^(Corta|Claude|ChatGPT \(Codex\)|Gemini|English|Español|9:16|1:1|4:5|16:9)$/.test(t);

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
  ["musica", "E=>{E.shorts=null;E.pestana='musica'}"],
  ["musica-elegida", "E=>{E.proyectos[0].proyecto.musica={archivo:'demo/musica-demo.mp3',volumen:0.15}}"],
  ["linea-pistas", "E=>{const p=E.proyectos[0].proyecto;p.cortes=[{i:0,f:1.1,motivo:'silencio'},{i:3.3,f:4.6,motivo:'muletilla'},{i:9.5,f:10.4,motivo:'manual'},{i:20,f:21,motivo:'ia'},{i:28,f:30.24,motivo:'fuera'}];p.zooms=[{i:5.2,f:7.4,escala:1.25}];p.textos=[{i:1.2,f:4,texto:'Edita en 1 minuto',y:0.16}];E.lt.sel={lista:'textos',k:0}}"],
  ["linea-zoom", "E=>{E.lt.zoom=4;E.lt.sel={lista:'zooms',k:0}}"],
  ["linea-corte-sin-subtitulos", "E=>{E.lt.zoom=1;E.lt.sel={lista:'cortes',k:1};E.proyectos[0].proyecto.subtitulos.activos=false}"],
  ["musica-fuera-y-muda", "E=>{const p=E.proyectos[0].proyecto;p.subtitulos.activos=true;p.musica={archivo:'/otra/carpeta/cancion.mp3',volumen:0};E.lt.sel=null}"],
  ["musica-sin-transcripcion", "E=>{E.sel=E.proyectos[1].carpeta;E.proyectos[1].proyecto.musica={archivo:'demo/musica-demo.mp3',volumen:0.2}}"],
  ["volver", "E=>{E.sel=E.proyectos[0].carpeta;E.proyectos[0].proyecto.musica=null}"],
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

// 7) Línea de tiempo y música
{
  const p = await navegador.newPage({ viewport: { width: 1360, height: 860 } });
  p.on("pageerror", (e) => falla("error de JavaScript (línea de tiempo): " + e.message));
  await p.goto(BASE); await p.waitForFunction(() => window.Corta && document.querySelector("#lt-vista"));
  // Lógica de bordes y de cuándo baja la música
  const malos = await p.evaluate(() => {
    const P = window.Corta._pruebas, m = [], igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
    const l = [{ i: 1, f: 2, motivo: "manual" }, { i: 3, f: 4, motivo: "silencio" }];
    if (!igual(P.limitesBorde(l, 1, "i", 10), [2, 3.95])) m.push("límites inicio " + P.limitesBorde(l, 1, "i", 10));
    if (!igual(P.limitesBorde(l, 0, "f", 10), [1.05, 3])) m.push("límites fin " + P.limitesBorde(l, 0, "f", 10));
    if (P.moverBorde(l, 1, "i", 0.5, 10) !== 2) m.push("no se detuvo en el vecino");
    if (P.moverBorde(l, 1, "f", 99, 10) !== 10) m.push("se salió del video");
    if (P.moverBorde(l, 0, "f", 0.2, 10) !== 1.05) m.push("se dio vuelta el tramo");
    if (!igual(l, [{ i: 1, f: 1.05, motivo: "manual" }, { i: 2, f: 10, motivo: "silencio" }])) m.push("cambió algo más que el borde " + JSON.stringify(l));
    const p = { cortes: [{ i: 2, f: 3, motivo: "manual" }], palabras: [{ t: "a", i: 0.5, f: 1 }, { t: "b", i: 1.1, f: 1.5 }, { t: "c", i: 2.2, f: 2.6 }, { t: "d", i: 5, f: 5.5 }] };
    const voz = P.tramosVoz(p);
    if (!igual(voz, [{ i: 0.47, f: 1.9 }, { i: 4.97, f: 5.9 }])) m.push("tramosVoz " + JSON.stringify(voz));
    if (P.cuantoBaja(voz, 1.2) !== 0.25 || P.cuantoBaja(voz, 2.4) !== 1 || P.cuantoBaja(voz, 4) !== 1) m.push("cuantoBaja");
    return m;
  });
  malos.forEach((x) => falla("línea de tiempo: " + x));
  if (!malos.length) console.log("  ✓ Bordes con límites y música que baja con la voz (lógica)");
  const proyecto = () => p.evaluate(() => { let r; window.Corta._probar((E) => { r = JSON.parse(JSON.stringify(E.proyectos[0].proyecto)); }); return r; });
  await p.evaluate(() => window.Corta._probar((E) => { E.bv = null; const q = E.proyectos[0].proyecto; q.cortes = [{ i: 3.3, f: 4.6, motivo: "muletilla" }]; q.textos = [{ i: 8, f: 10, texto: "Hola", y: 0.2 }]; }));
  // Mouse: arrastrar el fin del corte 40 px a la derecha
  const caja = await p.locator("#lt-cortes-0-f").boundingBox();
  await p.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2); await p.mouse.down();
  await p.mouse.move(caja.x + caja.width / 2 + 20, caja.y + 10, { steps: 3 }); await p.mouse.move(caja.x + caja.width / 2 + 40, caja.y + 10, { steps: 3 }); await p.mouse.up();
  let q = await proyecto();
  if (!(q.cortes[0].f > 4.6) || q.cortes[0].i !== 3.3 || Object.keys(q.cortes[0]).join() !== "i,f,motivo") falla("arrastrar con el mouse no movió el borde: " + JSON.stringify(q.cortes));
  else console.log(`  ✓ Mouse: el borde se arrastra (fin del corte 4,6 → ${q.cortes[0].f} s)`);
  // Teclado: foco visible en el borde, flechas y que se guarde
  await p.focus("#lt-textos-0-i");
  for (let k = 0; k < 3; k++) await p.keyboard.press("ArrowRight");
  await p.keyboard.press("Shift+ArrowLeft");
  await p.waitForTimeout(900);
  q = await proyecto();
  const foco = await p.evaluate(() => [document.activeElement?.id, document.activeElement?.getAttribute("aria-valuenow"), getComputedStyle(document.activeElement).outlineStyle]);
  if (q.textos[0].i !== 7.3 || foco[0] !== "lt-textos-0-i" || foco[1] !== "7.3") falla("teclado en el borde: " + JSON.stringify([q.textos[0], foco]));
  else if (foco[2] === "none") falla("el borde enfocado no muestra el foco");
  else console.log("  ✓ Teclado: flechas mueven el borde, se guarda y el foco se ve");
  await p.keyboard.press("Delete");
  q = await proyecto();
  if (q.textos.length !== 0) falla("Suprimir no quitó el texto"); else console.log("  ✓ Suprimir quita el tramo");
  // Toque: los mismos eventos de puntero con el dedo
  const c2 = await p.locator("#lt-cortes-0-i").boundingBox();
  await p.evaluate(({ x, y }) => {
    const h = document.querySelector("#lt-cortes-0-i"), ev = (tipo, dx) => new PointerEvent(tipo, { bubbles: true, cancelable: true, pointerId: 7, pointerType: "touch", clientX: x + dx, clientY: y, isPrimary: true });
    h.dispatchEvent(ev("pointerdown", 0)); document.dispatchEvent(ev("pointermove", -15)); document.dispatchEvent(ev("pointermove", -30)); document.dispatchEvent(ev("pointerup", -30));
  }, { x: c2.x + c2.width / 2, y: c2.y + c2.height / 2 });
  q = await proyecto();
  if (!(q.cortes[0].i < 3.3)) falla("arrastrar con el dedo no movió el borde: " + JSON.stringify(q.cortes)); else console.log(`  ✓ Toque: el borde se arrastra (inicio 3,3 → ${q.cortes[0].i} s)`);
  // Zoom horizontal
  await p.click('[data-lt-zoom="1"]'); await p.click('[data-lt-zoom="1"]');
  const zoom = await p.evaluate(() => { const v = document.querySelector("#lt-vista"); return v.scrollWidth / v.clientWidth; });
  if (!(zoom > 1.9)) falla("el zoom de la línea de tiempo no agrandó las pistas: " + zoom); else console.log(`  ✓ Zoom de la línea de tiempo (×${zoom.toFixed(1)})`);
  await p.click('[data-lt-zoom="0"]');
  // Música: elegir (simulado), formato {archivo, volumen}, suena y baja cuando hablas
  await p.click('[data-pestana="musica"]'); await p.click('.cuerpo-panel [data-accion="elegir-musica"]');
  await p.waitForSelector("[data-musica-volumen]");
  q = await proyecto();
  if (JSON.stringify(Object.keys(q.musica)) !== '["archivo","volumen"]' || q.musica.volumen !== 0.15) falla("la música no quedó como {archivo, volumen}: " + JSON.stringify(q.musica));
  const palabras = q.palabras, larga = palabras.findIndex((w) => w.t === "una"), pausa = palabras.findIndex((w) => w.t === "videos?");
  await p.evaluate(() => window.Corta._probar((E) => { E.proyectos[0].proyecto.cortes = []; }));
  await p.click('[data-accion="escuchar-musica"]');
  await p.evaluate((t) => { document.querySelector("#video").currentTime = t; }, palabras[larga].i);
  await p.waitForTimeout(450);
  const hablando = await p.evaluate(() => { const a = window.Corta._pruebas.musica(); return { sonando: !a.paused && a.currentTime > 0, vol: a.volume, video: !document.querySelector("#video").paused }; });
  await p.evaluate((t) => { document.querySelector("#video").currentTime = t; }, palabras[pausa].f + 0.45);
  await p.waitForTimeout(950);
  const callado = await p.evaluate(() => { const a = window.Corta._pruebas.musica(); return { sonando: !a.paused, vol: a.volume, texto: document.querySelector("#musica-ahora")?.textContent }; });
  if (!hablando.sonando || !hablando.video) falla("la música no suena en la vista previa: " + JSON.stringify(hablando));
  else if (!(hablando.vol < 0.06 && callado.vol > 0.1)) falla(`la música no baja cuando hablas: ${hablando.vol.toFixed(3)} hablando, ${callado.vol.toFixed(3)} en la pausa`);
  else console.log(`  ✓ Música suena y baja cuando hablas (volumen ${hablando.vol.toFixed(3)} hablando, ${callado.vol.toFixed(3)} en la pausa: «${callado.texto}»)`);
  await p.click('[data-accion="escuchar-musica"]');
  await p.waitForTimeout(100);
  if (!(await p.evaluate(() => window.Corta._pruebas.musica().paused))) falla("la música sigue sonando con el video en pausa");
  await p.click('[data-accion="quitar-musica"]');
  if ((await proyecto()).musica !== null) falla("quitar la música no dejó musica: null");
  await p.close();
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
